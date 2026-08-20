"""GIF search and send."""

import os

from telethon import TelegramClient
from telethon.tl import functions, types


async def search_gif(client: TelegramClient, query: str, limit: int = 10) -> list[dict]:
    """Search for GIFs.
    
    Args:
        client: Authenticated Telethon client
        query: Search query
        limit: Max results
    
    Returns:
        list of GIF info dicts
    """
    result = await client(functions.messages.GetInlineBotResultsRequest(
        peer="me",
        bot=await client.get_input_entity("gif"),
        query=query,
        geo_point=None,
        offset="",
    ))
    
    gifs = []
    for r in result.results[:limit]:
        gifs.append({
            "id": r.id,
            "type": r.type,
            "title": getattr(r, "title", None),
            "description": getattr(r, "description", None),
            "thumb_url": getattr(r, "thumb", {}).url if hasattr(getattr(r, "thumb", None), "url") else None,
        })
    return gifs


async def send_gif(client: TelegramClient, entity: str | int, gif_query: str) -> dict:
    """Search and send the first GIF result.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        gif_query: GIF search query
    
    Returns:
        dict with sent message info
    """
    result = await client(functions.messages.GetInlineBotResultsRequest(
        peer="me",
        bot=await client.get_input_entity("gif"),
        query=gif_query,
        geo_point=None,
        offset="",
    ))
    
    if not result.results:
        return {"error": "No GIFs found"}
    
    first = result.results[0]
    await client(functions.messages.SendInlineBotResultRequest(
        peer=entity,
        query_id=result.query_id,
        id=first.id,
        random_id=int.from_bytes(os.urandom(8), 'big', signed=True),
    ))
    return {"sent": True, "query": gif_query, "gif_id": first.id}
