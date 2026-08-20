"""Chat wallpaper management."""

import os
from telethon import TelegramClient
from telethon.tl import functions, types


async def get_wallpapers(client: TelegramClient) -> list[dict]:
    """Get available wallpapers.
    
    Args:
        client: Authenticated Telethon client
    
    Returns:
        list of wallpaper dicts
    """
    result = await client(functions.account.GetWallPapersRequest(hash=0))
    wallpapers = []
    for w in result.wallpapers:
        wallpapers.append({
            "id": w.id,
            "creator": w.creator if hasattr(w, "creator") else False,
            "pattern": w.pattern if hasattr(w, "pattern") else False,
            "dark": w.dark if hasattr(w, "dark") else False,
            "slug": w.slug if hasattr(w, "slug") else "",
        })
    return wallpapers


async def set_wallpaper(client: TelegramClient, entity: str | int, wallpaper_path: str = None, wallpaper_id: int = None) -> dict:
    """Set chat wallpaper.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        wallpaper_path: Path to custom wallpaper image (optional)
        wallpaper_id: Existing wallpaper ID (optional)
    
    Returns:
        dict with status
    """
    e = await client.get_input_entity(entity)
    
    if wallpaper_path:
        if not os.path.exists(wallpaper_path):
            raise FileNotFoundError(f"File not found: {wallpaper_path}")
        uploaded = await client.upload_file(wallpaper_path)
        result = await client(functions.messages.SetChatWallPaperRequest(
            peer=e,
            wallpaper=types.InputWallPaperUpload(file=uploaded),
        ))
    elif wallpaper_id:
        result = await client(functions.messages.SetChatWallPaperRequest(
            peer=e,
            wallpaper=types.InputWallPaper(id=wallpaper_id, access_hash=0),
        ))
    else:
        return {"error": "Provide either wallpaper_path or wallpaper_id"}
    
    return {"set": True, "entity": str(entity)}
