"""
Discord threads module — create, join, leave, manage threads.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def create_thread_from_message(
    message: discord.Message,
    name: str,
    auto_archive_duration: int = 1440,
    slowmode_delay: int = 0,
) -> discord.Thread:
    """Create a thread from a message."""
    return await message.create_thread(
        name=name,
        auto_archive_duration=auto_archive_duration,
        slowmode_delay=slowmode_delay,
    )


async def create_thread_in_channel(
    channel: discord.TextChannel,
    name: str,
    auto_archive_duration: int = 1440,
    slowmode_delay: int = 0,
    invitable: bool = True,
) -> discord.Thread:
    """Create a standalone thread in a channel (not tied to a message)."""
    return await channel.create_thread(
        name=name,
        auto_archive_duration=auto_archive_duration,
        slowmode_delay=slowmode_delay,
        invitable=invitable,
    )


async def create_forum_thread(
    channel: discord.ForumChannel,
    name: str,
    content: str = "",
    embed: Optional[discord.Embed] = None,
    files: Optional[List[discord.File]] = None,
    tags: Optional[List[discord.ForumTag]] = None,
    auto_archive_duration: int = 1440,
) -> discord.Thread:
    """Create a new post in a forum channel."""
    return await channel.create_thread(
        name=name,
        content=content,
        embed=embed,
        files=files,
        applied_tags=tags,
        auto_archive_duration=auto_archive_duration,
    )


async def join_thread(thread: discord.Thread) -> None:
    """Join a thread."""
    await thread.join()


async def leave_thread(thread: discord.Thread) -> None:
    """Leave a thread."""
    await thread.leave()


async def add_user_to_thread(thread: discord.Thread, user: discord.User) -> None:
    """Add a user to a thread."""
    await thread.add_user(user)


async def remove_user_from_thread(thread: discord.Thread, user: discord.User) -> None:
    """Remove a user from a thread."""
    await thread.remove_user(user)


async def get_thread_members(thread: discord.Thread) -> List[dict]:
    """Get all members of a thread."""
    members = await thread.fetch_members()
    return [
        {"id": str(m.id), "joined_at": str(m.joined_at)}
        for m in members
    ]


async def get_archived_threads(
    channel: discord.TextChannel,
    limit: int = 50,
    joined: bool = False,
) -> List[dict]:
    """Get archived threads from a channel."""
    threads = []
    if joined:
        async for thread in channel.archived_threads(limit=limit, joined=True):
            threads.append({
                "id": str(thread.id),
                "name": thread.name,
                "archived_at": str(thread.archived_at),
                "owner": thread.owner.name if thread.owner else None,
            })
    else:
        async for thread in channel.archived_threads(limit=limit):
            threads.append({
                "id": str(thread.id),
                "name": thread.name,
                "archived_at": str(thread.archived_at),
                "owner": thread.owner.name if thread.owner else None,
            })
    return threads


async def edit_thread(
    thread: discord.Thread,
    name: Optional[str] = None,
    archived: Optional[bool] = None,
    locked: Optional[bool] = None,
    pinned: Optional[bool] = None,
    slowmode_delay: Optional[int] = None,
    auto_archive_duration: Optional[int] = None,
) -> None:
    """Edit thread properties."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if archived is not None:
        kwargs["archived"] = archived
    if locked is not None:
        kwargs["locked"] = locked
    if pinned is not None:
        kwargs["pinned"] = pinned
    if slowmode_delay is not None:
        kwargs["slowmode_delay"] = slowmode_delay
    if auto_archive_duration is not None:
        kwargs["auto_archive_duration"] = auto_archive_duration
    await thread.edit(**kwargs)


async def delete_thread(thread: discord.Thread) -> None:
    """Delete a thread."""
    await thread.delete()


async def add_tags(thread: discord.Thread, *tags: discord.ForumTag) -> None:
    """Add tags to a forum thread."""
    await thread.add_tags(*tags)


async def remove_tags(thread: discord.Thread, *tags: discord.ForumTag) -> None:
    """Remove tags from a forum thread."""
    await thread.remove_tags(*tags)


async def get_forum_tags(channel: discord.ForumChannel) -> List[dict]:
    """Get all available tags in a forum channel."""
    return [
        {"id": str(t.id), "name": t.name, "emoji": str(t.emoji) if t.emoji else None}
        for t in channel.available_tags
    ]


async def create_forum_tag(
    channel: discord.ForumChannel,
    name: str,
    emoji: Optional[str] = None,
    moderated: bool = False,
) -> discord.ForumTag:
    """Create a new tag in a forum channel."""
    return await channel.create_tag(name=name, emoji=emoji, moderated=moderated)
