"""Channel and message statistics."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def get_channel_stats(client: TelegramClient, entity: str | int, dark: bool = False) -> dict:
    """Get channel statistics.
    
    Args:
        client: Authenticated Telethon client
        entity: Channel entity
        dark: Dark mode for stats graphics
    
    Returns:
        dict with channel stats
    """
    e = await client.get_input_entity(entity)
    result = await client(functions.stats.GetBroadcastStatsRequest(
        channel=e,
        dark=dark,
    ))
    
    stats = {}
    if result.period:
        stats["period"] = [{
            "date": str(p.date),
            "followers": p.followers,
            "views_per_post": p.views_per_post,
            "shares_per_post": p.shares_per_post,
        } for p in result.period]
    
    if result.followers:
        f = result.followers
        stats["followers"] = {
            "current": f.current,
            "old": f.old,
        }
    
    if result.top_posters:
        stats["top_posters"] = [{
            "user_id": tp.user_id,
            "messages": tp.messages,
        } for tp in result.top_posters[:10]]
    
    return stats


async def get_message_stats(client: TelegramClient, entity: str | int, message_ids: list[int]) -> list[dict]:
    """Get message view/reaction statistics.
    
    Args:
        client: Authenticated Telethon client
        entity: Channel entity
        message_ids: List of message IDs
    
    Returns:
        list of message stat dicts
    """
    e = await client.get_input_entity(entity)
    result = await client(functions.messages.GetMessagesViewsRequest(
        peer=e,
        id=message_ids,
        increment=False,
    ))
    
    stats = []
    for v in result.views:
        stats.append({
            "message_id": v.id if hasattr(v, "id") else None,
            "views": v.views,
            "forwards": v.forwards if hasattr(v, "forwards") else 0,
            "replies": v.replies.replies if hasattr(v, "replies") and v.replies else 0,
        })
    return stats
