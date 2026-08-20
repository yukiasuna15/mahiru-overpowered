"""Stories — post, view, delete, and get stories."""

import os
from telethon import TelegramClient
from telethon.tl import functions, types


async def post_story(client: TelegramClient, media_path: str, caption: str = "", privacy: str = "all") -> dict:
    """Post a story.
    
    Args:
        client: Authenticated Telethon client
        media_path: Path to media file (photo/video)
        caption: Story caption
        privacy: 'all', 'contacts', 'close_friends', or 'selected'
    
    Returns:
        dict with story info
    """
    if not os.path.exists(media_path):
        raise FileNotFoundError(f"File not found: {media_path}")
    
    uploaded = await client.upload_file(media_path)
    
    privacy_rules = {
        "all": types.InputPrivacyValueAllowAll(),
        "contacts": types.InputPrivacyValueAllowContacts(),
        "close_friends": types.InputPrivacyValueAllowCloseFriends(),
    }
    
    media = types.InputMediaUploadedPhoto(file=uploaded)
    result = await client(functions.stories.SendStoryRequest(
        peer="me",
        media=media,
        caption=caption,
        privacy_rules=[privacy_rules.get(privacy, types.InputPrivacyValueAllowAll())],
    ))
    return {"posted": True, "media": os.path.basename(media_path), "caption": caption}


async def view_story(client: TelegramClient, user: str | int, story_id: int) -> dict:
    """View/mark a story as seen.
    
    Args:
        client: Authenticated Telethon client
        user: Story author
        story_id: Story ID
    
    Returns:
        dict with status
    """
    e = await client.get_input_entity(user)
    await client(functions.stories.ReadStoriesRequest(
        peer=e,
        max_id=story_id,
    ))
    return {"viewed": True, "user": str(user), "story_id": story_id}


async def delete_story(client: TelegramClient, story_id: int) -> dict:
    """Delete your own story.
    
    Args:
        client: Authenticated Telethon client
        story_id: Story ID to delete
    
    Returns:
        dict with status
    """
    await client(functions.stories.DeleteStoriesRequest(
        peer="me",
        id=[story_id],
    ))
    return {"deleted": True, "story_id": story_id}


async def get_stories(client: TelegramClient, user: str | int = "me") -> list[dict]:
    """Get stories from a user.
    
    Args:
        client: Authenticated Telethon client
        user: User entity (default: your own stories)
    
    Returns:
        list of story dicts
    """
    e = await client.get_input_entity(user)
    result = await client(functions.stories.GetUserStoriesRequest(peer=e))
    
    stories = []
    if result.stories and result.stories.stories:
        for s in result.stories.stories:
            stories.append({
                "id": s.id,
                "date": str(s.date),
                "expire_date": str(s.expire_date) if s.expire_date else None,
                "caption": s.caption if hasattr(s, "caption") else None,
                "media_type": type(s.media).__name__ if s.media else None,
            })
    return stories
