"""Central configuration for ayman-os-agent.

Rules:
- No secrets, real IDs, or real URLs may be hardcoded in this repository.
- Everything sensitive comes from environment variables (or a local .env file).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def load_dotenv(dotenv_path: Path | str | None = None) -> None:
    """Load key-value pairs from a .env file into os.environ if not already set."""
    if dotenv_path is not None:
        candidates = [Path(dotenv_path)]
    else:
        cwd = Path.cwd()
        pkg_dir = Path(__file__).resolve().parent.parent
        candidates = [cwd / ".env", pkg_dir / ".env"]

    for candidate in candidates:
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = val
                break
            except Exception:
                pass


# Automatically load .env if available
load_dotenv()


def _clean_str(value: str | None) -> str | None:
    if value is None:
        return None
    val = value.strip().strip('"\'')
    return val if val else None


def get_data_dir() -> Path:
    base_env = _clean_str(os.environ.get("AYMAN_DATA_DIR"))
    base = Path(base_env) if base_env else Path.home() / ".ayman-os-agent"
    base.mkdir(parents=True, exist_ok=True)
    return base


# ---------------------------------------------------------------- timezone

def get_timezone_name() -> str:
    """IANA timezone used for all scheduling and 'today' calculations."""
    return _clean_str(os.environ.get("TIMEZONE")) or "Asia/Riyadh"


# ---------------------------------------------------------------- schedule times

def _parse_clock(value: str | None, default: str) -> str:
    candidate = _clean_str(value) or default
    if _TIME_RE.match(candidate):
        hour, minute = candidate.split(":", 1)
        return f"{int(hour):02d}:{int(minute):02d}"
    return default


def get_daily_report_time() -> str:
    """Clock time (HH:MM) in the configured timezone for the daily parent report."""
    return _parse_clock(os.environ.get("DAILY_REPORT_TIME"), "21:00")


def get_evening_nudge_time() -> str:
    """Clock time for the 'you have not logged anything today' reminder."""
    return _parse_clock(os.environ.get("EVENING_NUDGE_TIME"), "20:00")


def get_reminder_minutes_before() -> int:
    """How many minutes before an appointment the reminder fires."""
    try:
        return max(5, int(_clean_str(os.environ.get("REMINDER_MINUTES_BEFORE")) or "60"))
    except ValueError:
        return 60


# ---------------------------------------------------------------- Google Sheets

def get_service_account_json() -> str | None:
    """Service-account credentials: raw JSON or Base64-encoded JSON."""
    return _clean_str(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))


def get_study_sheet_id() -> str | None:
    """Google Sheet ID (the long token in the sheet URL)."""
    return _clean_str(os.environ.get("GOOGLE_SHEET_ID"))


def get_study_sheet_url() -> str | None:
    """Optional public sheet URL (read-only XLSX fallback). No hardcoded default."""
    return _clean_str(os.environ.get("AYMAN_STUDY_SHEET_URL"))


def get_sheet_cache_ttl() -> int:
    try:
        return max(0, int(_clean_str(os.environ.get("SHEET_CACHE_TTL_SECONDS")) or "60"))
    except ValueError:
        return 60


def get_study_sheet_path() -> str | None:
    """Optional local XLSX path (offline / read-only fallback)."""
    return _clean_str(os.environ.get("AYMAN_STUDY_SHEET")) or _clean_str(os.environ.get("STUDY_SHEET_PATH"))


# ---------------------------------------------------------------- AI backends

def get_ai_backend() -> str:
    backend = _clean_str(os.environ.get("AI_BACKEND")) or "auto"
    return backend.lower()


def get_aws_config() -> dict:
    return {
        "region": _clean_str(os.environ.get("AWS_REGION")) or _clean_str(os.environ.get("AWS_DEFAULT_REGION")) or "us-east-1",
        "model_id": _clean_str(os.environ.get("AWS_BEDROCK_MODEL")) or "anthropic.claude-3-haiku-20240307-v1:0",
    }


def get_gemini_config() -> dict:
    return {
        "api_key": _clean_str(os.environ.get("GEMINI_API_KEY")) or _clean_str(os.environ.get("GOOGLE_API_KEY")),
        "model": _clean_str(os.environ.get("GEMINI_MODEL")) or "gemini-2.0-flash",
    }


# ---------------------------------------------------------------- Telegram

def get_telegram_token() -> str | None:
    return _clean_str(os.environ.get("TELEGRAM_BOT_TOKEN"))


def get_telegram_chat_ids() -> tuple[str, ...]:
    """Allowed chat/user IDs. Empty means DENY ALL (fail closed)."""
    configured = _clean_str(os.environ.get("TELEGRAM_CHAT_ID")) or ""
    ids = []
    for item in configured.split(","):
        cleaned = item.strip().strip('"\'')
        if cleaned:
            ids.append(cleaned)
    return tuple(ids)


def get_telegram_student_chat_id() -> str | None:
    """Optional: the student's own chat id (nudges go here instead of everyone)."""
    return _clean_str(os.environ.get("TELEGRAM_STUDENT_CHAT_ID"))


def get_telegram_max_response_chars() -> int:
    try:
        return max(500, int(_clean_str(os.environ.get("TELEGRAM_MAX_RESPONSE_CHARS")) or "1800"))
    except ValueError:
        return 1800


# ---------------------------------------------------------------- Email (optional)

def get_parent_email() -> str | None:
    return _clean_str(os.environ.get("PARENT_EMAIL"))


def get_primary_report_label() -> str:
    return _clean_str(os.environ.get("REPORT_LABEL")) or "تقرير اليوم"


def get_smtp_config() -> dict:
    port_str = _clean_str(os.environ.get("SMTP_PORT")) or "587"
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    user = _clean_str(os.environ.get("SMTP_USER"))
    from_email = _clean_str(os.environ.get("SMTP_FROM_EMAIL")) or user or "no-reply@example.com"

    return {
        "host": _clean_str(os.environ.get("SMTP_HOST")) or "smtp.gmail.com",
        "port": port,
        "user": user,
        "password": _clean_str(os.environ.get("SMTP_PASSWORD")),
        "from_email": from_email,
    }
