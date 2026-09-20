import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

SENSITIVE_ENV_KEYS = [
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_SHEET_ID",
    "AYMAN_STUDY_SHEET_URL",
    "AYMAN_STUDY_SHEET",
    "STUDY_SHEET_PATH",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_STUDENT_CHAT_ID",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_PROFILE",
]


class FakeStore:
    """In-memory SheetStore double for tests."""

    def __init__(self, tabs: dict | None = None, writable: bool = True) -> None:
        self.tabs = tabs or {}
        self.writable = writable
        self.last_error = None
        self.last_sync_at = None
        self.sheet_url = None
        self.appended: list[tuple[str, list]] = []

    def is_configured(self) -> bool:
        return True

    def is_writable(self) -> bool:
        return self.writable

    def mode(self) -> str:
        return "sheets" if self.writable else "none"

    @staticmethod
    def _as_records(tab_data: dict) -> list[dict]:
        headers = tab_data["headers"]
        rows = []
        for row in tab_data["rows"]:
            padded = (list(row) + [""] * len(headers))[: len(headers)]
            rows.append(dict(zip(headers, padded)))
        return rows

    def get_records(self, tab: str, max_rows: int = 500) -> list[dict]:
        tab_data = self.tabs.get(tab)
        return self._as_records(tab_data) if tab_data else []

    def append_row(self, tab: str, values: list, headers: list) -> bool:
        if not self.writable:
            return False
        tab_data = self.tabs.setdefault(tab, {"headers": list(headers), "rows": []})
        tab_data["rows"].append([str(v) for v in values])
        self.appended.append((tab, list(values)))
        return True

    def update_first_match(self, tab: str, predicate, updates: dict, headers=None) -> bool:
        tab_data = self.tabs.get(tab)
        if not tab_data:
            return False
        headers_list = tab_data["headers"]
        for index, row in enumerate(tab_data["rows"]):
            record = dict(zip(headers_list, (list(row) + [""] * len(headers_list))[: len(headers_list)]))
            if predicate(record):
                new_row = (list(row) + [""] * len(headers_list))[: len(headers_list)]
                for name, value in updates.items():
                    if name in headers_list:
                        new_row[headers_list.index(name)] = str(value)
                tab_data["rows"][index] = new_row
                return True
        return False

    def ensure_tab(self, tab: str, headers: list) -> bool:
        return self.writable

    def invalidate_cache(self, tab=None) -> None:
        return None


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Isolate tests from the host environment and from real credentials."""
    for key in SENSITIVE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AYMAN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMEZONE", "Asia/Riyadh")
    yield
