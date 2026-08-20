"""Profile management — name, bio, avatar, username."""

import os
from telethon import TelegramClient
from telethon.tl import functions


async def update_name(client: TelegramClient, first_name: str = None, last_name: str = None) -> dict:
    """Update profile name.
    
    Args:
        client: Authenticated Telethon client
        first_name: New first name (None to keep current)
        last_name: New last name (None to keep current)
    
    Returns:
        dict with updated profile info
    """
    me = await client.get_me()
    result = await client(functions.account.UpdateProfileRequest(
        first_name=first_name if first_name is not None else (me.first_name or ""),
        last_name=last_name if last_name is not None else (me.last_name or ""),
    ))
    return {
        "updated": True,
        "first_name": result.first_name,
        "last_name": result.last_name,
    }


async def update_bio(client: TelegramClient, bio: str) -> dict:
    """Update profile bio/about.
    
    Args:
        client: Authenticated Telethon client
        bio: New bio text (max 70 chars for users)
    
    Returns:
        dict with status
    """
    result = await client(functions.account.UpdateProfileRequest(about=bio))
    return {"updated": True, "bio": bio}


async def update_avatar(client: TelegramClient, photo_path: str) -> dict:
    """Update profile photo.
    
    Args:
        client: Authenticated Telethon client
        photo_path: Path to photo file
    
    Returns:
        dict with status
    """
    if not os.path.exists(photo_path):
        raise FileNotFoundError(f"File not found: {photo_path}")
    result = await client(functions.photos.UploadProfilePhotoRequest(
        file=await client.upload_file(photo_path)
    ))
    return {"updated": True, "photo": photo_path, "photo_id": result.photo.id if result.photo else None}


async def update_username(client: TelegramClient, username: str) -> dict:
    """Update profile username.
    
    Args:
        client: Authenticated Telethon client
        username: New username (without @)
    
    Returns:
        dict with status
    """
    result = await client(functions.account.UpdateUsernameRequest(username=username))
    return {"updated": True, "username": result.username}


async def get_profile(client: TelegramClient) -> dict:
    """Get full profile info.
    
    Args:
        client: Authenticated Telethon client
    
    Returns:
        dict with full profile info
    """
    me = await client.get_me()
    full = await client(functions.users.GetFullUserRequest(id=me.id))
    return {
        "id": me.id,
        "first_name": me.first_name,
        "last_name": me.last_name,
        "username": me.username,
        "phone": me.phone,
        "is_premium": me.premium,
        "bio": full.full_user.about,
        "common_chats_count": full.full_user.common_chats_count,
        "profile_photo": full.full_user.profile_photo.id if full.full_user.profile_photo else None,
    }
