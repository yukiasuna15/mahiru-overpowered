"""Search messages in chats and globally."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def search_messages(client: TelegramClient, entity: str | int, query: str, limit: int = 20) -> list[dict]:
    """Search messages in a specific chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity to search in
        query: Search query string
        limit: Max results to return
    
    Returns:
        list of message dicts
    """
    results = []
    async for msg in client.iter_messages(entity, limit=limit, search=query):
        sender = await msg.get_sender()
        sender_name = "Unknown"
        if sender:
            if hasattr(sender, "first_name"):
                sender_name = (sender.first_name or "") + (" " + sender.last_name if sender.last_name else "")
            elif hasattr(sender, "title"):
                sender_name = sender.title
        results.append({
            "id": msg.id,
            "text": msg.text or "",
            "date": str(msg.date),
            "sender": sender_name.strip(),
            "chat_id": msg.peer_id.channel_id if hasattr(msg.peer_id, "channel_id") else
                        msg.peer_id.chat_id if hasattr(msg.peer_id, "chat_id") else
                        msg.peer_id.user_id if hasattr(msg.peer_id, "user_id") else None,
        })
    return results


async def search_global(client: TelegramClient, query: str, limit: int = 20) -> list[dict]:
    """Search messages across all chats globally.
    
    Args:
        client: Authenticated Telethon client
        query: Search query string
        limit: Max results to return
    
    Returns:
        list of message dicts with chat info
    """
    result = await client(functions.messages.SearchGlobalRequest(
        q=query,
        filter=types.InputMessagesFilterEmpty(),
        min_date=None,
        max_date=None,
        offset_rate=0,
        offset_peer=types.InputPeerEmpty(),
        offset_id=0,
        limit=min(limit, 100),
    ))
    
    messages = []
    for msg in result.messages:
        sender = None
        for u in result.users:
            if u.id == msg.from_id.user_id if msg.from_id and hasattr(msg.from_id, "user_id") else 0:
                sender = u
                break
        
        chat = None
        for c in result.chats:
            peer_id = msg.peer_id
            if (hasattr(peer_id, "channel_id") and c.id == peer_id.channel_id) or \
               (hasattr(peer_id, "chat_id") and c.id == peer_id.chat_id):
                chat = c
                break
        
        messages.append({
            "id": msg.id,
            "text": msg.message or "",
            "date": str(msg.date),
            "sender": (sender.first_name if sender else "Unknown"),
            "chat": chat.title if chat else "Unknown",
            "chat_id": msg.peer_id.channel_id if hasattr(msg.peer_id, "channel_id") else
                       msg.peer_id.chat_id if hasattr(msg.peer_id, "chat_id") else
                       msg.peer_id.user_id if hasattr(msg.peer_id, "user_id") else None,
        })
    return messages
