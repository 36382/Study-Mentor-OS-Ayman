import base64
import json

from ayman_os_agent import config
from ayman_os_agent.sheet_store import parse_service_account


def test_no_hardcoded_sheet_url(monkeypatch):
    monkeypatch.delenv("AYMAN_STUDY_SHEET_URL", raising=False)
    assert config.get_study_sheet_url() is None


def test_timezone_default_is_riyadh():
    assert config.get_timezone_name() == "Asia/Riyadh"


def test_daily_report_time_default_and_env(monkeypatch):
    assert config.get_daily_report_time() == "21:00"
    monkeypatch.setenv("DAILY_REPORT_TIME", "9:05")
    assert config.get_daily_report_time() == "09:05"
    monkeypatch.setenv("DAILY_REPORT_TIME", "99:99")
    assert config.get_daily_report_time() == "21:00"


def test_empty_chat_ids_means_deny():
    assert config.get_telegram_chat_ids() == ()


def test_parse_service_account_raw_json():
    creds = {"client_email": "sa@project.iam.gserviceaccount.com", "type": "service_account"}
    assert parse_service_account(json.dumps(creds)) == creds


def test_parse_service_account_base64():
    creds = {"client_email": "sa@project.iam.gserviceaccount.com", "type": "service_account"}
    encoded = base64.b64encode(json.dumps(creds).encode()).decode()
    assert parse_service_account(encoded) == creds


def test_parse_service_account_rejects_garbage():
    assert parse_service_account("not json at all") is None
    assert parse_service_account('{"nope": 1}') is None
    assert parse_service_account(None) is None
    assert parse_service_account("") is None
