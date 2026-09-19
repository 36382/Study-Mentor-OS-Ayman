import os
import unittest
from unittest.mock import patch

from ayman_os_agent.agent import OSAgent


class TestOSAgent(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.dict(os.environ, {
            "AI_BACKEND": "gemini",
            "GEMINI_API_KEY": "fake_key",
            "GEMINI_MODEL": "gemini-3.6-flash"
        })
        self.patcher.start()
        self.agent = OSAgent()

    def tearDown(self):
        self.patcher.stop()

    def test_list_directory(self):
        output = self.agent.list_directory(".")
        self.assertIn("README.md", output)

    def test_read_file(self):
        content = self.agent.read_file("pyproject.toml")
        self.assertIn("ayman-os-agent", content)

    def test_appointment_management(self):
        result = self.agent.add_appointment("Study Math", "2026-09-30", "15:00", "Final review")
        self.assertIn("Study Math", result)
        appointments = self.agent.list_appointments()
        self.assertIn("Study Math", appointments)

    def test_execute_ai_routing(self):
        with patch.object(self.agent.bedrock, "generate", return_value="AI Response Test") as mock_gen:
            res = self.agent.execute("ai what is python?")
            self.assertEqual(res, "AI Response Test")
            mock_gen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
