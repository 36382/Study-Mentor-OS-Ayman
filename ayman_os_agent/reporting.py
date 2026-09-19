from __future__ import annotations

from datetime import datetime

from .scheduler import AppointmentManager
from .study_sheet import StudySheetManager


class ParentReportBuilder:
    def __init__(self, scheduler: AppointmentManager | None = None, study_sheet: StudySheetManager | None = None) -> None:
        self.scheduler = scheduler or AppointmentManager()
        self.study_sheet = study_sheet or StudySheetManager()

    def build(self, title: str = "تقرير يومي") -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        appointments = self.scheduler.upcoming()
        report = f"# {title}\n\n**تاريخ التقرير:** {now}\n\n## المواعيد القادمة\n{appointments}\n\n## ملخص\n- تم تجهيز التقرير بشكل تلقائي.\n- يمكن متابعة المهام والتنبيهات من خلال الوكيل.\n"
        if self.study_sheet.is_available():
            report += "\n## مؤشرات ورقة الدراسة\n" + self.study_sheet.summary() + "\n"
        return report
