"""
Discord emojis and stickers module — create, edit, delete, manage.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def get_emojis(guild: discord.Guild) -> List[dict]:
    """List all custom emojis in a guild."""
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "url": str(e.url),
            "animated": e.animated,
            "managed": e.managed,
            "available": e.available,
            "require_colons": e.require_colons,
        }
        for e in guild.emojis
    ]


async def get_emoji(guild: discord.Guild, emoji_id: int) -> discord.Emoji:
    """Fetch a specific emoji."""
    return await guild.fetch_emoji(emoji_id)


async def create_emoji(
    guild: discord.Guild,
    name: str,
    image: bytes,
    roles: Optional[List[discord.Role]] = None,
    reason: Optional[str] = None,
) -> discord.Emoji:
    """Create a custom emoji."""
    return await guild.create_custom_emoji(
        name=name, image=image, roles=roles, reason=reason
    )


async def edit_emoji(
    emoji: discord.Emoji,
    name: Optional[str] = None,
    roles: Optional[List[discord.Role]] = None,
    reason: Optional[str] = None,
) -> None:
    """Edit a custom emoji."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if roles is not None:
        kwargs["roles"] = roles
    if reason is not None:
        kwargs["reason"] = reason
    await emoji.edit(**kwargs)


async def delete_emoji(emoji: discord.Emoji, reason: Optional[str] = None) -> None:
    """Delete a custom emoji."""
    await emoji.delete(reason=reason)


async def get_stickers(guild: discord.Guild) -> List[dict]:
    """List all stickers in a guild."""
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "description": s.description,
            "format": str(s.format),
            "available": s.available,
        }
        for s in guild.stickers
    ]


async def get_sticker(guild: discord.Guild, sticker_id: int) -> discord.GuildSticker:
    """Fetch a specific sticker."""
    return await guild.fetch_sticker(sticker_id)


async def create_sticker(
    guild: discord.Guild,
    name: str,
    description: str,
    emoji: str,
    file: discord.File,
    reason: Optional[str] = None,
) -> discord.GuildSticker:
    """Create a sticker in a guild."""
    return await guild.create_sticker(
        name=name, description=description, emoji=emoji, file=file, reason=reason
    )


async def edit_sticker(
    sticker: discord.GuildSticker,
    name: Optional[str] = None,
    description: Optional[str] = None,
    emoji: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Edit a sticker."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if emoji is not None:
        kwargs["emoji"] = emoji
    if reason is not None:
        kwargs["reason"] = reason
    await sticker.edit(**kwargs)


async def delete_sticker(sticker: discord.GuildSticker, reason: Optional[str] = None) -> None:
    """Delete a sticker."""
    await sticker.delete(reason=reason)


async def get_sticker_packs(client: discord.Client) -> List[dict]:
    """Get all available sticker packs."""
    packs = await client.sticker_packs()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "stickers": len(p.stickers),
        }
        for p in packs
    ]


async def save_sticker(sticker: discord.Sticker, path: str) -> None:
    """Download and save a sticker to a file."""
    data = await sticker.read()
    with open(path, "wb") as f:
        f.write(data)
