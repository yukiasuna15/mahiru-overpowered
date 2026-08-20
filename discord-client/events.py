"""
Discord scheduled events module — create, edit, delete, RSVP.
Uses discord.py-self.
"""

import discord
from typing import Optional, List
from datetime import datetime


async def get_events(guild: discord.Guild) -> List[dict]:
    """List all scheduled events in a guild."""
    events = await guild.fetch_scheduled_events()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "description": e.description,
            "start_time": str(e.start_time),
            "end_time": str(e.end_time),
            "status": str(e.status),
            "entity_type": str(e.entity_type),
            "location": e.location if hasattr(e, "location") else None,
            "subscriber_count": e.subscriber_count if hasattr(e, "subscriber_count") else None,
        }
        for e in events
    ]


async def get_event(guild: discord.Guild, event_id: int) -> discord.ScheduledEvent:
    """Fetch a specific scheduled event."""
    return await guild.fetch_scheduled_event(event_id)


async def create_event(
    guild: discord.Guild,
    name: str,
    start_time: datetime,
    entity_type: discord.ScheduledEventEntityType,
    description: Optional[str] = None,
    end_time: Optional[datetime] = None,
    channel: Optional[discord.VoiceChannel] = None,
    location: Optional[str] = None,
    privacy_level: discord.PrivacyLevel = discord.PrivacyLevel.guild_only,
) -> discord.ScheduledEvent:
    """Create a scheduled event."""
    kwargs = {
        "name": name,
        "start_time": start_time,
        "entity_type": entity_type,
        "privacy_level": privacy_level,
    }
    if description:
        kwargs["description"] = description
    if end_time:
        kwargs["end_time"] = end_time
    if channel:
        kwargs["channel"] = channel
    if location:
        kwargs["location"] = location
    return await guild.create_scheduled_event(**kwargs)


async def edit_event(
    event: discord.ScheduledEvent,
    name: Optional[str] = None,
    description: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    location: Optional[str] = None,
) -> None:
    """Edit a scheduled event."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if start_time is not None:
        kwargs["start_time"] = start_time
    if end_time is not None:
        kwargs["end_time"] = end_time
    if location is not None:
        kwargs["location"] = location
    await event.edit(**kwargs)


async def delete_event(event: discord.ScheduledEvent) -> None:
    """Delete a scheduled event."""
    await event.delete()


async def start_event(event: discord.ScheduledEvent) -> None:
    """Start a scheduled event."""
    await event.start()


async def end_event(event: discord.ScheduledEvent) -> None:
    """End a scheduled event."""
    await event.end()


async def rsvp_event(event: discord.ScheduledEvent) -> None:
    """RSVP to a scheduled event."""
    await event.rsvp()


async def unrsvp_event(event: discord.ScheduledEvent) -> None:
    """Cancel RSVP to a scheduled event."""
    await event.unrsvp()


async def get_event_subscribers(
    event: discord.ScheduledEvent, limit: int = 100
) -> List[dict]:
    """Get subscribers of a scheduled event."""
    subscribers = []
    async for user in event.users(limit=limit):
        subscribers.append({
            "id": str(user.id),
            "name": user.name,
            "display_name": user.display_name,
        })
    return subscribers
