from datetime import timedelta

from conftest import FakeStore

from ayman_os_agent.scheduler import AppointmentManager
from ayman_os_agent.timeutils import now


def test_add_requires_valid_date(tmp_path):
    manager = AppointmentManager(store=FakeStore(writable=False), storage_path=str(tmp_path / "a.json"))
    assert "تاريخ غير صالح" in manager.add("مراجعة", "tomorrow")
    assert "وقت غير صالح" in manager.add("مراجعة", "2026-09-25", "25:99")


def test_json_fallback_roundtrip(tmp_path):
    path = str(tmp_path / "appts.json")
    manager = AppointmentManager(store=FakeStore(writable=False), storage_path=path)
    result = manager.add("مراجعة شبكات", "2026-09-25", "18:00", note="فصل 4")
    assert "تمت إضافة" in result
    listing = manager.list()
    assert "مراجعة شبكات" in listing and "2026-09-25" in listing
    assert manager.upcoming_items()[0]["title"] == "مراجعة شبكات"


def test_sheet_backed_storage(tmp_path):
    store = FakeStore(writable=True)
    manager = AppointmentManager(store=store, storage_path=str(tmp_path / "a.json"))
    manager.add("محاضرة", "2026-09-26", "10:00")
    assert store.appended[0][0] == "Appointments"
    assert manager.items()[0]["title"] == "محاضرة"


def test_due_items_finds_upcoming(tmp_path):
    soon = now() + timedelta(minutes=30)
    manager = AppointmentManager(store=FakeStore(writable=False), storage_path=str(tmp_path / "a.json"))
    manager.add("سكشن رياضيات", soon.date().isoformat(), soon.strftime("%H:%M"))
    due = manager.due_items(60)
    assert len(due) == 1
    assert due[0]["minutes_until"] <= 31
    assert manager.due_items(10) == []


def test_upcoming_filters_past(tmp_path):
    manager = AppointmentManager(store=FakeStore(writable=False), storage_path=str(tmp_path / "a.json"))
    manager.add("قديم", "2020-01-01", "09:00")
    manager.add("قادم", "2099-01-01", "09:00")
    titles = [item["title"] for item in manager.upcoming_items()]
    assert titles == ["قادم"]
