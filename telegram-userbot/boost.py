"""Channel boost operations."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def boost_channel(client: TelegramClient, entity: str | int) -> dict:
    """Boost a channel with available boosts.
    
    Args:
        client: Authenticated Telethon client
        entity: Channel entity to boost
    
    Returns:
        dict with boost status
    """
    e = await client.get_input_entity(entity)
    result = await client(functions.premium.BoostsApplyBoostRequest(
        peer=e,
    ))
    return {"boosted": True, "entity": str(entity), "result": str(result)}


async def get_boosts(client: TelegramClient, entity: str | int) -> dict:
    """Get boost status for a channel.
    
    Args:
        client: Authenticated Telethon client
        entity: Channel entity
    
    Returns:
        dict with boost info
    """
    e = await client.get_input_entity(entity)
    result = await client(functions.premium.GetBoostsStatusRequest(
        peer=e,
    ))
    return {
        "level": result.level,
        "boosts": result.boosts,
        "my_boosts": result.my_boosts,
        "premium_audience": str(result.premium_audience) if hasattr(result, "premium_audience") and result.premium_audience else None,
    }
