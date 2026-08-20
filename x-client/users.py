"""
Waguri X/Twitter Client - User Operations
Follow, unfollow, block, mute, get user tweets/followers/following.
"""
from twikit import Client
from auth import get_client


async def follow(user_id: str, client: Client = None):
    """Follow a user."""
    if client is None:
        client = await get_client()
    return await client.follow_user(user_id)


async def unfollow(user_id: str, client: Client = None):
    """Unfollow a user."""
    if client is None:
        client = await get_client()
    return await client.unfollow_user(user_id)


async def block(user_id: str, client: Client = None):
    """Block a user."""
    if client is None:
        client = await get_client()
    return await client.block_user(user_id)


async def unblock(user_id: str, client: Client = None):
    """Unblock a user."""
    if client is None:
        client = await get_client()
    return await client.unblock_user(user_id)


async def mute(user_id: str, client: Client = None):
    """Mute a user."""
    if client is None:
        client = await get_client()
    return await client.mute_user(user_id)


async def unmute(user_id: str, client: Client = None):
    """Unmute a user."""
    if client is None:
        client = await get_client()
    return await client.unmute_user(user_id)


async def get_user_tweets(user_id: str, tweet_type: str = 'Tweets', count: int = 20, client: Client = None):
    """Get user's tweets. tweet_type: 'Tweets', 'Replies', 'Media', 'Likes'."""
    if client is None:
        client = await get_client()
    return await client.get_user_tweets(user_id, tweet_type, count=count)


async def get_followers(user_id: str, count: int = 20, client: Client = None):
    """Get user's followers."""
    if client is None:
        client = await get_client()
    return await client.get_user_followers(user_id, count=count)


async def get_following(user_id: str, count: int = 20, client: Client = None):
    """Get who user is following."""
    if client is None:
        client = await get_client()
    return await client.get_user_following(user_id, count=count)


async def get_followers_ids(user_id: str, count: int = 5000, client: Client = None):
    """Get follower IDs (fast, no profile data)."""
    if client is None:
        client = await get_client()
    return await client.get_followers_ids(user_id, count=count)


async def get_following_ids(user_id: str, count: int = 5000, client: Client = None):
    """Get following IDs (fast, no profile data)."""
    if client is None:
        client = await get_client()
    return await client.get_friends_ids(user_id, count=count)


async def get_verified_followers(user_id: str, count: int = 20, client: Client = None):
    """Get verified followers."""
    if client is None:
        client = await get_client()
    return await client.get_user_verified_followers(user_id, count=count)


async def get_highlights(user_id: str, count: int = 20, client: Client = None):
    """Get user's highlight tweets."""
    if client is None:
        client = await get_client()
    return await client.get_user_highlights_tweets(user_id, count=count)


async def get_subscriptions(user_id: str, count: int = 20, client: Client = None):
    """Get user's subscriptions (Premium)."""
    if client is None:
        client = await get_client()
    return await client.get_user_subscriptions(user_id, count=count)
