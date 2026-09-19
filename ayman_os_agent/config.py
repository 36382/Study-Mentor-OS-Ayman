from __future__ import annotations

import os
from pathlib import Path


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


def get_ai_backend() -> str:
    backend = _clean_str(os.environ.get("AI_BACKEND")) or "auto"
    return backend.lower()


def get_telegram_token() -> str | None:
    return _clean_str(os.environ.get("TELEGRAM_BOT_TOKEN"))


def get_telegram_chat_ids() -> tuple[str, ...]:
    configured = _clean_str(os.environ.get("TELEGRAM_CHAT_ID")) or ""
    ids = []
    for item in configured.split(","):
        cleaned = item.strip().strip('"\'')
        if cleaned:
            ids.append(cleaned)
    return tuple(ids)


def get_telegram_max_response_chars() -> int:
    try:
        return max(500, int(_clean_str(os.environ.get("TELEGRAM_MAX_RESPONSE_CHARS")) or "1800"))
    except ValueError:
        return 1800


def get_parent_email() -> str | None:
    return _clean_str(os.environ.get("PARENT_EMAIL"))


def get_study_sheet_path() -> str | None:
    return _clean_str(os.environ.get("AYMAN_STUDY_SHEET")) or _clean_str(os.environ.get("STUDY_SHEET_PATH"))


def get_study_sheet_url() -> str | None:
    return _clean_str(os.environ.get("AYMAN_STUDY_SHEET_URL")) or "https://docs.google.com/spreadsheets/d/1g7NsctkNigecJVVewBgdQeO9PXPceejg702MW60kQvY/edit"


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
