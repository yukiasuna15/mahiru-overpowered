"""
Waguri X/Twitter Client - Timeline & Notifications
Home timeline, notifications.
"""
from twikit import Client
from auth import get_client


async def get_home_timeline(count: int = 20, client: Client = None):
    """Get home timeline (For You)."""
    if client is None:
        client = await get_client()
    return await client.get_timeline(count=count)


async def get_latest_timeline(count: int = 20, client: Client = None):
    """Get home timeline (Following)."""
    if client is None:
        client = await get_client()
    return await client.get_latest_timeline(count=count)


async def get_notifications(type: str = 'All', count: int = 40, client: Client = None):
    """Get notifications. type: 'All', 'Verified', 'Mentions'."""
    if client is None:
        client = await get_client()
    return await client.get_notifications(type, count=count)
