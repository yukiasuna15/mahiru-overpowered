"""
Waguri X/Twitter Client - List Operations
Create, edit, manage lists and list members.
"""
from twikit import Client
from auth import get_client


async def get_lists(count: int = 100, client: Client = None):
    """Get own lists."""
    if client is None:
        client = await get_client()
    return await client.get_lists(count=count)


async def get_list(list_id: str, client: Client = None):
    """Get list info."""
    if client is None:
        client = await get_client()
    return await client.get_list(list_id)


async def create_list(name: str, description: str = '', is_private: bool = False, client: Client = None):
    """Create a new list."""
    if client is None:
        client = await get_client()
    return await client.create_list(name, description=description, is_private=is_private)


async def edit_list(list_id: str, name: str = None, description: str = None,
                    is_private: bool = None, client: Client = None):
    """Edit list properties."""
    if client is None:
        client = await get_client()
    return await client.edit_list(list_id, name=name, description=description, is_private=is_private)


async def get_list_tweets(list_id: str, count: int = 20, client: Client = None):
    """Get tweets from a list."""
    if client is None:
        client = await get_client()
    return await client.get_list_tweets(list_id, count=count)


async def get_list_members(list_id: str, count: int = 20, client: Client = None):
    """Get list members."""
    if client is None:
        client = await get_client()
    return await client.get_list_members(list_id, count=count)


async def add_list_member(list_id: str, user_id: str, client: Client = None):
    """Add a user to a list."""
    if client is None:
        client = await get_client()
    return await client.add_list_member(list_id, user_id)


async def remove_list_member(list_id: str, user_id: str, client: Client = None):
    """Remove a user from a list."""
    if client is None:
        client = await get_client()
    return await client.remove_list_member(list_id, user_id)
