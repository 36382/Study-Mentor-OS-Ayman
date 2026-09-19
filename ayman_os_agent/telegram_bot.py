from __future__ import annotations

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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

from .agent import OSAgent
from .config import get_parent_email, get_telegram_chat_ids, get_telegram_token

logger = logging.getLogger("ayman_os_agent.telegram_bot")


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
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info("Health check server listening on port %d", port)
    except Exception as exc:
        logger.warning("Failed to start health check server on port %d: %s", port, exc)


class TelegramBotService:
    def __init__(self) -> None:
        self.token = get_telegram_token()
        self.allowed_chat_ids = get_telegram_chat_ids()
        self.agent = OSAgent()

    def is_available(self) -> bool:
        return bool(self.token) and ApplicationBuilder is not None and MessageHandler is not None

    def _is_allowed(self, update: "Update") -> bool:
        if not self.allowed_chat_ids:
            return True
        chat_id = str(update.effective_chat.id) if update.effective_chat else None
        user_id = str(update.effective_user.id) if update.effective_user else None
        allowed = (chat_id in self.allowed_chat_ids) or (user_id in self.allowed_chat_ids)
        if not allowed:
            logger.warning("Ignoring unauthorized Telegram chat_id=%s user_id=%s.", chat_id, user_id)
        return allowed

    async def _handle_unauthorized(self, update: "Update") -> None:
        chat_id = update.effective_chat.id if update.effective_chat else "Unknown"
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        logger.warning("Unauthorized access attempt: chat_id=%s, user_id=%s", chat_id, user_id)
        target = update.effective_message or update.message
        if target:
            await target.reply_text(
                f"⚠️ غير مصرح لك باستخدام هذا البوت.\n"
                f"معرف الدردشة الخاص بك (Chat ID): {chat_id}\n"
                f"معرف المستخدم الخاص بك (User ID): {user_id}\n\n"
                f"للسماح بالوصول، أضف هذا المعرف إلى متغير TELEGRAM_CHAT_ID في الإعدادات."
            )

    async def _reply(self, update: "Update", text: str) -> None:
        target = update.effective_message or update.message
        if target is not None:
            text = (text or "").strip()
            if not text:
                text = "لا توجد استجابة."
            if len(text) <= 4000:
                await target.reply_text(text)
            else:
                for i in range(0, len(text), 4000):
                    await target.reply_text(text[i : i + 4000])

    async def start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        await self._reply(
            update,
            "مرحباً بك! أنا Ayman OS Agent، مرشدك الدراسي الذكي.\n\n"
            "📌 الأوامر المتاحة:\n"
            "/summary - ملخص دراسة اليوم والتوصيات\n"
            "/risk - تقييم المخاطر والمواد ذات الأولوية\n"
            "/sheet - عرض ملخص جدول المذاكرة من Google Sheets\n"
            "/report - عرض تقرير المتابعة\n"
            "/sendreport - إرسال التقرير اليومي للوالد بالبريد\n"
            "/appt - عرض أو إضافة المواعيد\n"
            "/ai - التحدث مع المساعد الذكي\n"
            "/status - حالة النظام\n\n"
            "أو أرسل أي سؤال وسأقوم بالإجابة عليه مباشرة!",
        )

    async def status(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        await self._reply(update, self.agent.status_summary())

    async def list(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        path = context.args[0] if context.args else "."
        await self._reply(update, self.agent.list_directory(path))

    async def report(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        await self._reply(update, self.agent.parent_report())

    async def sendreport(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        await self._reply(update, "⏳ جاري إرسال التقرير اليومي...")
        report = self.agent.parent_report()
        parent_email = get_parent_email()
        results = []
        if parent_email:
            email_status = self.agent.send_alert(parent_email, "تقرير يومي من Ayman OS Agent", report)
            results.append(email_status)
        else:
            results.append("لم يتم ضبط PARENT_EMAIL لإرسال التقرير بالبريد.")
        await self._reply(update, "\n".join(results))

    async def sheet(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        await self._reply(update, self.agent.study_sheet_summary())

    async def risk(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        await self._reply(update, self.agent.risk_summary())

    async def summary(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        await self._reply(update, self.agent.today_summary())

    async def ai(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        prompt = " ".join(context.args).strip()
        if not prompt:
            await self._reply(update, "استخدم: /ai اشرح لي كيف أنظم دراسة اليوم")
            return
        await self._reply(
            update,
            self.agent.bedrock.generate(prompt, "أنت مساعد دراسي عملي. أجب بالعربية باختصار."),
        )

    async def message(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        if update.effective_message is None or not update.effective_message.text:
            return
        try:
            response = self.agent.execute(update.effective_message.text)
            await self._reply(update, response or "تم استلام رسالتك ولكن لم يتم إنتاج رد.")
        except Exception as exc:
            logger.error("Error executing agent command: %s", exc, exc_info=True)
            await self._reply(update, f"حدث خطأ أثناء معالجة الطلب: {exc}")

    async def appt(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            await self._handle_unauthorized(update)
            return
        if not context.args or context.args[0].lower() in {"list", "show", "عرض", "مواعيد"}:
            appointments = self.agent.list_appointments()
            await self._reply(
                update,
                f"📅 قائمة المواعيد:\n{appointments}\n\nلإضافة موعد جديد: /appt عنوان التاريخ الوقت\nمثال: /appt مراجعة 2026-09-17 09:00",
            )
            return
        if len(context.args) < 2:
            await self._reply(update, "صيغة غير مكتملة. مثال: /appt مراجعة 2026-09-17 09:00\nأو لعرض المواعيد: /appt list")
            return
        try:
            title = context.args[0]
            date = context.args[1]
            time = context.args[2] if len(context.args) > 2 else "09:00"
            result = self.agent.scheduler.add(title, date, time)
            await self._reply(update, result)
        except Exception as exc:
            await self._reply(update, f"صيغة خاطئة. مثال: /appt مراجعة 2026-09-17 09:00\n({exc})")

    async def _on_error(self, update: object, context: "ContextTypes.DEFAULT_TYPE") -> None:
        logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(f"⚠️ حدث خطأ في البوت: {context.error}")
            except Exception:
                pass

    async def _post_init(self, app) -> None:
        if BotCommand is not None:
            commands = [
                BotCommand("start", "بدء المحادثة والترحيب"),
                BotCommand("summary", "ملخص دراسة اليوم والتوصيات"),
                BotCommand("risk", "المواد ذات الأولوية والمخاطرة العالية"),
                BotCommand("sheet", "قراءة بيانات ورقة ومتابعة المذاكرة"),
                BotCommand("report", "عرض التقرير اليومي"),
                BotCommand("sendreport", "إرسال التقرير اليومي للوالد"),
                BotCommand("appt", "عرض أو إضافة المواعيد"),
                BotCommand("ai", "سؤال المساعد الذكي (Gemini/Bedrock)"),
                BotCommand("status", "حالة النظام والملفات"),
            ]
            try:
                await app.bot.set_my_commands(commands)
            except Exception as exc:
                logger.warning("Could not register bot commands: %s", exc)

    def build_app(self):
        if not self.is_available():
            if not self.token:
                raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")
            if _telegram_import_error is not None:
                raise RuntimeError("python-telegram-bot is unavailable.") from _telegram_import_error
            raise RuntimeError("Telegram bot dependencies are unavailable.")
        app = ApplicationBuilder().token(self.token).post_init(self._post_init).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("list", self.list))
        app.add_handler(CommandHandler("report", self.report))
        app.add_handler(CommandHandler("sendreport", self.sendreport))
        app.add_handler(CommandHandler("sheet", self.sheet))
        app.add_handler(CommandHandler("risk", self.risk))
        app.add_handler(CommandHandler("summary", self.summary))
        app.add_handler(CommandHandler("ai", self.ai))
        app.add_handler(CommandHandler("appt", self.appt))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message))
        app.add_error_handler(self._on_error)
        return app

    def run(self) -> None:
        start_health_server()
        app = self.build_app()
        logger.info("Telegram bot started polling...")
        app.run_polling()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    service = TelegramBotService()
    if not service.is_available():
        service.build_app()
    service.run()


if __name__ == "__main__":
    main()
