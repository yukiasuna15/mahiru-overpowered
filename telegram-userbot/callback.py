"""Callback query handling — inline keyboard buttons."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def answer_callback(client: TelegramClient, query_id: int, text: str | None = None, alert: bool = False) -> dict:
    """Answer a callback query from an inline keyboard button.
    
    Args:
        client: Authenticated Telethon client
        query_id: Callback query ID
        text: Text to show in notification (optional)
        alert: Show as alert popup instead of toast
    
    Returns:
        dict with status
    """
    await client(functions.messages.SetBotCallbackAnswerRequest(
        query_id=query_id,
        message=text,
        alert=alert,
    ))
    return {"answered": True, "query_id": query_id, "text": text}


async def send_callback(client: TelegramClient, entity: str | int, message_id: int, data: str = b"") -> dict:
    """Simulate clicking an inline keyboard button.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID with inline keyboard
        data: Button callback data (bytes or string)
    
    Returns:
        dict with callback result
    """
    if isinstance(data, str):
        data = data.encode()
    
    result = await client(functions.messages.GetBotCallbackAnswerRequest(
        peer=entity,
        msg_id=message_id,
        data=data,
    ))
    return {
        "sent": True,
        "message": result.message,
        "alert": result.alert,
        "has_url": result.has_url if hasattr(result, "has_url") else False,
    }
