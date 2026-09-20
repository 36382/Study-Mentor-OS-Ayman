"""Send the daily parent report now: Telegram to all allowed chats (+ optional email)."""

from __future__ import annotations

from ayman_os_agent.agent import OSAgent
from ayman_os_agent.config import get_parent_email, get_telegram_chat_ids, get_telegram_token


def main() -> int:
    agent = OSAgent()
    report = agent.parent_report()

    token = get_telegram_token()
    chat_ids = get_telegram_chat_ids()
    if token and chat_ids:
        for chat_id in chat_ids:
            print(agent.alert_manager.send_telegram_message(report, chat_id))
    else:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID غير مضبوطين — تخطي إرسال تيليجرام.")

    parent_email = get_parent_email()
    if parent_email:
        print(agent.alert_manager.send_email(parent_email, "تقرير يومي من Study Mentor OS", report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
