"""Appointments: stored in the Appointments tab of the study sheet.

Falls back to a local JSON file (legacy behaviour) when the sheet is not
writable, and auto-migrates legacy JSON data into the sheet on first run.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import get_data_dir
from .sheet_store import SheetStore
from .study_sheet import field
from .timeutils import combine, now, parse_date, parse_time

TAB = "Appointments"
HEADERS = ["Title", "Date", "Time", "Note", "CreatedAt"]


class AppointmentManager:
    def __init__(self, store: SheetStore | None = None, storage_path: str | None = None) -> None:
        self.store = store or SheetStore.from_env()
        self.storage_path = Path(storage_path) if storage_path else get_data_dir() / "appointments.json"
        self._migrate_legacy_if_needed()

    # ------------------------------------------------------------ storage

    def _sheet_enabled(self) -> bool:
        return self.store.is_writable()

    def _read_json(self) -> list[dict]:
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
        except Exception:
            return []

    def _write_json(self, items: list[dict]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def _migrate_legacy_if_needed(self) -> None:
        if not self._sheet_enabled() or not self.storage_path.exists():
            return
        legacy = self._read_json()
        if not legacy:
            return
        existing = self.store.get_records(TAB)
        if existing:
            return
        from .timeutils import today_iso

        for item in legacy:
            self.store.append_row(
                TAB,
                [item.get("title", ""), item.get("date", ""), item.get("time", "09:00"), item.get("note", ""), today_iso()],
                HEADERS,
            )
        try:
            self.storage_path.rename(self.storage_path.with_suffix(".json.migrated"))
        except OSError:
            pass

    def items(self) -> list[dict]:
        if self._sheet_enabled():
            records = self.store.get_records(TAB)
            return [
                {
                    "title": str(field(r, "title", "task", default="")),
                    "date": str(field(r, "date", "day", default="")),
                    "time": str(field(r, "time", "clock", default="09:00")) or "09:00",
                    "note": str(field(r, "note", "notes", default="")),
                }
                for r in records
            ]
        return self._read_json()

    # ------------------------------------------------------------ API

    def add(self, title: str, date: str, time: str = "09:00", note: str = "") -> str:
        title = str(title).strip()[:80]
        if not title:
            return "العنوان مطلوب."
        if parse_date(date) is None:
            return "تاريخ غير صالح. الصيغة: YYYY-MM-DD مثال 2026-09-25"
        parsed_time = parse_time(time)
        if parsed_time is None:
            return "وقت غير صالح. الصيغة: HH:MM مثال 09:00"
        time = parsed_time.strftime("%H:%M")

        if self._sheet_enabled():
            from .timeutils import today_iso

            ok = self.store.append_row(TAB, [title, parse_date(date).isoformat(), time, note.strip(), today_iso()], HEADERS)
            if not ok:
                return f"تعذر الحفظ في الشيت: {self.store.last_error}"
        else:
            items = self._read_json()
            items.append({"title": title, "date": parse_date(date).isoformat(), "time": time, "note": note.strip()})
            self._write_json(items)
        return f"تمت إضافة الموعد: {title} في {parse_date(date).isoformat()} {time}"

    def list(self) -> str:
        items = self.items()
        if not items:
            return "لا توجد مواعيد مسجلة."
        items.sort(key=lambda item: (str(item.get("date", "")), str(item.get("time", ""))))
        lines = []
        for index, item in enumerate(items, start=1):
            note = item.get("note") or "لا توجد ملاحظات"
            lines.append(f"{index}. {item['title']} | {item['date']} {item['time']} | {note}")
        return "\n".join(lines)

    def upcoming_items(self) -> list[dict]:
        today = now().date().isoformat()
        items = [item for item in self.items() if str(item.get("date", "")) >= today]
        items.sort(key=lambda item: (str(item.get("date", "")), str(item.get("time", ""))))
        return items

    def upcoming(self) -> str:
        items = self.upcoming_items()
        if not items:
            return "لا توجد مواعيد قادمة."
        return "\n".join(f"- {item['title']} ({item['date']} {item['time']})" for item in items)

    def due_items(self, within_minutes: int) -> list[dict]:
        """Appointments starting within the next ``within_minutes`` minutes."""
        current = now()
        due = []
        for item in self.upcoming_items():
            start = combine(item.get("date"), item.get("time"))
            if start is None:
                continue
            delta_minutes = (start - current).total_seconds() / 60
            if 0 <= delta_minutes <= within_minutes:
                item = dict(item)
                item["minutes_until"] = int(delta_minutes)
                due.append(item)
        return due
