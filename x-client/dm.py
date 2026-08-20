"""
Waguri X/Twitter Client - Direct Message Operations
Send/receive DMs, group DMs, reactions.
"""
from twikit import Client
from auth import get_client


async def send_dm(user_id: str, text: str, media_id: str = None,
                  reply_to: str = None, client: Client = None):
    """Send a direct message to a user."""
    if client is None:
        client = await get_client()
    return await client.send_dm(user_id, text, media_id=media_id, reply_to=reply_to)


async def get_dm_history(user_id: str, max_id: str = None, client: Client = None):
    """Get DM conversation history with a user."""
    if client is None:
        client = await get_client()
    return await client.get_dm_history(user_id, max_id=max_id)


async def delete_dm(message_id: str, client: Client = None):
    """Delete a direct message."""
    if client is None:
        client = await get_client()
    return await client.delete_dm(message_id)


async def send_group_dm(group_id: str, text: str, media_id: str = None,
                        reply_to: str = None, client: Client = None):
    """Send a message to a group DM."""
    if client is None:
        client = await get_client()
    return await client.send_dm_to_group(group_id, text, media_id=media_id, reply_to=reply_to)


async def get_group_dm_history(group_id: str, max_id: str = None, client: Client = None):
    """Get group DM history."""
    if client is None:
        client = await get_client()
    return await client.get_group_dm_history(group_id, max_id=max_id)


async def get_group(group_id: str, client: Client = None):
    """Get group DM info."""
    if client is None:
        client = await get_client()
    return await client.get_group(group_id)


async def change_group_name(group_id: str, name: str, client: Client = None):
    """Change group DM name."""
    if client is None:
        client = await get_client()
    return await client.change_group_name(group_id, name)


async def add_to_group(group_id: str, user_ids: list, client: Client = None):
    """Add users to group DM."""
    if client is None:
        client = await get_client()
    return await client.add_members_to_group(group_id, user_ids)


async def add_reaction(message_id: str, conversation_id: str, emoji: str, client: Client = None):
    """Add emoji reaction to a DM."""
    if client is None:
        client = await get_client()
    return await client.add_reaction_to_message(message_id, conversation_id, emoji)


async def remove_reaction(message_id: str, conversation_id: str, emoji: str, client: Client = None):
    """Remove emoji reaction from a DM."""
    if client is None:
        client = await get_client()
    return await client.remove_reaction_from_message(message_id, conversation_id, emoji)
