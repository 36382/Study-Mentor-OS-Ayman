import pytest

from ayman_os_agent.telegram_bot import TelegramBotService


def test_bot_service_constructs_safely_without_token():
    service = TelegramBotService()
    assert service.is_available() is False
    with pytest.raises(RuntimeError):
        service.build_app()


def test_job_daily_report_does_not_crash_without_token():
    """Scheduled jobs must never raise (they run in background threads)."""
    service = TelegramBotService()
    service.job_daily_report()
    service.job_evening_nudge()
    service.job_appointment_reminders()
