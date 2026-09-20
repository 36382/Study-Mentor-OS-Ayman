from datetime import date, time

from ayman_os_agent.timeutils import combine, get_zone, now, parse_date, parse_time, today_iso


def test_parse_date_accepts_iso():
    assert parse_date("2026-09-25") == date(2026, 9, 25)


def test_parse_date_tolerates_single_digits():
    assert parse_date("2026-9-5") == date(2026, 9, 5)


def test_parse_date_rejects_garbage():
    assert parse_date("25/09/2026") is None
    assert parse_date("not-a-date") is None
    assert parse_date("") is None
    assert parse_date(None) is None


def test_parse_time():
    assert parse_time("09:05") == time(9, 5)
    assert parse_time("9:05") == time(9, 5)
    assert parse_time("9:5") is None
    assert parse_time("25:00") is None


def test_now_is_timezone_aware():
    current = now()
    assert current.tzinfo is not None
    assert str(current.tzinfo) == "Asia/Riyadh"


def test_today_iso_format():
    value = today_iso()
    assert len(value) == 10 and value[4] == "-" and value[7] == "-"


def test_combine():
    combined = combine("2026-09-25", "18:30")
    assert combined is not None
    assert (combined.year, combined.month, combined.day) == (2026, 9, 25)
    assert (combined.hour, combined.minute) == (18, 30)
    assert combined.tzinfo == get_zone()
