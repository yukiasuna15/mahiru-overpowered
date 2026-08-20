"""Message drafts management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def save_draft(client: TelegramClient, entity: str | int, text: str, reply_to: int = None) -> dict:
    """Save a message draft.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        text: Draft text
        reply_to: Optional message ID to reply to
    
    Returns:
        dict with draft status
    """
    e = await client.get_entity(entity)
    kwargs = {
        "peer": await client.get_input_entity(e),
        "message": text,
    }
    if reply_to is not None:
        kwargs["reply_to_msg_id"] = reply_to
    await client(functions.messages.SaveDraftRequest(**kwargs))
    return {"saved": True, "text": text, "entity": str(entity)}


async def get_draft(client: TelegramClient, entity: str | int) -> dict:
    """Get the current draft for a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
    
    Returns:
        dict with draft info or empty dict
    """
    e = await client.get_input_entity(entity)
    result = await client(functions.messages.GetDraftsRequest(
        peers=[e]
    ))
    if result.drafts:
        draft = result.drafts[0]
        return {
            "text": draft.draft.message or "",
            "date": str(draft.draft.date) if draft.draft.date else None,
            "reply_to": draft.draft.reply_to_msg_id,
        }
    return {"text": "", "date": None, "reply_to": None}


async def delete_draft(client: TelegramClient, entity: str | int) -> dict:
    """Clear/delete the draft for a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
    
    Returns:
        dict with deletion status
    """
    e = await client.get_input_entity(entity)
    await client(functions.messages.SaveDraftRequest(
        peer=e,
        message="",
    ))
    return {"deleted": True, "entity": str(entity)}
