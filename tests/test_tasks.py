from conftest import FakeStore

from ayman_os_agent.tasks import TaskManager


def make_manager(writable=True, rows=None):
    tabs = {}
    if rows is not None:
        tabs["Tasks"] = {"headers": ["Task", "Course", "DueDate", "Status", "Notes"], "rows": rows}
    return TaskManager(store=FakeStore(tabs=tabs, writable=writable))


def test_add_task():
    manager = make_manager()
    assert "تمت إضافة" in manager.add("حل واجب الشبكات", course="CS120", due="2026-09-30")
    assert "واجب الشبكات" in manager.list()


def test_add_rejects_bad_due_date():
    manager = make_manager()
    assert "تاريخ استحقاق غير صالح" in manager.add("مهمة", due="الأحد")


def test_read_only_mode_is_graceful():
    manager = make_manager(writable=False)
    assert "وضع القراءة فقط" in manager.add("مهمة")
    assert "وضع القراءة فقط" in manager.mark_done("أي شيء")
    assert manager.items() == []


def test_mark_done_matches_fuzzy():
    manager = make_manager(rows=[["حل واجب الشبكات", "CS120", "", "pending", ""]])
    assert "تم إنجاز" in manager.mark_done("واجب")
    assert manager.store.tabs["Tasks"]["rows"][0][3] == "done"


def test_mark_done_ignores_already_done():
    manager = make_manager(rows=[["حل واجب", "CS120", "", "done", ""]])
    assert "لا توجد مهمة مفتوحة" in manager.mark_done("واجب")


def test_mark_done_ambiguous_lists_matches():
    manager = make_manager(rows=[
        ["حل واجب الشبكات", "CS120", "", "pending", ""],
        ["حل واجب الرياضيات", "MATH101", "", "pending", ""],
    ])
    result = manager.mark_done("واجب")
    assert "أكثر من مهمة" in result
