"""
Discord presence/status module — change status, activity, custom status.
Uses discord.py-self.
"""

import discord
from typing import Optional


async def set_status(
    client: discord.Client,
    status: discord.Status = discord.Status.online,
) -> None:
    """Set account status (online, idle, dnd, invisible)."""
    await client.change_presence(status=status)


async def set_activity(
    client: discord.Client,
    activity_type: discord.ActivityType = discord.ActivityType.playing,
    name: str = "",
    url: Optional[str] = None,
    details: Optional[str] = None,
    state: Optional[str] = None,
) -> None:
    """Set activity (playing, streaming, listening, watching, competing)."""
    activity = discord.Activity(
        type=activity_type,
        name=name,
        url=url,
        details=details,
        state=state,
    )
    await client.change_presence(activity=activity)


async def set_custom_status(
    client: discord.Client,
    text: str,
    emoji: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> None:
    """Set a custom status message."""
    activity = discord.CustomActivity(
        name=text,
        emoji=emoji,
    )
    await client.change_presence(activity=activity)


async def set_streaming(
    client: discord.Client,
    name: str,
    url: str,
) -> None:
    """Set streaming status (requires valid Twitch/YouTube URL)."""
    activity = discord.Streaming(name=name, url=url)
    await client.change_presence(activity=activity)


async def set_listening(
    client: discord.Client,
    name: str,
) -> None:
    """Set listening status."""
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name=name,
    )
    await client.change_presence(activity=activity)


async def set_watching(
    client: discord.Client,
    name: str,
) -> None:
    """Set watching status."""
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=name,
    )
    await client.change_presence(activity=activity)


async def set_competing(
    client: discord.Client,
    name: str,
) -> None:
    """Set competing status."""
    activity = discord.Activity(
        type=discord.ActivityType.competing,
        name=name,
    )
    await client.change_presence(activity=activity)


async def clear_presence(client: discord.Client) -> None:
    """Clear all presence/activity."""
    await client.change_presence(status=discord.Status.online, activity=None)
