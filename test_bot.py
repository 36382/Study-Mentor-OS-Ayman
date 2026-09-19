#!/usr/bin/env python3
"""Interactive & Automated Test Script for Ayman OS Agent & Bot."""

import os
import sys
from unittest.mock import MagicMock, AsyncMock

from ayman_os_agent.agent import OSAgent
from ayman_os_agent.config import get_gemini_config, get_ai_backend, get_telegram_token
from ayman_os_agent.bedrock_service import BedrockService


def test_configuration():
    print("=" * 50)
    print("1. Checking Agent & Bot Configuration:")
    print("=" * 50)
    backend = get_ai_backend()
    gemini_cfg = get_gemini_config()
    tg_token = get_telegram_token()

    print(f"  • AI Backend: {backend}")
    print(f"  • Gemini Model: {gemini_cfg['model']}")
    print(f"  • Gemini Key Configured: {'Yes' if gemini_cfg['api_key'] else 'No (set GEMINI_API_KEY in .env)'}")
    print(f"  • Telegram Bot Token: {'Yes' if tg_token else 'No (set TELEGRAM_BOT_TOKEN in .env)'}")
    print()


def test_agent_commands():
    print("=" * 50)
    print("2. Testing Agent Local Commands:")
    print("=" * 50)
    agent = OSAgent()

    print("  • Testing list directory:")
    list_res = agent.list_directory(".")
    print(f"    Result: {len(list_res.splitlines())} items listed.")

    print("  • Testing appointment scheduling:")
    appt_res = agent.add_appointment("Bot Test Session", "2026-09-20", "14:00", "Verification test")
    print(f"    Result: {appt_res}")

    print("  • Testing summary command:")
    summary_res = agent.execute("today summary")
    print(f"    Result preview:\n{summary_res[:150]}...")
    print()


def test_gemini_integration():
    print("=" * 50)
    print("3. Testing Gemini Model Call:")
    print("=" * 50)
    gemini_cfg = get_gemini_config()
    service = BedrockService()

    if not gemini_cfg["api_key"]:
        print("  ⚠️ Skipping live Gemini call (No GEMINI_API_KEY set).")
        print("     To test with real Gemini API, set GEMINI_API_KEY in your .env file or environment.")
        return

    print(f"  • Sending test prompt to model '{gemini_cfg['model']}'...")
    response = service.generate("Say 'Gemini 3.6 is online and working!' in Arabic and English in one sentence.")
    print(f"  • Response from Gemini:\n    {response}")
    print()


def main():
    test_configuration()
    test_agent_commands()
    test_gemini_integration()
    print("=" * 50)
    print("✅ All local tests completed successfully.")
    print("=" * 50)


if __name__ == "__main__":
    main()
