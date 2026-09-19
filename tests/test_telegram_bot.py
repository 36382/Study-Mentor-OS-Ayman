import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ayman_os_agent.telegram_bot import TelegramBotService


class TestTelegramBotService(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "123456:fake-token",
            "TELEGRAM_CHAT_ID": "111,222",
            "AI_BACKEND": "gemini",
            "GEMINI_API_KEY": "fake_key",
            "GEMINI_MODEL": "gemini-3.6-flash"
        })
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _create_mock_update(self, chat_id="111", user_id="111", text="hello"):
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.id = user_id
        update.effective_message.text = text
        update.effective_message.reply_text = AsyncMock()
        return update

    def test_is_allowed(self):
        bot = TelegramBotService()
        allowed_update = self._create_mock_update(chat_id="111")
        unauthorized_update = self._create_mock_update(chat_id="999", user_id="999")

        self.assertTrue(bot._is_allowed(allowed_update))
        self.assertFalse(bot._is_allowed(unauthorized_update))

    async def _async_test_start(self):
        bot = TelegramBotService()
        update = self._create_mock_update()
        context = MagicMock()
        await bot.start(update, context)
        update.effective_message.reply_text.assert_called_once()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("Ayman OS Agent", call_text)

    def test_start_command(self):
        import asyncio
        asyncio.run(self._async_test_start())

    async def _async_test_ai_command(self):
        bot = TelegramBotService()
        update = self._create_mock_update()
        context = MagicMock()
        context.args = ["explain", "recursion"]

        with patch.object(bot.agent.bedrock, "generate", return_value="Recursion explanation") as mock_gen:
            await bot.ai(update, context)
            mock_gen.assert_called_once_with("explain recursion", "أنت مساعد دراسي عملي. أجب بالعربية باختصار.")
            update.effective_message.reply_text.assert_called_once_with("Recursion explanation")

    def test_ai_command(self):
        import asyncio
        asyncio.run(self._async_test_ai_command())

    async def _async_test_unauthorized_user(self):
        bot = TelegramBotService()
        update = self._create_mock_update(chat_id="999", user_id="999")
        context = MagicMock()
        await bot.start(update, context)
        update.effective_message.reply_text.assert_called_once()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("غير مصرح لك", call_text)

    def test_unauthorized_access(self):
        import asyncio
        asyncio.run(self._async_test_unauthorized_user())

    async def _async_test_appt_command(self):
        bot = TelegramBotService()
        update = self._create_mock_update()
        context = MagicMock()
        context.args = ["math_exam", "2026-09-25", "10:00"]
        await bot.appt(update, context)
        update.effective_message.reply_text.assert_called_once()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("math_exam", call_text)

    def test_appt_command(self):
        import asyncio
        asyncio.run(self._async_test_appt_command())


    async def _async_test_setkey(self):
        bot = TelegramBotService()
        update = self._create_mock_update()
        context = MagicMock()
        context.args = ["test_live_key_123"]
        with patch.object(bot.agent.bedrock, "generate", return_value="Gemini OK"):
            await bot.setkey(update, context)
            update.effective_message.reply_text.assert_called_once()
            call_text = update.effective_message.reply_text.call_args[0][0]
            self.assertIn("تم تفعيل واختبار مفتاح Gemini بنجاح", call_text)

    def test_setkey_command(self):
        import asyncio
        asyncio.run(self._async_test_setkey())


if __name__ == "__main__":
    unittest.main()
