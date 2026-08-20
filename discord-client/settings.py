"""
Discord settings module — guild settings, notification settings, sessions, user settings.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


# === Guild Settings ===

async def edit_guild(
    guild: discord.Guild,
    name: Optional[str] = None,
    description: Optional[str] = None,
    icon: Optional[bytes] = None,
    banner: Optional[bytes] = None,
    splash: Optional[bytes] = None,
    discovery_splash: Optional[bytes] = None,
    region: Optional[str] = None,
    afk_channel: Optional[discord.VoiceChannel] = None,
    afk_timeout: Optional[int] = None,
    system_channel: Optional[discord.TextChannel] = None,
    system_channel_flags: Optional[discord.SystemChannelFlags] = None,
    rules_channel: Optional[discord.TextChannel] = None,
    public_updates_channel: Optional[discord.TextChannel] = None,
    default_notifications: Optional[discord.NotificationLevel] = None,
    explicit_content_filter: Optional[discord.ContentFilter] = None,
    verification_level: Optional[discord.VerificationLevel] = None,
    reason: Optional[str] = None,
) -> None:
    """Edit guild settings."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if icon is not None:
        kwargs["icon"] = icon
    if banner is not None:
        kwargs["banner"] = banner
    if splash is not None:
        kwargs["splash"] = splash
    if discovery_splash is not None:
        kwargs["discovery_splash"] = discovery_splash
    if region is not None:
        kwargs["region"] = region
    if afk_channel is not None:
        kwargs["afk_channel"] = afk_channel
    if afk_timeout is not None:
        kwargs["afk_timeout"] = afk_timeout
    if system_channel is not None:
        kwargs["system_channel"] = system_channel
    if system_channel_flags is not None:
        kwargs["system_channel_flags"] = system_channel_flags
    if rules_channel is not None:
        kwargs["rules_channel"] = rules_channel
    if public_updates_channel is not None:
        kwargs["public_updates_channel"] = public_updates_channel
    if default_notifications is not None:
        kwargs["default_notifications"] = default_notifications
    if explicit_content_filter is not None:
        kwargs["explicit_content_filter"] = explicit_content_filter
    if verification_level is not None:
        kwargs["verification_level"] = verification_level
    if reason is not None:
        kwargs["reason"] = reason
    await guild.edit(**kwargs)


async def edit_welcome_screen(
    guild: discord.Guild,
    enabled: bool = True,
    description: Optional[str] = None,
    welcome_channels: Optional[List[dict]] = None,
) -> None:
    """Edit the welcome screen for community guilds."""
    kwargs = {"enabled": enabled}
    if description:
        kwargs["description"] = description
    if welcome_channels:
        channels = []
        for wc in welcome_channels:
            ch = guild.get_channel(wc["channel_id"])
            channels.append(
                discord.WelcomeChannel(
                    channel=ch,
                    description=wc.get("description", ""),
                    emoji=wc.get("emoji"),
                )
            )
        kwargs["welcome_channels"] = channels
    await guild.edit_welcome_screen(**kwargs)


async def get_welcome_screen(guild: discord.Guild) -> dict:
    """Get the welcome screen configuration."""
    ws = guild.welcome_screen
    if not ws:
        return {"enabled": False}
    return {
        "enabled": True,
        "description": ws.description,
        "channels": [
            {
                "channel": c.channel.name if c.channel else None,
                "description": c.description,
                "emoji": str(c.emoji) if c.emoji else None,
            }
            for c in ws.welcome_channels
        ],
    }


async def edit_widget(
    guild: discord.Guild,
    enabled: bool = True,
    channel: Optional[discord.TextChannel] = None,
) -> None:
    """Edit guild widget settings."""
    await guild.edit_widget(discord.WidgetSettings(enabled=enabled, channel=channel))


async def get_widget(guild: discord.Guild) -> dict:
    """Get guild widget data."""
    try:
        widget = await guild.widget()
        return {
            "name": widget.name,
            "id": str(widget.id),
            "channels": [
                {"id": str(c.id), "name": c.name}
                for c in widget.channels
            ] if widget.channels else [],
            "members": [
                {"name": m.name, "status": str(m.status)}
                for m in widget.members
            ] if widget.members else [],
        }
    except Exception as e:
        return {"error": str(e)}


# === User Settings ===

async def get_settings(client: discord.Client) -> dict:
    """Get current user settings."""
    settings = await client.fetch_settings()
    return {
        "locale": str(settings.locale) if hasattr(settings, "locale") else None,
        "theme": str(settings.theme) if hasattr(settings, "theme") else None,
    }


async def get_notification_settings(client: discord.Client) -> dict:
    """Get notification settings."""
    settings = await client.notification_settings()
    return {"raw": str(settings)}


async def get_email_settings(client: discord.Client) -> dict:
    """Get email notification settings."""
    settings = await client.email_settings()
    return {"raw": str(settings)}


# === Sessions ===

async def get_sessions(client: discord.Client) -> List[dict]:
    """Get all active sessions."""
    sessions = client.sessions  # property, not callable
    return [
        {
            "id": s.session_id,
            "current": s.is_current,
            "os": str(s.os) if s.os else None,
            "status": str(s.status) if s.status else None,
            "active": s.active if hasattr(s, "active") else None,
        }
        for s in sessions
    ]


async def get_connections(client: discord.Client) -> List[dict]:
    """Get linked connections (Spotify, GitHub, etc)."""
    connections = await client.fetch_connections()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "type": c.type,
            "verified": c.verified if hasattr(c, "verified") else None,
            "visible": c.visible if hasattr(c, "visible") else None,
        }
        for c in connections
    ]
