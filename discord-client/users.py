"""
Discord users module — profiles, friends, block, notes.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def get_user(client: discord.Client, user_id: int) -> discord.User:
    """Fetch a user by ID."""
    return await client.fetch_user(user_id)


async def get_user_profile(client: discord.Client, user_id: int) -> discord.UserProfile:
    """Fetch a user's profile (bio, badges, etc)."""
    user = await client.fetch_user(user_id)
    return await user.profile()


async def get_friends(client: discord.Client) -> List[dict]:
    """List all friends."""
    await client.fetch_relationships()
    return [
        {
            "id": str(r.user.id),
            "name": r.user.name,
            "type": str(r.type),
        }
        for r in client.relationships
        if r.type == discord.RelationshipType.friend
    ]


async def get_blocked(client: discord.Client) -> List[dict]:
    """List all blocked users."""
    await client.fetch_relationships()
    return [
        {
            "id": str(r.user.id),
            "name": r.user.name,
        }
        for r in client.relationships
        if r.type == discord.RelationshipType.blocked
    ]


async def send_friend_request(client: discord.Client, user_id: int) -> None:
    """Send a friend request by user ID."""
    user = await client.fetch_user(user_id)
    await user.send_friend_request()


async def remove_friend(user: discord.User) -> None:
    """Remove a friend."""
    await user.remove_friend()


async def block_user(user: discord.User) -> None:
    """Block a user."""
    await user.block()


async def unblock_user(user: discord.User) -> None:
    """Unblock a user."""
    await user.unblock()


async def get_note(client: discord.Client, user_id: int) -> str:
    """Get your note for a user."""
    note = await client.fetch_note(user_id)
    return note.content if note else ""


async def set_note(user: discord.User, content: str) -> None:
    """Set a note for a user."""
    await user.edit_note(content)


async def get_mutual_friends(user: discord.User) -> List[dict]:
    """Get mutual friends with a user."""
    mutuals = await user.fetch_mutual_friends()
    return [
        {"id": str(u.id), "name": u.name}
        for u in mutuals
    ]


async def get_mutual_guilds(user: discord.User) -> List[dict]:
    """Get mutual guilds with a user (from cache)."""
    return [
        {"id": str(g.id), "name": g.name}
        for g in user.mutual_guilds
    ]
