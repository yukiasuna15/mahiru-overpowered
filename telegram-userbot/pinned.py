"""Pin and unpin messages."""

from telethon import TelegramClient
from telethon.tl import functions


async def pin_message(client: TelegramClient, entity: str | int, message_id: int, notify: bool = False) -> dict:
    """Pin a message in a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID to pin
        notify: Whether to notify members
    
    Returns:
        dict with pin status
    """
    peer = await client.get_input_entity(entity)
    await client(functions.messages.UpdatePinnedMessageRequest(
        peer=peer,
        id=message_id,
        silent=not notify,
    ))
    return {"pinned": True, "message_id": message_id, "notified": notify}


async def unpin_message(client: TelegramClient, entity: str | int, message_id: int) -> dict:
    """Unpin a specific message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID to unpin
    
    Returns:
        dict with unpin status
    """
    peer = await client.get_input_entity(entity)
    await client(functions.messages.UpdatePinnedMessageRequest(
        peer=peer,
        id=message_id,
        unpin=True,
    ))
    return {"unpinned": True, "message_id": message_id}


async def get_pinned(client: TelegramClient, entity: str | int) -> list[dict]:
    """Get all pinned messages in a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
    
    Returns:
        list of pinned message dicts
    """
    peer = await client.get_input_entity(entity)
    result = await client(functions.messages.GetPinnedMessagesRequest(peer=peer))
    messages = []
    for msg in result.messages:
        messages.append({
            "id": msg.id,
            "text": msg.message or "",
            "date": str(msg.date),
        })
    return messages
