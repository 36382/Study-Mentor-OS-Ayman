from __future__ import annotations

import os
from pathlib import Path


def get_data_dir() -> Path:
    base = Path(os.environ.get("AYMAN_DATA_DIR", Path.home() / ".ayman-os-agent"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_aws_config() -> dict:
    return {
        "region": os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
        "model_id": os.environ.get("AWS_BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"),
    }


def get_gemini_config() -> dict:
    return {
        "api_key": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
        "model": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
    }


def get_ai_backend() -> str:
    return os.environ.get("AI_BACKEND", "auto").strip().lower()


def get_telegram_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None


def get_telegram_chat_ids() -> tuple[str, ...]:
    configured = os.environ.get("TELEGRAM_CHAT_ID", "")
    return tuple(chat_id.strip() for chat_id in configured.split(",") if chat_id.strip())


def get_parent_email() -> str | None:
    return os.environ.get("PARENT_EMAIL") or None


def get_study_sheet_path() -> str | None:
    return os.environ.get("AYMAN_STUDY_SHEET") or os.environ.get("STUDY_SHEET_PATH") or None


def get_primary_report_label() -> str:
    return os.environ.get("REPORT_LABEL", "تقرير اليوم")


def get_smtp_config() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST") or "smtp.gmail.com",
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "from_email": os.environ.get("SMTP_FROM_EMAIL", os.environ.get("SMTP_USER", "no-reply@example.com")),
    }
