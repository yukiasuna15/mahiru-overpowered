"""Send and receive messages."""

from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel


async def send_message(client: TelegramClient, entity: str | int, message: str) -> dict:
    """Send a text message to a user, group, or channel."""
    result = await client.send_message(entity, message)
    return {
        "id": result.id,
        "text": result.text,
        "date": str(result.date),
        "peer_id": str(result.peer_id),
    }


async def get_messages(client: TelegramClient, entity: str | int, limit: int = 20) -> list[dict]:
    """Get recent messages from a chat."""
    messages = []
    async for msg in client.iter_messages(entity, limit=limit):
        sender = await msg.get_sender()
        sender_name = "Unknown"
        if sender:
            if hasattr(sender, "first_name"):
                sender_name = sender.first_name or ""
                if hasattr(sender, "last_name") and sender.last_name:
                    sender_name += f" {sender.last_name}"
            elif hasattr(sender, "title"):
                sender_name = sender.title
        messages.append({
            "id": msg.id,
            "text": msg.text or "",
            "date": str(msg.date),
            "sender": sender_name.strip(),
            "is_reply": msg.reply_to is not None,
            "reply_to": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
        })
    return messages


async def reply_to_message(client: TelegramClient, entity: str | int, message_id: int, text: str) -> dict:
    """Reply to a specific message."""
    result = await client.send_message(entity, text, reply_to=message_id)
    return {
        "id": result.id,
        "text": result.text,
        "date": str(result.date),
    }


async def delete_message(client: TelegramClient, entity: str | int, message_id: int) -> bool:
    """Delete a message."""
    await client.delete_messages(entity, message_id)
    return True


async def forward_message(client: TelegramClient, from_entity: str | int, to_entity: str | int, message_id: int) -> dict:
    """Forward a message from one chat to another."""
    result = await client.forward_messages(to_entity, message_id, from_entity)
    return {"forwarded": True, "result_ids": [m.id for m in result] if result else []}
