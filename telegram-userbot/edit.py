"""Edit messages and media."""

import os
from telethon import TelegramClient


async def edit_message(client: TelegramClient, entity: str | int, message_id: int, text: str) -> dict:
    """Edit a text message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID to edit
        text: New message text
    
    Returns:
        dict with edited message info
    """
    result = await client.edit_message(entity, message_id, text)
    return {
        "edited": True,
        "id": result.id,
        "text": result.text,
        "date": str(result.date),
    }


async def edit_media(client: TelegramClient, entity: str | int, message_id: int, file_path: str, caption: str = "") -> dict:
    """Edit a message's media (photo, video, document).
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID to edit
        file_path: Path to new media file
        caption: Optional new caption
    
    Returns:
        dict with edited message info
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    result = await client.edit_message(entity, message_id, file=file_path, text=caption)
    return {
        "edited": True,
        "id": result.id,
        "media_type": type(result.media).__name__ if result.media else None,
        "file": os.path.basename(file_path),
    }
