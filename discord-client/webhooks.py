"""
Discord webhooks module — create, send, edit, delete, manage webhooks.
Uses discord.py-self.
"""

import discord
from typing import Optional, List, Union


async def create_webhook(
    channel: discord.TextChannel,
    name: str,
    avatar: Optional[bytes] = None,
    reason: Optional[str] = None,
) -> discord.Webhook:
    """Create a webhook in a channel."""
    return await channel.create_webhook(name=name, avatar=avatar, reason=reason)


async def get_webhooks(guild: discord.Guild) -> List[dict]:
    """List all webhooks in a guild."""
    webhooks = await guild.webhooks()
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "channel": w.channel.name if w.channel else None,
            "owner": w.user.name if w.user else None,
            "url": w.url,
        }
        for w in webhooks
    ]


async def get_channel_webhooks(channel: discord.TextChannel) -> List[dict]:
    """List webhooks for a specific channel."""
    webhooks = await channel.webhooks()
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "url": w.url,
        }
        for w in webhooks
    ]


async def fetch_webhook(client: discord.Client, webhook_id: int) -> discord.Webhook:
    """Fetch a webhook by ID."""
    return await client.fetch_webhook(webhook_id)


async def send_webhook(
    webhook: discord.Webhook,
    content: str = "",
    username: Optional[str] = None,
    avatar_url: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    file: Optional[discord.File] = None,
    wait: bool = True,
) -> Optional[discord.Message]:
    """Send a message via webhook."""
    kwargs = {"wait": wait}
    if content:
        kwargs["content"] = content
    if username:
        kwargs["username"] = username
    if avatar_url:
        kwargs["avatar_url"] = avatar_url
    if embed:
        kwargs["embed"] = embed
    if file:
        kwargs["file"] = file
    return await webhook.send(**kwargs)


async def edit_webhook(
    webhook: discord.Webhook,
    name: Optional[str] = None,
    avatar: Optional[bytes] = None,
    channel: Optional[discord.TextChannel] = None,
) -> None:
    """Edit a webhook."""
    kwargs = {}
    if name:
        kwargs["name"] = name
    if avatar:
        kwargs["avatar"] = avatar
    if channel:
        kwargs["channel"] = channel
    await webhook.edit(**kwargs)


async def delete_webhook(webhook: discord.Webhook) -> None:
    """Delete a webhook."""
    await webhook.delete()


async def webhook_from_url(url: str) -> discord.Webhook:
    """Get a webhook from its URL."""
    return await discord.Webhook.from_url(url)
