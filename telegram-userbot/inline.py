"""Inline bot queries and answers."""

import os

from telethon import TelegramClient
from telethon.tl import functions, types


async def send_inline(client: TelegramClient, bot: str, query: str, entity: str | int = None) -> dict:
    """Send an inline query to a bot and optionally send the result to a chat.
    
    Args:
        client: Authenticated Telethon client
        bot: Bot username
        query: Query string
        entity: Chat to send result to (None = just get results)
    
    Returns:
        dict with inline results or sent message
    """
    result = await client(functions.messages.GetInlineBotResultsRequest(
        peer="me",
        bot=await client.get_input_entity(bot),
        query=query,
        geo_point=None,
        offset="",
    ))
    
    results = []
    for r in result.results:
        results.append({
            "id": r.id,
            "type": r.type,
            "title": getattr(r, "title", None),
            "description": getattr(r, "description", None),
        })
    
    if entity and results:
        # Send first result
        await client(functions.messages.SendInlineBotResultRequest(
            peer=entity,
            query_id=result.query_id,
            id=results[0]["id"],
            random_id=int.from_bytes(os.urandom(8), 'big', signed=True),
        ))
        return {"sent": True, "result": results[0], "total_results": len(results)}
    
    return {"results": results, "query_id": result.query_id, "total": len(results)}


async def answer_inline(client: TelegramClient, query_id: int, results: list) -> dict:
    """Answer an inline query (for running as a bot).
    
    Args:
        client: Authenticated Telethon client
        query_id: Query ID from the inline query update
        results: List of InputBotInlineResult objects
    
    Returns:
        dict with status
    """
    await client(functions.messages.SetInlineBotResultsRequest(
        query_id=query_id,
        results=results,
        cache_time=300,
        gallery=False,
        next_offset="",
    ))
    return {"answered": True, "query_id": query_id}
