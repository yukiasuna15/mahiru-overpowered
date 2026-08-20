"""
Waguri X/Twitter Client - Tweet Operations
Create, delete, edit, retweet, like, bookmark, poll, scheduled tweets.
"""
from twikit import Client
from auth import get_client


async def create_tweet(text: str, reply_to: str = None, media_ids: list = None,
                       community_id: str = None, attachment_url: str = None,
                       is_note_tweet: bool = False, client: Client = None):
    """Post a tweet."""
    if client is None:
        client = await get_client()
    return await client.create_tweet(
        text=text, reply_to=reply_to, media_ids=media_ids,
        community_id=community_id, attachment_url=attachment_url,
        is_note_tweet=is_note_tweet
    )


async def delete_tweet(tweet_id: str, client: Client = None):
    """Delete a tweet by ID."""
    if client is None:
        client = await get_client()
    return await client.delete_tweet(tweet_id)


async def get_tweet(tweet_id: str, client: Client = None):
    """Get a single tweet by ID."""
    if client is None:
        client = await get_client()
    return await client.get_tweet_by_id(tweet_id)


async def get_tweets_by_ids(ids: list, client: Client = None):
    """Get multiple tweets by IDs."""
    if client is None:
        client = await get_client()
    return await client.get_tweets_by_ids(ids)


async def retweet(tweet_id: str, client: Client = None):
    """Retweet a tweet."""
    if client is None:
        client = await get_client()
    return await client.retweet(tweet_id)


async def delete_retweet(tweet_id: str, client: Client = None):
    """Undo a retweet."""
    if client is None:
        client = await get_client()
    return await client.delete_retweet(tweet_id)


async def like(tweet_id: str, client: Client = None):
    """Like a tweet."""
    if client is None:
        client = await get_client()
    return await client.favorite_tweet(tweet_id)


async def unlike(tweet_id: str, client: Client = None):
    """Unlike a tweet."""
    if client is None:
        client = await get_client()
    return await client.unfavorite_tweet(tweet_id)


async def bookmark(tweet_id: str, folder_id: str = None, client: Client = None):
    """Bookmark a tweet."""
    if client is None:
        client = await get_client()
    return await client.bookmark_tweet(tweet_id, folder_id=folder_id)


async def remove_bookmark(tweet_id: str, client: Client = None):
    """Remove a bookmark."""
    if client is None:
        client = await get_client()
    return await client.delete_bookmark(tweet_id)


async def get_bookmarks(count: int = 20, client: Client = None):
    """Get bookmarked tweets."""
    if client is None:
        client = await get_client()
    return await client.get_bookmarks(count=count)


async def create_poll(choices: list, duration_minutes: int, client: Client = None):
    """Create a poll. Returns poll URI for use with create_tweet."""
    if client is None:
        client = await get_client()
    return await client.create_poll(choices, duration_minutes)


async def create_scheduled_tweet(scheduled_at: int, text: str = '',
                                 media_ids: list = None, client: Client = None):
    """Schedule a tweet. scheduled_at is Unix timestamp in seconds."""
    if client is None:
        client = await get_client()
    return await client.create_scheduled_tweet(scheduled_at, text=text, media_ids=media_ids)


async def get_scheduled_tweets(client: Client = None):
    """Get all scheduled tweets."""
    if client is None:
        client = await get_client()
    return await client.get_scheduled_tweets()


async def delete_scheduled_tweet(tweet_id: str, client: Client = None):
    """Delete a scheduled tweet."""
    if client is None:
        client = await get_client()
    return await client.delete_scheduled_tweet(tweet_id)


async def get_retweeters(tweet_id: str, count: int = 40, client: Client = None):
    """Get users who retweeted a tweet."""
    if client is None:
        client = await get_client()
    return await client.get_retweeters(tweet_id, count=count)


async def get_favoriters(tweet_id: str, count: int = 40, client: Client = None):
    """Get users who liked a tweet."""
    if client is None:
        client = await get_client()
    return await client.get_favoriters(tweet_id, count=count)


async def get_similar_tweets(tweet_id: str, client: Client = None):
    """Get similar tweets."""
    if client is None:
        client = await get_client()
    return await client.get_similar_tweets(tweet_id)
