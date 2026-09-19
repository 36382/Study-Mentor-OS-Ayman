from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText
from urllib import request, error

from .config import get_smtp_config, get_telegram_chat_ids, get_telegram_token


class AlertManager:
    def __init__(self) -> None:
        self.smtp = get_smtp_config()
        self.telegram_token = get_telegram_token()
        self.telegram_chat_ids = get_telegram_chat_ids()

    def send_email(self, to_email: str, subject: str, body: str) -> str:
        if not self.smtp["host"] or not self.smtp["user"] or not self.smtp["password"]:
            return "لم يتم إعداد SMTP. أضف SMTP_HOST و SMTP_USER و SMTP_PASSWORD لإرسال الإشعارات بالبريد."

        message = MIMEText(body, "plain", "utf-8")
        message["Subject"] = subject
        message["From"] = self.smtp["from_email"]
        message["To"] = to_email

        try:
            with smtplib.SMTP(self.smtp["host"], self.smtp["port"]) as server:
                server.starttls()
                server.login(self.smtp["user"], self.smtp["password"])
                server.send_message(message)
            return f"تم إرسال الإشعار إلى {to_email}."
        except Exception as exc:
            return f"فشل إرسال البريد: {exc}"

    def send_telegram_message(self, text: str, chat_id: str | None = None) -> str:
        token = self.telegram_token
        target_chat = chat_id or (self.telegram_chat_ids[0] if self.telegram_chat_ids else None)
        if not token or not target_chat:
            return "لم يتم إعداد Telegram bot token أو chat_id لإرسال الرسائل."

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": target_chat, "text": text, "parse_mode": "HTML"}).encode("utf-8")
        req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            if result.get("ok"):
                return "تم إرسال الرسالة إلى Telegram."
            return f"فشل إرسال رسالة Telegram: {result}"
        except error.HTTPError as exc:
            return f"فشل إرسال رسالة Telegram: {exc.read().decode('utf-8', errors='replace')}"
        except Exception as exc:  # pragma: no cover
            return f"فشل إرسال رسالة Telegram: {exc}"
