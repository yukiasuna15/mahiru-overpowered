"""
Discord DM module — DM 1:1, group DM.
Uses discord.py-self.
"""

import discord
from typing import Optional, List, Union


async def create_dm(client: discord.Client, user_id: int) -> discord.DMChannel:
    """Create or get a DM channel with a user."""
    user = await client.fetch_user(user_id)
    return await user.create_dm()


async def send_dm(
    client: discord.Client, user_id: int, content: str
) -> discord.Message:
    """Send a DM to a user by ID."""
    user = await client.fetch_user(user_id)
    dm = await user.create_dm()
    return await dm.send(content)


async def list_dms(client: discord.Client) -> List[dict]:
    """List all DM channels."""
    channels = await client.fetch_private_channels()
    return [
        {
            "id": str(c.id),
            "type": "dm" if isinstance(c, discord.DMChannel) else "group",
            "user": c.user.name if isinstance(c, discord.DMChannel) and c.user else None,
            "recipients": (
                [r.name for r in c.recipients]
                if isinstance(c, discord.GroupChannel)
                else []
            ),
            "name": c.name if isinstance(c, discord.GroupChannel) else None,
        }
        for c in channels
    ]


async def get_dm_history(
    channel: Union[discord.DMChannel, discord.GroupChannel],
    limit: int = 100,
) -> List[discord.Message]:
    """Get message history from a DM or group DM."""
    messages = []
    async for msg in channel.history(limit=limit):
        messages.append(msg)
    return messages


async def create_group_dm(
    client: discord.Client,
    user_ids: List[int],
) -> discord.GroupChannel:
    """Create a group DM with multiple users."""
    users = []
    for uid in user_ids:
        user = await client.fetch_user(uid)
        users.append(user)
    return await client.create_group(*users)


async def add_to_group(client: discord.Client, group: discord.GroupChannel, user_id: int) -> None:
    """Add a user to a group DM."""
    user = await client.fetch_user(user_id)
    await group.add_recipients(user)


async def remove_from_group(group: discord.GroupChannel, user_id: int) -> None:
    """Remove a user from a group DM."""
    await group.remove_recipients([user_id])


async def leave_group(group: discord.GroupChannel) -> None:
    """Leave a group DM."""
    await group.leave()


async def close_dm(channel: discord.DMChannel) -> None:
    """Close a DM channel."""
    await channel.close()


async def accept_dm(channel: discord.DMChannel) -> None:
    """Accept a message request DM."""
    await channel.accept()


async def decline_dm(channel: discord.DMChannel) -> None:
    """Decline a message request DM."""
    await channel.decline()
