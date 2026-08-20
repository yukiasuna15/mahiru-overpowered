"""Message reactions management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def add_reaction(client: TelegramClient, entity: str | int, message_id: int, emoji: str = "👍") -> dict:
    """Add a reaction to a message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity (username, ID, or link)
        message_id: Message ID to react to
        emoji: Reaction emoji string (e.g. "👍", "❤️", "🔥")
    
    Returns:
        dict with reaction status
    """
    result = await client(functions.messages.SendReactionRequest(
        peer=entity,
        msg_id=message_id,
        reaction=[types.ReactionEmoji(emoticon=emoji)]
    ))
    return {"added": True, "emoji": emoji, "message_id": message_id}


async def remove_reaction(client: TelegramClient, entity: str | int, message_id: int, emoji: str = "👍") -> dict:
    """Remove a specific reaction from a message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID
        emoji: Reaction emoji to remove
    
    Returns:
        dict with removal status
    """
    result = await client(functions.messages.SendReactionRequest(
        peer=entity,
        msg_id=message_id,
        reaction=[]
    ))
    return {"removed": True, "emoji": emoji, "message_id": message_id}


async def get_reactions(client: TelegramClient, entity: str | int, message_id: int) -> dict:
    """Get reactions on a message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID
    
    Returns:
        dict with reaction details
    """
    msg = await client.get_messages(entity, ids=message_id)
    if not msg:
        return {"error": "Message not found"}
    
    reactions = []
    if msg.reactions:
        for r in msg.reactions.results:
            emoji = r.reaction.emoticon if isinstance(r.reaction, types.ReactionEmoji) else str(r.reaction)
            reactions.append({
                "emoji": emoji,
                "count": r.count,
                "chosen": r.chosen if hasattr(r, 'chosen') else False,
            })
    
    return {
        "message_id": message_id,
        "reactions": reactions,
        "total_count": msg.reactions.total_count if msg.reactions else 0,
    }


async def set_default_reaction(client: TelegramClient, entity: str | int, emoji: str = "👍") -> dict:
    """Set default reaction for a chat (requires admin rights in channels/groups).
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        emoji: Default reaction emoji
    
    Returns:
        dict with status
    """
    e = await client.get_entity(entity)
    result = await client(functions.messages.SetDefaultReactionRequest(
        peer=e,
        reaction=[types.ReactionEmoji(emoticon=emoji)]
    ))
    return {"set": True, "emoji": emoji, "result": result}
