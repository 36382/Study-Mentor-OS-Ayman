from conftest import FakeStore

from ayman_os_agent.reporting import ParentReportBuilder
from ayman_os_agent.scheduler import AppointmentManager
from ayman_os_agent.study_sheet import StudySheetManager
from ayman_os_agent.tasks import TaskManager
from ayman_os_agent.telegram_bot import AccessControl


def test_report_contains_sections(tmp_path):
    store = FakeStore(writable=True)
    report = ParentReportBuilder(
        scheduler=AppointmentManager(store=store, storage_path=str(tmp_path / "a.json")),
        study_sheet=StudySheetManager(store=store),
        tasks=TaskManager(store=store),
    ).build("تقرير الوالد")
    assert "تقرير الوالد" in report
    assert "المواعيد القادمة" in report
    assert "مهام مفتوحة" in report


def test_report_lists_open_tasks(tmp_path):
    store = FakeStore(
        tabs={"Tasks": {"headers": ["Task", "Course", "DueDate", "Status", "Notes"],
                        "rows": [["حل واجب الشبكات", "CS120", "2026-09-30", "pending", ""]]}}
    )
    report = ParentReportBuilder(
        scheduler=AppointmentManager(store=store, storage_path=str(tmp_path / "a.json")),
        study_sheet=StudySheetManager(store=store),
        tasks=TaskManager(store=store),
    ).build()
    assert "حل واجب الشبكات" in report


# ------------------------------------------------------------------ access control

def test_access_control_default_deny():
    control = AccessControl(())
    assert control.is_allowed(123, 456) is False


def test_access_control_allows_listed():
    control = AccessControl(("123", "456"))
    assert control.is_allowed(123, 999) is True
    assert control.is_allowed(999, 456) is True
    assert control.is_allowed(999, 888) is False
