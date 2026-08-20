"""
Discord servers (guilds) module — list, channels, members, roles, invites.
Uses discord.py-self.
"""

import discord
from typing import Optional, List
from datetime import datetime


async def list_guilds(client: discord.Client) -> List[dict]:
    """List all guilds the account is in."""
    return [
        {
            "id": str(g.id),
            "name": g.name,
            "owner": g.owner.name if g.owner else None,
            "member_count": g.member_count,
            "channels": len(g.channels),
            "roles": len(g.roles),
        }
        for g in client.guilds
    ]


async def get_guild(client: discord.Client, guild_id: int) -> discord.Guild:
    """Get a guild by ID."""
    return await client.fetch_guild(guild_id)


async def get_channels(guild: discord.Guild) -> List[dict]:
    """List all channels in a guild."""
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "type": str(c.type),
            "category": c.category.name if hasattr(c, "category") and c.category else None,
        }
        for c in guild.channels
    ]


async def get_text_channels(guild: discord.Guild) -> List[dict]:
    """List text channels in a guild."""
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "nsfw": c.is_nsfw(),
            "news": c.is_news(),
        }
        for c in guild.text_channels
    ]


async def get_members(guild: discord.Guild, limit: int = 100) -> List[dict]:
    """Get members from a guild (requires chunk or cache)."""
    members = []
    async for member in guild.fetch_members(limit=limit):
        members.append({
            "id": str(member.id),
            "name": member.name,
            "display_name": member.display_name,
            "bot": member.bot,
            "roles": [r.name for r in member.roles],
        })
    return members


async def get_member(guild: discord.Guild, user_id: int) -> discord.Member:
    """Fetch a specific member by ID."""
    return await guild.fetch_member(user_id)


async def get_roles(guild: discord.Guild) -> List[dict]:
    """List all roles in a guild."""
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "color": str(r.color),
            "position": r.position,
            "permissions": r.permissions.value,
        }
        for r in guild.roles
    ]


async def create_role(
    guild: discord.Guild,
    name: str,
    color: discord.Color = discord.Color.default(),
    permissions: Optional[discord.Permissions] = None,
) -> discord.Role:
    """Create a new role in a guild."""
    return await guild.create_role(name=name, color=color, permissions=permissions)


async def create_text_channel(
    guild: discord.Guild,
    name: str,
    category: Optional[discord.CategoryChannel] = None,
    topic: Optional[str] = None,
) -> discord.TextChannel:
    """Create a new text channel."""
    return await guild.create_text_channel(name=name, category=category, topic=topic)


async def create_invite(
    channel: discord.TextChannel,
    max_age: int = 0,
    max_uses: int = 0,
    temporary: bool = False,
) -> discord.Invite:
    """Create an invite for a channel."""
    return await channel.create_invite(
        max_age=max_age, max_uses=max_uses, temporary=temporary
    )


async def get_invites(guild: discord.Guild) -> List[dict]:
    """List all active invites in a guild."""
    invites = await guild.invites()
    return [
        {
            "code": i.code,
            "url": i.url,
            "uses": i.uses,
            "max_uses": i.max_uses,
            "inviter": i.inviter.name if i.inviter else None,
        }
        for i in invites
    ]


async def ban_member(
    guild: discord.Guild,
    user: discord.User,
    reason: Optional[str] = None,
    delete_message_days: int = 0,
) -> None:
    """Ban a user from a guild."""
    await guild.ban(user, reason=reason, delete_message_days=delete_message_days)


async def unban_member(guild: discord.Guild, user: discord.User) -> None:
    """Unban a user from a guild."""
    await guild.unban(user)


async def kick_member(member: discord.Member, reason: Optional[str] = None) -> None:
    """Kick a member from a guild."""
    await member.kick(reason=reason)


async def timeout_member(
    member: discord.Member, duration: Optional[datetime] = None
) -> None:
    """Timeout a member."""
    await member.timeout(duration)


async def edit_member(
    member: discord.Member,
    nick: Optional[str] = None,
    roles: Optional[List[discord.Role]] = None,
) -> None:
    """Edit a member's properties."""
    kwargs = {}
    if nick is not None:
        kwargs["nick"] = nick
    if roles is not None:
        kwargs["roles"] = roles
    await member.edit(**kwargs)


async def join_guild(client: discord.Client, invite_code: str) -> discord.Guild:
    """Join a guild via invite code."""
    invite = await client.fetch_invite(invite_code)
    return await invite.accept()


async def leave_guild(guild: discord.Guild) -> None:
    """Leave a guild."""
    await guild.leave()


async def delete_guild(guild: discord.Guild) -> None:
    """Delete a guild (owner only)."""
    await guild.delete()
