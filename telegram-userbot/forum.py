"""Forum topic management for supergroups."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def create_topic(client: TelegramClient, entity: str | int, title: str, icon_color: int = None) -> dict:
    """Create a forum topic.
    
    Args:
        client: Authenticated Telethon client
        entity: Supergroup entity
        title: Topic title
        icon_color: Topic icon color (optional, int)
    
    Returns:
        dict with topic info
    """
    e = await client.get_input_entity(entity)
    kwargs = {"peer": e, "title": title}
    if icon_color is not None:
        kwargs["icon_color"] = icon_color
    
    result = await client(functions.channels.CreateForumTopicRequest(**kwargs))
    return {"created": True, "title": title, "result": str(result)}


async def edit_topic(client: TelegramClient, entity: str | int, topic_id: int, title: str = None, icon_emoji_id: int = None) -> dict:
    """Edit a forum topic.
    
    Args:
        client: Authenticated Telethon client
        entity: Supergroup entity
        topic_id: Topic ID (top_message ID)
        title: New title (optional)
        icon_emoji_id: New icon emoji ID (optional)
    
    Returns:
        dict with status
    """
    e = await client.get_input_entity(entity)
    await client(functions.channels.EditForumTopicRequest(
        channel=e,
        topic_id=topic_id,
        title=title,
        icon_emoji_id=icon_emoji_id,
    ))
    return {"edited": True, "topic_id": topic_id, "title": title}


async def delete_topic(client: TelegramClient, entity: str | int, topic_id: int) -> dict:
    """Delete a forum topic.
    
    Args:
        client: Authenticated Telethon client
        entity: Supergroup entity
        topic_id: Topic ID
    
    Returns:
        dict with status
    """
    e = await client.get_input_entity(entity)
    await client(functions.channels.DeleteTopicHistoryRequest(
        channel=e,
        top_msg_id=topic_id,
    ))
    return {"deleted": True, "topic_id": topic_id}


async def get_topics(client: TelegramClient, entity: str | int, limit: int = 100) -> list[dict]:
    """Get forum topics.
    
    Args:
        client: Authenticated Telethon client
        entity: Supergroup entity
        limit: Max topics to return
    
    Returns:
        list of topic dicts
    """
    e = await client.get_input_entity(entity)
    result = await client(functions.channels.GetForumTopicsRequest(
        channel=e,
        offset_date=0,
        offset_id=0,
        offset_topic_id=0,
        limit=min(limit, 100),
    ))
    
    topics = []
    for t in result.topics:
        topics.append({
            "id": t.id,
            "title": t.title,
            "top_message": t.top_message,
            "unread_count": getattr(t, "unread_count", 0),
            "icon_color": t.icon_color if hasattr(t, "icon_color") else None,
        })
    return topics
