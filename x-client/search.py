"""
Waguri X/Twitter Client - Search Operations
Search tweets, users, communities, lists.
"""
from twikit import Client
from auth import get_client


async def search_tweets(query: str, product: str = 'Latest', count: int = 20, client: Client = None):
    """Search tweets. product: 'Top', 'Latest', 'Media'."""
    if client is None:
        client = await get_client()
    return await client.search_tweet(query, product, count=count)


async def search_users(query: str, count: int = 20, client: Client = None):
    """Search users."""
    if client is None:
        client = await get_client()
    return await client.search_user(query, count=count)


async def search_communities(query: str, client: Client = None):
    """Search communities."""
    if client is None:
        client = await get_client()
    return await client.search_community(query)


async def search_lists(query: str, count: int = 20, client: Client = None):
    """Search lists."""
    if client is None:
        client = await get_client()
    return await client.search_list(query, count=count)


async def get_trends(category: str = 'trending', count: int = 20, client: Client = None):
    """Get trending topics. category: 'trending', 'for-you', 'news', 'sports', 'entertainment'."""
    if client is None:
        client = await get_client()
    return await client.get_trends(category, count=count)
