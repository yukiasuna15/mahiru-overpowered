"""Giveaway management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def create_giveaway(
    client: TelegramClient,
    entity: str | int,
    quantity: int,
    months: int = 12,
    until_date: int = None,
    countries: list[str] = None,
    prize_description: str = None,
) -> dict:
    """Create a Telegram Premium giveaway.
    
    Args:
        client: Authenticated Telethon client
        entity: Channel/group entity
        quantity: Number of winners
        months: Premium subscription months
        until_date: Unix timestamp for giveaway end
        countries: Country codes filter (optional)
        prize_description: Custom prize description (optional)
    
    Returns:
        dict with giveaway info
    """
    e = await client.get_input_entity(entity)
    
    media = types.InputMediaGiveaway(
        channels=[e],
        quantity=quantity,
        months=months,
        until_date=until_date,
        countries_iso2=countries or [],
        prize_description=prize_description or "",
    )
    
    result = await client.send_message(entity, file=media)
    return {"created": True, "id": result.id, "quantity": quantity, "months": months}


async def get_giveaway(client: TelegramClient, entity: str | int, message_id: int) -> dict:
    """Get giveaway results.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID with giveaway
    
    Returns:
        dict with giveaway results
    """
    msg = await client.get_messages(entity, ids=message_id)
    if not msg or not msg.media:
        return {"error": "No media found in message"}
    
    media = msg.media
    if isinstance(media, types.MessageMediaGiveaway):
        return {
            "type": "giveaway",
            "channels": [c.channel_id for c in media.channels] if media.channels else [],
            "quantity": media.quantity,
            "months": media.months,
            "until_date": str(media.until_date) if media.until_date else None,
            "countries": media.countries_iso2,
        }
    elif isinstance(media, types.MessageMediaGiveawayResults):
        return {
            "type": "results",
            "winners_count": media.winners_count,
            "unclaimed_count": media.unclaimed_count,
            "winners": [w.user_id for w in media.winners] if media.winners else [],
        }
    return {"error": "Message is not a giveaway", "media_type": type(media).__name__}
