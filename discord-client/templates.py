"""
Discord templates module — create, edit, sync, delete server templates.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def get_templates(guild: discord.Guild) -> List[dict]:
    """List all templates for a guild."""
    templates = await guild.templates()
    return [
        {
            "code": t.code,
            "name": t.name,
            "description": t.description,
            "creator": t.creator.name if t.creator else None,
            "usage_count": t.usage_count,
            "url": t.url,
            "created_at": str(t.created_at),
            "updated_at": str(t.updated_at),
        }
        for t in templates
    ]


async def fetch_template(client: discord.Client, code: str) -> discord.Template:
    """Fetch a template by code."""
    return await client.fetch_template(code)


async def create_template(
    guild: discord.Guild,
    name: str,
    description: Optional[str] = None,
) -> discord.Template:
    """Create a new template for a guild."""
    return await guild.create_template(name=name, description=description)


async def edit_template(
    template: discord.Template,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """Edit a template."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    await template.edit(**kwargs)


async def sync_template(template: discord.Template) -> None:
    """Sync a template with the current guild state."""
    await template.sync()


async def delete_template(template: discord.Template) -> None:
    """Delete a template."""
    await template.delete()


async def create_guild_from_template(
    client: discord.Client,
    template_code: str,
    name: str,
    icon: Optional[bytes] = None,
) -> discord.Guild:
    """Create a new guild from a template."""
    template = await client.fetch_template(template_code)
    return await template.create_guild(name=name, icon=icon)
