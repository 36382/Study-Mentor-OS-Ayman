"""Study tasks: stored in the Tasks tab of the study sheet."""

from __future__ import annotations

from .sheet_store import SheetStore
from .study_sheet import field
from .timeutils import parse_date, today_iso

TAB = "Tasks"
HEADERS = ["Task", "Course", "DueDate", "Status", "Notes"]


class TaskManager:
    def __init__(self, store: SheetStore | None = None) -> None:
        self.store = store or SheetStore.from_env()

    # ------------------------------------------------------------ helpers

    def _task_name(self, record: dict) -> str:
        return str(field(record, "task", "title", "name", "المهمة", default="")).strip()

    def _status(self, record: dict) -> str:
        return str(field(record, "status", "الحالة", default="pending")).strip().lower()

    # ------------------------------------------------------------ API

    def items(self) -> list[dict]:
        if not self.store.is_writable():
            return []
        return [
            {
                "task": self._task_name(r),
                "course": str(field(r, "course", "code", default="")),
                "due": str(field(r, "duedate", "due_date", "due", default="")),
                "status": self._status(r),
                "notes": str(field(r, "notes", "note", default="")),
            }
            for r in self.store.get_records(TAB)
            if self._task_name(r)
        ]

    def open_items(self) -> list[dict]:
        return [item for item in self.items() if item["status"] not in {"done", "تمت", "منجزة", "منجزه"}]

    def add(self, task: str, course: str = "", due: str = "", notes: str = "") -> str:
        task = str(task).strip()[:120]
        if not task:
            return "اسم المهمة مطلوب."
        if not self.store.is_writable():
            return "وضع القراءة فقط: لا يمكن إضافة مهام بدون اتصال الكتابة بالشيت (GOOGLE_SERVICE_ACCOUNT_JSON)."
        if due and parse_date(due) is None:
            return "تاريخ استحقاق غير صالح. الصيغة: YYYY-MM-DD"
        ok = self.store.append_row(TAB, [task, course.strip(), parse_date(due).isoformat() if due else "", "pending", notes.strip()], HEADERS)
        if not ok:
            return f"تعذر الحفظ في الشيت: {self.store.last_error}"
        return f"تمت إضافة المهمة: {task}" + (f" (تسليم {due})" if due else "")

    def mark_done(self, query: str) -> str:
        query = str(query).strip().lower()
        if not query:
            return "حدد المهمة المطلوب إنجازها."
        if not self.store.is_writable():
            return "وضع القراءة فقط: لا يمكن تحديث المهام بدون اتصال الكتابة بالشيت."
        matches = [item for item in self.open_items() if query in item["task"].lower()]
        if not matches:
            return f"لا توجد مهمة مفتوحة تطابق: {query}"
        if len(matches) > 1:
            options = "، ".join(item["task"] for item in matches[:4])
            return f"تطابق أكثر من مهمة. حدد بدقة أكبر: {options}"
        target = matches[0]
        ok = self.store.update_first_match(
            TAB,
            lambda record: self._task_name(record).strip().lower() == target["task"].lower(),
            {"Status": "done", "DoneAt": today_iso()},
            headers=HEADERS,
        )
        if not ok:
            return f"تعذر التحديث في الشيت: {self.store.last_error}"
        return f"أحسنت! تم إنجاز: {target['task']}"

    def list(self, include_done: bool = False) -> str:
        items = self.items() if include_done else self.open_items()
        if not items:
            return "لا توجد مهام مفتوحة. 🎉"
        lines = []
        for index, item in enumerate(items, start=1):
            suffix = []
            if item["course"]:
                suffix.append(item["course"])
            if item["due"]:
                suffix.append(f"تسليم {item['due']}")
            status = "✅" if item["status"] in {"done", "تمت", "منجزة", "منجزه"} else "⬜"
            tail = f" ({'، '.join(suffix)})" if suffix else ""
            lines.append(f"{status} {index}. {item['task']}{tail}")
        return "\n".join(lines)
