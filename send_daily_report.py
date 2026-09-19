from __future__ import annotations

import os
from datetime import datetime

from ayman_os_agent.agent import OSAgent
from ayman_os_agent.config import get_parent_email, get_telegram_chat_ids, get_telegram_token
from ayman_os_agent.notifications import AlertManager


def main() -> int:
    agent = OSAgent()
    report = agent.parent_report()
    parent_email = get_parent_email()

    if parent_email:
        status = agent.send_alert(
            parent_email,
            "تقرير يومي من Ayman OS Agent",
            report,
        )
        print(status)

    chat_ids = get_telegram_chat_ids()
    token = get_telegram_token()
    if token and chat_ids:
        notifier = AlertManager()
        for chat_id in chat_ids:
            print(notifier.send_telegram_message(report, chat_id))

    print(f"Report generated at {datetime.now().isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
