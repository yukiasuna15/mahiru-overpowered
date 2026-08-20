"""Emoji status management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def set_emoji_status(client: TelegramClient, emoji_id: int) -> dict:
    """Set emoji status.
    
    Args:
        client: Authenticated Telethon client
        emoji_id: Document ID of the emoji
    
    Returns:
        dict with status
    """
    result = await client(functions.account.UpdateEmojiStatusRequest(
        emoji_status=types.EmojiStatus(document_id=emoji_id),
    ))
    return {"set": True, "emoji_id": emoji_id}


async def get_emoji_status(client: TelegramClient, user: str | int = None) -> dict:
    """Get emoji status for self or a user.
    
    Args:
        client: Authenticated Telethon client
        user: User entity (None for self)
    
    Returns:
        dict with emoji status info
    """
    if user is None:
        me = await client.get_me()
        entity = me
    else:
        entity = await client.get_entity(user)
    
    full = await client(functions.users.GetFullUserRequest(id=entity.id))
    emoji_status = full.full_user.emoji_status
    
    if emoji_status and hasattr(emoji_status, "document_id"):
        return {
            "has_status": True,
            "document_id": emoji_status.document_id,
            "until": str(emoji_status.until_date) if hasattr(emoji_status, "until_date") and emoji_status.until_date else None,
        }
    return {"has_status": False}
