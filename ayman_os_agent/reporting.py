"""Parent-facing daily report, built purely from the sheet-backed managers."""

from __future__ import annotations

from .scheduler import AppointmentManager
from .study_sheet import StudySheetManager, field
from .tasks import TaskManager
from .timeutils import format_dt, now


class ParentReportBuilder:
    def __init__(
        self,
        scheduler: AppointmentManager | None = None,
        study_sheet: StudySheetManager | None = None,
        tasks: TaskManager | None = None,
    ) -> None:
        self.scheduler = scheduler or AppointmentManager()
        self.study_sheet = study_sheet or StudySheetManager()
        self.tasks = tasks or TaskManager()

    def build(self, title: str = "تقرير يومي") -> str:
        lines = [
            f"# {title}",
            f"**التاريخ:** {format_dt(now())}",
            "",
            "## إنجاز اليوم",
        ]

        if self.study_sheet.is_available():
            minutes = self.study_sheet.minutes_logged_today()
            lines.append(f"- دقائق المذاكرة اليوم: {minutes:g}" if minutes else "- لا توجد جلسات مسجلة اليوم.")
            top = self.study_sheet.top_risk_course()
            if top is not None:
                lines.append(
                    f"- أعلى مخاطرة: {field(top, 'code', 'key', default='-')} ({field(top, 'name', default='-')}) "
                    f"| Risk={field(top, 'risk', default='-')}"
                )
        else:
            lines.append("- ورقة الدراسة غير متصلة حالياً.")

        lines.extend(["", "## المواعيد القادمة", self.scheduler.upcoming()])

        try:
            open_tasks = self.tasks.open_items()
        except Exception:
            open_tasks = []
        lines.extend(["", f"## مهام مفتوحة ({len(open_tasks)})"])
        if open_tasks:
            for item in open_tasks[:5]:
                due = f" — تسليم {item['due']}" if item["due"] else ""
                lines.append(f"- ⬜ {item['task']}{due}")
        else:
            lines.append("- لا توجد مهام مفتوحة. 🎉")

        lines.extend(
            [
                "",
                "---",
                "أُرسل تلقائياً من Study Mentor OS Agent 🤖",
            ]
        )
        return "\n".join(lines)
