from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List

from .config import get_data_dir


@dataclass
class Appointment:
    title: str
    date: str
    time: str
    note: str = ""


class AppointmentManager:
    def __init__(self, storage_path: str | None = None) -> None:
        base = Path(storage_path) if storage_path else get_data_dir() / "appointments.json"
        self.storage_path = base
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("[]", encoding="utf-8")

    def _read(self) -> List[dict]:
        try:
            raw = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write(self, items: List[dict]) -> None:
        self.storage_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, title: str, date: str, time: str = "09:00", note: str = "") -> str:
        items = self._read()
        items.append({
            "title": title,
            "date": date,
            "time": time,
            "note": note,
        })
        self._write(items)
        return f"تمت إضافة الموعد: {title} في {date} {time}"

    def list(self) -> str:
        items = self._read()
        if not items:
            return "لا توجد مواعيد مسجلة."
        lines = []
        for index, item in enumerate(items, start=1):
            lines.append(f"{index}. {item['title']} | {item['date']} {item['time']} | {item['note'] or 'لا يوجد ملاحظات'}")
        return "\n".join(lines)

    def upcoming(self) -> str:
        items = self._read()
        if not items:
            return "لا توجد مواعيد قادمة."
        today = datetime.now().date().isoformat()
        upcoming_items = [item for item in items if item["date"] >= today]
        if not upcoming_items:
            return "لا توجد مواعيد قادمة."
        lines = [f"- {item['title']} ({item['date']} {item['time']})" for item in upcoming_items]
        return "\n".join(lines)
