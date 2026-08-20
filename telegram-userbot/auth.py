"""Telegram userbot authentication via Telethon."""

import os
from telethon import TelegramClient

API_ID = int(os.environ.get("TELEGRAM_API_ID", "27677578"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "a04f56ffb88b75b00d7d6f5cf44d5da8")
SESSION_PATH = os.path.expanduser("~/.hermes/credentials/telegram-userbot.session")

_client = None


async def get_client() -> TelegramClient:
    """Get authenticated Telethon client. Reuses connection if possible."""
    global _client
    if _client is None:
        _client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    if not _client.is_connected():
        await _client.connect()
    if not await _client.is_user_authorized():
        raise RuntimeError("Telegram session not authorized. Run login.py first.")
    return _client
