import os
import unittest
from unittest.mock import MagicMock, patch

from ayman_os_agent.bedrock_service import BedrockService
from ayman_os_agent.config import get_gemini_config


class TestGeminiConfig(unittest.TestCase):
    def test_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = get_gemini_config()
            self.assertEqual(cfg["model"], "gemini-3.6-flash")

    def test_custom_model(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "custom-model"}):
            cfg = get_gemini_config()
            self.assertEqual(cfg["model"], "custom-model")

    def test_model_with_prefix(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "models/gemini-3.6-flash"}):
            cfg = get_gemini_config()
            self.assertEqual(cfg["model"], "gemini-3.6-flash")

    def test_generate_gemini_url(self):
        with patch.dict(os.environ, {"AI_BACKEND": "gemini", "GEMINI_API_KEY": "test_key", "GEMINI_MODEL": "gemini-3.6-flash"}):
            service = BedrockService()
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "Hello world"}]}}]}'
                mock_response.__enter__.return_value = mock_response
                mock_urlopen.return_value = mock_response

                result = service.generate("Say hello")
                self.assertEqual(result, "Hello world")

                req = mock_urlopen.call_args[0][0]
                self.assertIn("models/gemini-3.6-flash:generateContent?key=test_key", req.full_url)


if __name__ == "__main__":
    unittest.main()
