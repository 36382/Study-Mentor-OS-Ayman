from __future__ import annotations

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


class TelegramBotService:
    def __init__(self) -> None:
        self.token = get_telegram_token()
        self.allowed_chat_ids = get_telegram_chat_ids()
        self.agent = OSAgent()

    def is_available(self) -> bool:
        return bool(self.token) and ApplicationBuilder is not None and MessageHandler is not None

    def _is_allowed(self, update: "Update") -> bool:
        if not self.allowed_chat_ids or update.effective_chat is None:
            return True
        return str(update.effective_chat.id) in self.allowed_chat_ids

    async def _reply(self, update: "Update", text: str) -> None:
        if update.message is not None:
            await update.message.reply_text(text[:4000])

    async def start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            return
        await self._reply(update,
            "مرحباً! أنا وكيلي الشخصي.\n"
            "الأوامر: /status /list /report /sheet /risk /summary /ai /appt "
            "\nأو أرسل سؤالاً بسيطاً وسوف أحاول تنفيذه."
        )

    async def status(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if self._is_allowed(update):
            await self._reply(update, self.agent.status_summary())

    async def list(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            return
        path = context.args[0] if context.args else "."
        await self._reply(update, self.agent.list_directory(path))

    async def report(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if self._is_allowed(update):
            await self._reply(update, self.agent.parent_report())

    async def sheet(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if self._is_allowed(update):
            await self._reply(update, self.agent.study_sheet_summary())

    async def risk(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if self._is_allowed(update):
            await self._reply(update, self.agent.risk_summary())

    async def summary(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if self._is_allowed(update):
            await self._reply(update, self.agent.today_summary())

    async def ai(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update):
            return
        prompt = " ".join(context.args).strip()
        if not prompt:
            await self._reply(update, "استخدم: /ai اشرح لي كيف أنظم دراسة اليوم")
            return
        await self._reply(update, self.agent.bedrock.generate(prompt, "أنت مساعد دراسي عملي. أجب بالعربية باختصار."))

    async def message(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_allowed(update) or update.message is None or not update.message.text:
            return
        await self._reply(update, self.agent.execute(update.message.text))

    async def appt(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not context.args:
            await update.message.reply_text("استخدم: /appt مراجعة 2026-09-17 09:00")
            return
        try:
            title = context.args[0]
            date = context.args[1]
            time = context.args[2] if len(context.args) > 2 else "09:00"
            result = self.agent.scheduler.add(title, date, time)
            await update.message.reply_text(result)
        except Exception:
            await update.message.reply_text("صيغة خاطئة. مثال: /appt مراجعة 2026-09-17 09:00")

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
        return app

    def run(self) -> None:
        app = self.build_app()
        app.run_polling()


def main() -> None:
    service = TelegramBotService()
    if not service.is_available():
        print("Telegram bot is not configured. Set TELEGRAM_BOT_TOKEN before starting it.")
        return
    service.run()
