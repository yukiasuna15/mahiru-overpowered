"""Media operations — upload, download, send photos/files."""

import os
from telethon import TelegramClient


async def send_file(client: TelegramClient, entity: str | int, file_path: str, caption: str = "") -> dict:
    """Send a file (photo, document, video, etc.) to a chat."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    result = await client.send_file(entity, file_path, caption=caption)
    return {
        "id": result.id,
        "date": str(result.date),
        "file": os.path.basename(file_path),
        "media_type": type(result.media).__name__ if result.media else None,
    }


async def send_photo(client: TelegramClient, entity: str | int, photo_path: str, caption: str = "") -> dict:
    """Send a photo to a chat."""
    return await send_file(client, entity, photo_path, caption)


async def download_media(client: TelegramClient, entity: str | int, message_id: int, save_path: str = "/tmp/") -> str:
    """Download media from a message."""
    msg = await client.get_messages(entity, ids=message_id)
    if not msg or not msg.media:
        raise ValueError("Message has no media")
    path = await client.download_media(msg, file=save_path)
    return path


async def send_voice(client: TelegramClient, entity: str | int, audio_path: str) -> dict:
    """Send a voice message (OGG/Opus format)."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"File not found: {audio_path}")
    result = await client.send_file(entity, audio_path, voice_note=True)
    return {
        "id": result.id,
        "date": str(result.date),
    }
