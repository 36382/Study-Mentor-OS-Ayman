"""Google Sheets data layer.

Primary mode: read + write through gspread with a Service Account
(``GOOGLE_SERVICE_ACCOUNT_JSON`` accepts raw JSON or Base64-encoded JSON).

Fallback mode: read-only from a local/public XLSX workbook (handled in
``study_sheet``); when this store is not configured the rest of the app must
degrade gracefully to read-only behaviour, never crash.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime
from typing import Any, Callable

from .config import (
    get_service_account_json,
    get_sheet_cache_ttl,
    get_study_sheet_id,
    get_study_sheet_url,
)
from .timeutils import now

_GSPREAD_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def parse_service_account(raw: str | None) -> dict | None:
    """Parse a service-account credential: raw JSON or Base64-encoded JSON."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("client_email"):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8")
        parsed = json.loads(decoded)
        if isinstance(parsed, dict) and parsed.get("client_email"):
            return parsed
    except Exception:
        return None
    return None


class SheetStore:
    """Cached read/write access to the study Google Sheet."""

    def __init__(
        self,
        service_account_json: str | None = None,
        sheet_id: str | None = None,
        sheet_url: str | None = None,
        cache_ttl: int | None = None,
    ) -> None:
        self.credentials = parse_service_account(service_account_json or get_service_account_json())
        self.sheet_id = sheet_id or get_study_sheet_id()
        self.sheet_url = sheet_url or get_study_sheet_url()
        self.cache_ttl = get_sheet_cache_ttl() if cache_ttl is None else max(0, int(cache_ttl))

        self.last_sync_at: datetime | None = None
        self.last_error: str | None = None

        self._client: Any = None
        self._client_failed = False
        self._doc: Any = None
        self._worksheets: dict[str, Any] = {}
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    # ------------------------------------------------------------ construction

    @classmethod
    def from_env(cls) -> "SheetStore":
        return cls()

    def is_configured(self) -> bool:
        return self.credentials is not None and bool(self.sheet_id or self.sheet_url)

    def is_writable(self) -> bool:
        """True only when credentials exist and the document opened successfully."""
        if not self.is_configured():
            return False
        return self._ensure_doc() is not None

    def mode(self) -> str:
        if self.is_writable():
            return "sheets"
        if self.credentials is not None:
            return "sheets-error"
        return "none"

    # ------------------------------------------------------------ internals

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if self._client_failed or self.credentials is None:
            return None
        try:
            import gspread

            self._client = gspread.service_account(info=self.credentials, scopes=_GSPREAD_SCOPES)
            return self._client
        except Exception as exc:
            self._client_failed = True
            self.last_error = f"gspread init failed: {exc}"
            return None

    def _ensure_doc(self):
        if self._doc is not None:
            return self._doc
        client = self._ensure_client()
        if client is None:
            return None
        try:
            if self.sheet_id:
                self._doc = client.open_by_key(self.sheet_id)
            elif self.sheet_url:
                self._doc = client.open_by_url(self.sheet_url)
        except Exception as exc:
            self._client_failed = True
            self.last_error = f"Cannot open Google Sheet: {exc}"
            return None
        self._worksheets.clear()
        return self._doc

    def _worksheet(self, tab: str):
        if tab in self._worksheets:
            return self._worksheets[tab]
        doc = self._ensure_doc()
        if doc is None:
            return None
        try:
            ws = doc.worksheet(tab)
        except Exception as exc:
            self.last_error = f"Tab '{tab}' not found: {exc}"
            return None
        self._worksheets[tab] = ws
        return ws

    # ------------------------------------------------------------ read API

    def get_records(self, tab: str, max_rows: int = 500) -> list[dict]:
        """All data rows of a tab as dicts keyed by the header row (cached)."""
        cached = self._cache.get(tab)
        if cached and self.cache_ttl > 0 and (time.time() - cached[0]) < self.cache_ttl:
            return cached[1]
        ws = self._worksheet(tab)
        if ws is None:
            return []
        try:
            values = ws.get_all_values()[: max_rows + 1]
        except Exception as exc:
            self.last_error = f"Read '{tab}' failed: {exc}"
            return []
        if not values:
            self._cache[tab] = (time.time(), [])
            return []
        headers = [str(h).strip() for h in values[0]]
        rows: list[dict] = []
        for raw in values[1:]:
            if not any(str(cell).strip() for cell in raw):
                continue
            record = {}
            for idx, header in enumerate(headers):
                record[header] = raw[idx] if idx < len(raw) else ""
            rows.append(record)
        self._cache[tab] = (time.time(), rows)
        self.last_sync_at = now()
        self.last_error = None
        return rows

    def invalidate_cache(self, tab: str | None = None) -> None:
        if tab is None:
            self._cache.clear()
        else:
            self._cache.pop(tab, None)

    # ------------------------------------------------------------ write API

    def ensure_tab(self, tab: str, headers: list[str]) -> bool:
        """Create the tab (and its header row) if missing. Returns True when usable."""
        doc = self._ensure_doc()
        if doc is None:
            return False
        ws = self._worksheet(tab)
        if ws is None:
            try:

                ws = doc.add_worksheet(title=tab, rows=200, cols=max(len(headers) + 2, 8))
                self._worksheets[tab] = ws
                self.last_error = None
            except Exception as exc:
                self.last_error = f"Cannot create tab '{tab}': {exc}"
                return False
        try:
            existing = [str(h).strip() for h in (ws.row_values(1) or [])]
        except Exception:
            existing = []
        if not any(existing):
            try:
                ws.update(values=[headers], range_name="A1")
            except Exception as exc:
                self.last_error = f"Cannot write headers to '{tab}': {exc}"
                return False
        self.invalidate_cache(tab)
        return True

    def append_row(self, tab: str, values: list, headers: list[str]) -> bool:
        if not self.ensure_tab(tab, headers):
            return False
        ws = self._worksheet(tab)
        try:
            ws.append_row([str(v) for v in values], value_input_option="USER_ENTERED")
        except Exception as exc:
            self.last_error = f"Append to '{tab}' failed: {exc}"
            return False
        self.invalidate_cache(tab)
        self.last_error = None
        return True

    def update_first_match(
        self,
        tab: str,
        predicate: Callable[[dict], bool],
        updates: dict[str, Any],
        headers: list[str] | None = None,
    ) -> bool:
        """Update columns of the first row whose record matches ``predicate``."""
        ws = self._worksheet(tab)
        if ws is None:
            if headers and self.ensure_tab(tab, headers):
                ws = self._worksheet(tab)
            if ws is None:
                return False
        try:
            values = ws.get_all_values()
        except Exception as exc:
            self.last_error = f"Read '{tab}' failed: {exc}"
            return False
        if len(values) < 2:
            return False
        header_row = [str(h).strip() for h in values[0]]
        for row_index, raw in enumerate(values[1:], start=2):
            record = {header_row[i]: (raw[i] if i < len(raw) else "") for i in range(len(header_row))}
            if predicate(record):
                for name, value in updates.items():
                    if name in header_row:
                        try:
                            ws.update_cell(row_index, header_row.index(name) + 1, str(value))
                        except Exception as exc:
                            self.last_error = f"Update '{tab}' failed: {exc}"
                            return False
                self.invalidate_cache(tab)
                self.last_error = None
                return True
        return False
