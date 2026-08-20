"""Scheduled messages management."""

import os
from datetime import datetime
from telethon import TelegramClient
from telethon.tl import functions, types


async def send_scheduled(client: TelegramClient, entity: str | int, message: str, schedule: datetime) -> dict:
    """Schedule a text message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message: Message text
        schedule: datetime when to send
    
    Returns:
        dict with scheduled message info
    """
    result = await client.send_message(entity, message, schedule=schedule)
    return {
        "scheduled": True,
        "id": result.id,
        "text": message,
        "scheduled_date": str(schedule),
    }


async def get_scheduled(client: TelegramClient, entity: str | int) -> list[dict]:
    """Get all scheduled messages in a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
    
    Returns:
        list of scheduled message dicts
    """
    result = await client(functions.messages.GetScheduledMessagesRequest(
        peer=entity,
        ids=[],
    ))
    messages = []
    for msg in result.messages:
        messages.append({
            "id": msg.id,
            "text": msg.message or "",
            "date": str(msg.date),
            "media": type(msg.media).__name__ if msg.media else None,
        })
    return messages


async def edit_scheduled(client: TelegramClient, entity: str | int, message_id: int, text: str) -> dict:
    """Edit a scheduled message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Scheduled message ID
        text: New message text
    
    Returns:
        dict with edit status
    """
    result = await client.edit_message(entity, message_id, text)
    return {"edited": True, "id": message_id, "text": text}


async def delete_scheduled(client: TelegramClient, entity: str | int, message_ids: list[int]) -> dict:
    """Delete scheduled messages.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_ids: List of scheduled message IDs to delete
    
    Returns:
        dict with deletion status
    """
    await client(functions.messages.DeleteScheduledMessagesRequest(
        peer=entity,
        ids=message_ids,
    ))
    return {"deleted": True, "ids": message_ids}
