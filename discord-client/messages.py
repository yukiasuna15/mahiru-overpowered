"""
Discord messages module — send, edit, delete, reply, react, history, pin.
Uses discord.py-self.
"""

import discord
from typing import Optional, List, Union


async def send_message(
    channel: Union[discord.TextChannel, discord.DMChannel, discord.GroupChannel],
    content: str = "",
    files: Optional[List[discord.File]] = None,
    embed: Optional[discord.Embed] = None,
    reference: Optional[discord.Message] = None,
    mention_author: bool = False,
) -> discord.Message:
    """Send a message to a channel."""
    return await channel.send(
        content=content or None,
        files=files,
        embed=embed,
        reference=reference,
        mention_author=mention_author,
    )


async def edit_message(message: discord.Message, content: str) -> discord.Message:
    """Edit an existing message."""
    return await message.edit(content=content)


async def delete_message(message: discord.Message) -> None:
    """Delete a message."""
    await message.delete()


async def reply_to(
    message: discord.Message,
    content: str,
    mention_author: bool = False,
) -> discord.Message:
    """Reply to a specific message."""
    return await message.reply(content=content, mention_author=mention_author)


async def add_reaction(message: discord.Message, emoji: str) -> None:
    """Add a reaction to a message."""
    await message.add_reaction(emoji)


async def remove_reaction(
    message: discord.Message, emoji: str, user: Optional[discord.User] = None, client: Optional[discord.Client] = None
) -> None:
    """Remove a reaction. If user is None, removes own reaction."""
    if user is not None:
        await message.remove_reaction(emoji, user)
    else:
        self_user = message.guild.me if message.guild else (client.user if client else message.author)
        await message.remove_reaction(emoji, self_user)


async def clear_reactions(message: discord.Message) -> None:
    """Clear all reactions on a message."""
    await message.clear_reactions()


async def pin_message(message: discord.Message) -> None:
    """Pin a message."""
    await message.pin()


async def unpin_message(message: discord.Message) -> None:
    """Unpin a message."""
    await message.unpin()


async def fetch_message(channel: discord.TextChannel, message_id: int) -> discord.Message:
    """Fetch a message by ID from a channel."""
    return await channel.fetch_message(message_id)


async def get_history(
    channel: Union[discord.TextChannel, discord.DMChannel, discord.GroupChannel],
    limit: int = 100,
    before: Optional[discord.Message] = None,
    after: Optional[discord.Message] = None,
) -> List[discord.Message]:
    """Get message history from a channel."""
    messages = []
    async for msg in channel.history(limit=limit, before=before, after=after):
        messages.append(msg)
    return messages


async def search_messages(
    channel: discord.TextChannel,
    query: str,
    limit: int = 25,
) -> List[discord.Message]:
    """Search messages in a channel."""
    messages = []
    async for msg in channel.search(query, limit=limit):
        messages.append(msg)
    return messages


async def delete_messages(channel: discord.TextChannel, messages: List[discord.Message]) -> None:
    """Bulk delete messages (must be < 14 days old)."""
    await channel.delete_messages(messages)


async def purge_messages(channel: discord.TextChannel, limit: int = 100) -> int:
    """Purge messages from a channel. Returns count deleted."""
    return await channel.purge(limit=limit)
