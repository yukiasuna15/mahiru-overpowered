"""Saved messages (cloud storage) operations."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def send_saved(client: TelegramClient, message: str, from_entity: str | int = None, from_message_id: int = None) -> dict:
    """Send a message to Saved Messages (your own chat).
    
    Args:
        client: Authenticated Telethon client
        message: Text message to save
        from_entity: Entity to forward from (with from_message_id)
        from_message_id: Message ID to forward to Saved Messages
    
    Returns:
        dict with saved message info
    """
    if from_entity and from_message_id:
        result = await client.forward_messages("me", from_message_id, from_entity)
        return {"forwarded": True, "ids": [m.id for m in result] if result else []}
    
    result = await client.send_message("me", message)
    return {"sent": True, "id": result.id, "text": result.text}


async def get_saved(client: TelegramClient, limit: int = 20) -> list[dict]:
    """Get messages from Saved Messages.
    
    Args:
        client: Authenticated Telethon client
        limit: Max messages to return
    
    Returns:
        list of message dicts
    """
    messages = []
    async for msg in client.iter_messages("me", limit=limit):
        messages.append({
            "id": msg.id,
            "text": msg.text or "",
            "date": str(msg.date),
            "media": type(msg.media).__name__ if msg.media else None,
            "is_forward": msg.forward is not None,
        })
    return messages
