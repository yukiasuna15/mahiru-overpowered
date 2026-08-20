"""Stickers — send, get, create sticker sets."""

import os
from telethon import TelegramClient
from telethon.tl import functions, types


async def send_sticker(client: TelegramClient, entity: str | int, sticker_path: str) -> dict:
    """Send a sticker (.webp file or sticker document).
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        sticker_path: Path to .webp sticker file
    
    Returns:
        dict with sent message info
    """
    if not os.path.exists(sticker_path):
        raise FileNotFoundError(f"File not found: {sticker_path}")
    result = await client.send_file(entity, sticker_path, force_document=False)
    return {"sent": True, "id": result.id, "file": os.path.basename(sticker_path)}


async def get_stickers(client: TelegramClient, emoji: str = "😀") -> list[dict]:
    """Get sticker suggestions for an emoji.
    
    Args:
        client: Authenticated Telethon client
        emoji: Emoji to get sticker suggestions for
    
    Returns:
        list of sticker set dicts
    """
    result = await client(functions.messages.GetStickerSetRequest(
        stickerset=types.InputStickerSetShortName(short_name=""),
        hash=0,
    ))
    # Use search instead
    result = await client(functions.messages.SearchStickerSetsRequest(
        q=emoji,
        hash=0,
    ))
    stickers = []
    for s in result.sets:
        stickers.append({
            "id": s.id,
            "title": s.title,
            "short_name": s.short_name,
            "count": s.count,
            "installed": s.installed_date is not None if hasattr(s, "installed_date") else False,
        })
    return stickers


async def create_sticker_set(
    client: TelegramClient,
    title: str,
    short_name: str,
    stickers: list[dict],
) -> dict:
    """Create a new sticker set.
    
    Args:
        client: Authenticated Telethon client
        title: Sticker set title
        short_name: URL-friendly short name
        stickers: List of sticker dicts with 'path' and 'emoji' keys
    
    Returns:
        dict with sticker set info
    """
    me = await client.get_me()
    input_stickers = []
    for s in stickers:
        if not os.path.exists(s["path"]):
            raise FileNotFoundError(f"File not found: {s['path']}")
        uploaded = await client.upload_file(s["path"])
        input_stickers.append(types.InputStickerSetItem(
            document=types.InputDocument(
                id=0,
                access_hash=0,
                file_reference=b"",
            ),
            emoji=s["emoji"],
        ))
    
    # Upload documents first
    input_docs = []
    for s in stickers:
        file = await client.upload_file(s["path"])
        doc = await client(functions.messages.UploadMediaRequest(
            peer="me",
            media=types.InputMediaUploadedDocument(
                file=file,
                mime_type="image/webp",
                attributes=[],
            ),
        ))
        input_docs.append(types.InputStickerSetItem(
            document=doc.document,
            emoji=s["emoji"],
        ))
    
    result = await client(functions.stickers.CreateStickerSetRequest(
        user_id=await client.get_input_entity(me),
        title=title,
        short_name=short_name,
        stickers=input_docs,
    ))
    return {
        "created": True,
        "title": title,
        "short_name": short_name,
        "id": result.set.id if result.set else None,
    }
