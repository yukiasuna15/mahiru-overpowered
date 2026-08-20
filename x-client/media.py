"""
Waguri X/Twitter Client - Media Operations
Upload images, videos, create metadata.
"""
from twikit import Client
from auth import get_client


async def upload_media(source: str, media_type: str = None, media_category: str = None,
                       is_long_video: bool = False, client: Client = None):
    """Upload media (image/video). Returns media_id for use with create_tweet.
    
    Args:
        source: File path or bytes
        media_type: MIME type (e.g. 'image/png', 'video/mp4')
        media_category: 'tweet_image', 'tweet_gif', 'tweet_video', 'amplify_video'
        is_long_video: True for videos > 140s (Premium)
    """
    if client is None:
        client = await get_client()
    return await client.upload_media(
        source, wait_for_completion=True,
        media_type=media_type, media_category=media_category,
        is_long_video=is_long_video
    )


async def check_media_status(media_id: str, is_long_video: bool = False, client: Client = None):
    """Check upload/processing status of media."""
    if client is None:
        client = await get_client()
    return await client.check_media_status(media_id, is_long_video=is_long_video)


async def create_media_metadata(media_id: str, alt_text: str = None,
                                 sensitive_warning: list = None, client: Client = None):
    """Add alt text or sensitivity warning to uploaded media.
    
    Args:
        media_id: ID from upload_media
        alt_text: Accessibility description
        sensitive_warning: ['adult_content', 'graphic_violence', 'other']
    """
    if client is None:
        client = await get_client()
    return await client.create_media_metadata(media_id, alt_text=alt_text,
                                               sensitive_warning=sensitive_warning)
