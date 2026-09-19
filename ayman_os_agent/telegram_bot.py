from __future__ import annotations

import logging

try:
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
except Exception:  # pragma: no cover
    Update = None
    ApplicationBuilder = None
    CommandHandler = None
    ContextTypes = None
    MessageHandler = None
    filters = None

from .agent import OSAgent
from .config import get_telegram_chat_ids, get_telegram_token

logger = logging.getLogger("ayman_os_agent.telegram_bot")


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
        return (chat_id in self.allowed_chat_ids) or (user_id in self.allowed_chat_ids)

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
            "مرحباً! أنا وكيلي الشخصي.\n"
            "الأوامر: /status /list /report /sheet /risk /summary /ai /appt "
            "\nأو أرسل سؤالاً بسيطاً وسوف أحاول تنفيذه.",
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
        if not context.args:
            await self._reply(update, "استخدم: /appt مراجعة 2026-09-17 09:00")
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

    def build_app(self):
        if not self.is_available():
            raise RuntimeError("Telegram bot is not configured. Set TELEGRAM_BOT_TOKEN.")
        app = ApplicationBuilder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("list", self.list))
        app.add_handler(CommandHandler("report", self.report))
        app.add_handler(CommandHandler("sheet", self.sheet))
        app.add_handler(CommandHandler("risk", self.risk))
        app.add_handler(CommandHandler("summary", self.summary))
        app.add_handler(CommandHandler("ai", self.ai))
        app.add_handler(CommandHandler("appt", self.appt))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message))
        app.add_error_handler(self._on_error)
        return app

    def run(self) -> None:
        app = self.build_app()
        logger.info("Telegram bot started polling...")
        app.run_polling()


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    if ApplicationBuilder is None:
        print("Error: python-telegram-bot is not installed. Install it with: pip install python-telegram-bot")
        return
    token = get_telegram_token()
    if not token:
        print("Telegram bot is not configured. Set TELEGRAM_BOT_TOKEN before starting it.")
        return
    service = TelegramBotService()
    service.run()


if __name__ == "__main__":
    main()
