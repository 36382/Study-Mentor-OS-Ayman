"""Timezone-aware helpers. All 'now/today' logic must go through here."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .config import get_timezone_name

_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def get_zone() -> ZoneInfo:
    try:
        return ZoneInfo(get_timezone_name())
    except Exception:
        return ZoneInfo("UTC")


def now() -> datetime:
    """Current time in the configured timezone (default Asia/Riyadh)."""
    return datetime.now(get_zone())


def today_iso() -> str:
    return now().date().isoformat()


def parse_date(value: object) -> date | None:
    """Parse YYYY-MM-DD (tolerant of single-digit month/day). Returns None on failure."""
    if value is None:
        return None
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date() if hasattr(value, "date") else None
    if hasattr(value, "year") and not isinstance(value, str):
        return date(value.year, value.month, value.day)
    match = _DATE_RE.match(str(value).strip())
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def parse_time(value: object) -> time | None:
    """Parse HH:MM (tolerant of single-digit hour). Returns None on failure."""
    if value is None:
        return None
    if hasattr(value, "hour") and not isinstance(value, str):
        return time(value.hour, getattr(value, "minute", 0))
    match = _TIME_RE.match(str(value).strip())
    if not match:
        return None
    try:
        return time(int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None


def combine(date_part: object, time_part: object):
    """Combine a date-like and time-like value into an aware datetime in the local zone."""
    parsed_date = parse_date(date_part)
    parsed_time = parse_time(time_part) or time(0, 0)
    if parsed_date is None:
        return None
    return datetime.combine(parsed_date, parsed_time, tzinfo=get_zone())


def format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")
