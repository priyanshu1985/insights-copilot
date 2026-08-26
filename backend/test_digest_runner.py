import sys
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load environment variables BEFORE importing db or bot.scheduler
backend_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(backend_dir, ".env")
load_dotenv(env_path)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from bot.scheduler import weekly_digest, parse_date

class MockBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": text})
        print(f"\n[MOCK BOT MESSAGE SENT]\n  Chat ID: {chat_id}\n  Message: {text}\n")

class MockApp:
    def __init__(self):
        self.bot = MockBot()

async def run_tests():
    print("==========================================")
    print("RUNNING AUTOMATED TESTS FOR WEEKLY DIGEST")
    print("==========================================")

    # Test 1: Date Parser
    d = parse_date("2026-08-01T10:00:00.000+00:00")
    assert d is not None, "parse_date failed on ISO string"
    print("✅ Test 1 Passed: parse_date utility function works correctly.")

    # Test 2: Execution of weekly_digest with MockApp
    app = MockApp()
    print("\nExecuting weekly_digest(app)...")
    await weekly_digest(app)
    
    print("\n==========================================")
    print("TEST SUMMARY:")
    print(f"Total messages sent by bot: {len(app.bot.sent_messages)}")
    for i, msg in enumerate(app.bot.sent_messages, 1):
        print(f" Message {i}: {msg['text']}")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
