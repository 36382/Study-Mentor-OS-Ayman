"""Telegram front-end: commands + free-form AI mentor + internal scheduler.

Security:
- Default-deny: if TELEGRAM_CHAT_ID is empty, nobody can use the bot.
- Free-form text goes through the AI tool-use loop (safe, whitelisted tools).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from .config import (
    get_daily_report_time,
    get_evening_nudge_time,
    get_reminder_minutes_before,
    get_telegram_chat_ids,
    get_telegram_max_response_chars,
    get_telegram_student_chat_id,
    get_telegram_token,
)
from .timeutils import get_zone

logger = logging.getLogger("ayman_os_agent.telegram_bot")

_telegram_import_error: Exception | None = None

try:
    from telegram import BotCommand, Update
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
except ImportError as exc:  # pragma: no cover
    _telegram_import_error = exc
    BotCommand = None
    Update = None
    ApplicationBuilder = None
    CommandHandler = None
    ContextTypes = None
    MessageHandler = None
    filters = None


# ---------------------------------------------------------------- health server

def start_health_server() -> None:
    """Run a minimal HTTP health check server if PORT is assigned by a cloud host."""
    port_str = os.environ.get("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
    except ValueError:
        return

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","bot":"running"}\n')

        def log_message(self, format, *args):
            pass

    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("Health check server listening on port %d", port)
    except Exception as exc:
        logger.warning("Failed to start health check server on port %d: %s", port, exc)


# ---------------------------------------------------------------- access control

class AccessControl:
    """Fail-closed authorization against TELEGRAM_CHAT_ID."""

    def __init__(self, allowed: tuple[str, ...]) -> None:
        self.allowed = {str(item).strip() for item in allowed if str(item).strip()}

    def is_allowed(self, chat_id: object, user_id: object) -> bool:
        if not self.allowed:
            return False  # default-deny
        return str(chat_id) in self.allowed or str(user_id) in self.allowed


# ---------------------------------------------------------------- bot service

class TelegramBotService:
    def __init__(self) -> None:
        self.token = get_telegram_token()
        self.max_response_chars = get_telegram_max_response_chars()
        self.allowed_chat_ids = get_telegram_chat_ids()
        self.access = AccessControl(self.allowed_chat_ids)
        self.started_at = time.time()
        self._reminded: set[str] = set()

        from .agent import OSAgent

        self.agent = OSAgent()
        self.notifier = self.agent.alert_manager

    def is_available(self) -> bool:
        return bool(self.token) and ApplicationBuilder is not None and MessageHandler is not None

    # ------------------------------------------------------------ replies

    async def _reply(self, update: "Update", text: str) -> None:
        target = update.effective_message or update.message
        if target is None:
            return
        text = "\n".join(" ".join(line.split()) for line in (text or "").splitlines() if line.strip())
        if not text:
            text = "لا توجد استجابة."
        if len(text) > self.max_response_chars:
            text = text[: self.max_response_chars - 24].rsplit(" ", 1)[0] + "\n… (تم اختصار الرد)"
        await target.reply_text(text)

    def _check(self, update: "Update") -> bool:
        chat_id = update.effective_chat.id if update.effective_chat else None
        user_id = update.effective_user.id if update.effective_user else None
        if self.access.is_allowed(chat_id, user_id):
            return True
        logger.warning("Unauthorized access attempt: chat_id=%s user_id=%s", chat_id, user_id)
        return False

    async def _deny(self, update: "Update") -> None:
        chat_id = update.effective_chat.id if update.effective_chat else "?"
        user_id = update.effective_user.id if update.effective_user else "?"
        await self._reply(
            update,
            "⚠️ غير مصرح لك باستخدام هذا البوت.\n"
            f"Chat ID: {chat_id}\nUser ID: {user_id}\n\n"
            "أضف هذا المعرف إلى TELEGRAM_CHAT_ID في إعدادات النشر.",
        )

    # ------------------------------------------------------------ commands

    async def start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        await self._reply(
            update,
            "مرحباً! أنا مرشدك الدراسي في Study Mentor OS 📚\n\n"
            "الأوامر: /summary /risk /log /tasks /done /appt /report /sendreport /ai /status\n"
            "أو اكتب بحرية: «ذاكرت ساعة CS120» وسأسجلها.",
        )

    async def summary(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        await self._reply(update, self.agent.today_summary())

    async def risk(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        await self._reply(update, self.agent.risk_summary())

    async def sheet(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        await self._reply(update, self.agent.study_sheet_summary())

    async def report(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        await self._reply(update, self.agent.parent_report())

    async def sendreport(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        await self._reply(update, "⏳ جاري إرسال التقرير...")
        await self._reply(update, self.agent.send_parent_report_now())

    async def log(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        args = context.args or []
        if len(args) < 2:
            await self._reply(update, "الصيغة: /log <رمز المادة> <الدقائق> [ملاحظة]\nمثال: /log CS120 45 راجعت الفصل 3")
            return
        try:
            minutes = int(float(args[1]))
        except ValueError:
            await self._reply(update, "الدقائق يجب أن تكون رقماً. مثال: /log CS120 45")
            return
        note = " ".join(args[2:])
        await self._reply(update, self.agent.log_study(args[0], minutes, note))

    async def tasks(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        await self._reply(update, self.agent.tasks_overview())

    async def done(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        query = " ".join(context.args or []).strip()
        if not query:
            await self._reply(update, "الصيغة: /done <جزء من اسم المهمة>")
            return
        await self._reply(update, self.agent.complete_task(query))

    async def appt(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        args = context.args or []
        if not args or args[0].lower() in {"list", "show", "عرض", "مواعيد"}:
            await self._reply(
                update,
                f"📅 المواعيد القادمة:\n{self.agent.list_appointments()}\n\n"
                "لإضافة موعد: /appt عنوان | 2026-09-25 | 09:00",
            )
            return
        parts = [part.strip() for part in " ".join(args).split("|") if part.strip()]
        if len(parts) < 2:
            await self._reply(update, "الصيغة: /appt عنوان | YYYY-MM-DD | HH:MM\nمثال: /appt مراجعة شبكات | 2026-09-25 | 18:00")
            return
        title, date_value = parts[0], parts[1]
        time_value = parts[2] if len(parts) > 2 else "09:00"
        note = parts[3] if len(parts) > 3 else ""
        await self._reply(update, self.agent.add_appointment(title, date_value, time_value, note))

    async def ai(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        prompt = " ".join(context.args or []).strip()
        if not prompt:
            await self._reply(update, "استخدم: /ai كيف أنظم مذاكرة اليوم؟")
            return
        chat_key = str(update.effective_chat.id) if update.effective_chat else "default"
        await self._reply(update, self.agent.ai_turn(prompt, chat_key))

    async def status(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        lines = [self.agent.status_summary(), ""]
        uptime = int((time.time() - self.started_at) / 60)
        lines.append(f"مدة التشغيل: {uptime} دقيقة")
        scheduler = getattr(self, "_scheduler", None)
        if scheduler is not None:
            jobs = scheduler.get_jobs()
            if jobs:
                next_runs = "\n".join(
                    f"- {job.name}: التشغيل القادم {job.next_run_time.strftime('%Y-%m-%d %H:%M') if job.next_run_time else '-'}"
                    for job in jobs
                )
                lines.append("مهام مجدولة:")
                lines.append(next_runs)
        await self._reply(update, "\n".join(lines))

    # ------------------------------------------------------------ free text

    async def message(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._check(update):
            await self._deny(update)
            return
        if update.effective_message is None or not update.effective_message.text:
            return
        chat_key = str(update.effective_chat.id) if update.effective_chat else "default"
        try:
            response = self.agent.ai_turn(update.effective_message.text, chat_key)
            await self._reply(update, response or "تم استلام رسالتك.")
        except Exception as exc:
            logger.error("Error handling message: %s", exc, exc_info=True)
            await self._reply(update, f"حدث خطأ أثناء معالجة الطلب: {exc}")

    async def _on_error(self, update: object, context: "ContextTypes.DEFAULT_TYPE") -> None:
        logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text("⚠️ حدث خطأ في البوت.")
            except Exception:
                pass

    # ------------------------------------------------------------ scheduled jobs (sync, own thread)

    def _target_chats(self) -> list[str]:
        student = get_telegram_student_chat_id()
        if student:
            return [student]
        return list(self.allowed_chat_ids)

    def job_daily_report(self) -> None:
        try:
            report = self.agent.parent_report()
            for chat_id in self.allowed_chat_ids:
                status = self.notifier.send_telegram_message(report, chat_id)
                logger.info("Daily report to %s: %s", chat_id, status)
        except Exception as exc:
            logger.error("Daily report job failed: %s", exc, exc_info=True)

    def job_evening_nudge(self) -> None:
        try:
            minutes = self.agent.study_sheet.minutes_logged_today()
            if minutes > 0:
                return
            message = (
                "🌙 ملاحظة لطيفة: لم تسجل أي جلسة مذاكرة اليوم.\n"
                "حتى 25 دقيقة تصنع فرقاً. سجل فور انتهائك: /log CS120 25"
            )
            for chat_id in self._target_chats():
                self.notifier.send_telegram_message(message, chat_id)
        except Exception as exc:
            logger.error("Evening nudge job failed: %s", exc, exc_info=True)

    def job_appointment_reminders(self) -> None:
        try:
            within = get_reminder_minutes_before()
            for item in self.agent.scheduler.due_items(within):
                key = f"{item['date']}T{item['time']}|{item['title']}"
                if key in self._reminded:
                    continue
                self._reminded.add(key)
                message = f"⏰ تذكير: «{item['title']}» بعد {item.get('minutes_until', '?')} دقيقة."
                for chat_id in self._target_chats():
                    self.notifier.send_telegram_message(message, chat_id)
        except Exception as exc:
            logger.error("Reminder job failed: %s", exc, exc_info=True)

    def start_scheduler(self) -> None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            logger.warning("APScheduler not installed; scheduled jobs disabled.")
            return

        zone = get_zone()
        scheduler = BackgroundScheduler(timezone=zone)

        hour, minute = (int(part) for part in get_daily_report_time().split(":"))
        scheduler.add_job(self.job_daily_report, "cron", hour=hour, minute=minute, id="daily_report", name="التقرير اليومي")

        nudge_hour, nudge_minute = (int(part) for part in get_evening_nudge_time().split(":"))
        scheduler.add_job(self.job_evening_nudge, "cron", hour=nudge_hour, minute=nudge_minute, id="evening_nudge", name="تذكير المساء")

        scheduler.add_job(
            self.job_appointment_reminders,
            "interval",
            minutes=5,
            id="appt_reminders",
            name="تذكير المواعيد",
            next_run_time=datetime.now(zone) + timedelta(seconds=20),
        )

        scheduler.start()
        self._scheduler = scheduler
        logger.info("Scheduler started (timezone=%s)", zone)

    # ------------------------------------------------------------ wiring

    async def _post_init(self, app) -> None:
        if BotCommand is not None:
            commands = [
                BotCommand("start", "الترحيب والتعليمات"),
                BotCommand("summary", "ملخص اليوم"),
                BotCommand("risk", "المواد الأخطر"),
                BotCommand("log", "تسجيل جلسة: /log CS120 45"),
                BotCommand("tasks", "المهام المفتوحة"),
                BotCommand("done", "إنجاز مهمة: /done اسم"),
                BotCommand("appt", "المواعيد: عرض أو إضافة"),
                BotCommand("report", "معاينة تقرير الوالد"),
                BotCommand("sendreport", "إرسال التقرير للوالد الآن"),
                BotCommand("ai", "سؤال المرشد الذكي"),
                BotCommand("status", "حالة النظام"),
            ]
            try:
                await app.bot.set_my_commands(commands)
            except Exception as exc:
                logger.warning("Could not register bot commands: %s", exc)

    def build_app(self):
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
        if ApplicationBuilder is None:
            raise RuntimeError("python-telegram-bot is unavailable.") from _telegram_import_error

        app = ApplicationBuilder().token(self.token).post_init(self._post_init).build()
        for name, handler in [
            ("start", self.start),
            ("summary", self.summary),
            ("risk", self.risk),
            ("log", self.log),
            ("tasks", self.tasks),
            ("done", self.done),
            ("appt", self.appt),
            ("report", self.report),
            ("sendreport", self.sendreport),
            ("ai", self.ai),
            ("status", self.status),
        ]:
            app.add_handler(CommandHandler(name, handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message))
        app.add_error_handler(self._on_error)
        return app

    def run(self) -> None:
        start_health_server()
        if not self.allowed_chat_ids:
            logger.warning(
                "TELEGRAM_CHAT_ID is empty — the bot will REJECT every user (default-deny). "
                "Set it to your chat IDs to enable access."
            )
        self.start_scheduler()
        app = self.build_app()
        logger.info("Telegram bot started polling...")
        app.run_polling()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    service = TelegramBotService()
    service.run()


if __name__ == "__main__":
    main()
