"""Chat folders/filters management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def create_folder(client: TelegramClient, title: str, pinned_peers: list = None, include_peers: list = None, exclude_peers: list = None) -> dict:
    """Create a new chat folder.
    
    Args:
        client: Authenticated Telethon client
        title: Folder title
        pinned_peers: List of entities to pin in folder
        include_peers: List of entities to include
        exclude_peers: List of entities to exclude
    
    Returns:
        dict with folder info
    """
    pinned = []
    if pinned_peers:
        for p in pinned_peers:
            pinned.append(await client.get_input_entity(p))
    
    included = []
    if include_peers:
        for p in include_peers:
            included.append(await client.get_input_entity(p))
    
    excluded = []
    if exclude_peers:
        for p in exclude_peers:
            excluded.append(await client.get_input_entity(p))
    
    result = await client(functions.messages.UpdateDialogFilterRequest(
        id=0,
        filter=types.DialogFilter(
            id=0,
            title=title,
            pinned_peers=pinned,
            include_peers=included,
            exclude_peers=excluded,
        ),
    ))
    return {"created": True, "title": title}


async def edit_folder(client: TelegramClient, folder_id: int, title: str = None, pinned_peers: list = None, include_peers: list = None, exclude_peers: list = None) -> dict:
    """Edit an existing chat folder.
    
    Args:
        client: Authenticated Telethon client
        folder_id: Folder ID to edit
        title: New folder title
        pinned_peers: New pinned peers list
        include_peers: New included peers list
        exclude_peers: New excluded peers list
    
    Returns:
        dict with status
    """
    # Get existing folders
    result = await client(functions.messages.GetDialogFiltersRequest())
    existing = None
    for f in result.filters:
        if hasattr(f, "id") and f.id == folder_id:
            existing = f
            break
    
    if not existing:
        return {"error": f"Folder {folder_id} not found"}
    
    pinned = []
    if pinned_peers:
        for p in pinned_peers:
            pinned.append(await client.get_input_entity(p))
    else:
        pinned = existing.pinned_peers if hasattr(existing, "pinned_peers") else []
    
    included = []
    if include_peers:
        for p in include_peers:
            included.append(await client.get_input_entity(p))
    else:
        included = existing.include_peers if hasattr(existing, "include_peers") else []
    
    excluded = []
    if exclude_peers:
        for p in exclude_peers:
            excluded.append(await client.get_input_entity(p))
    else:
        excluded = existing.exclude_peers if hasattr(existing, "exclude_peers") else []
    
    await client(functions.messages.UpdateDialogFilterRequest(
        id=folder_id,
        filter=types.DialogFilter(
            id=folder_id,
            title=title or existing.title,
            pinned_peers=pinned,
            include_peers=included,
            exclude_peers=excluded,
        ),
    ))
    return {"edited": True, "folder_id": folder_id}


async def delete_folder(client: TelegramClient, folder_id: int) -> dict:
    """Delete a chat folder.
    
    Args:
        client: Authenticated Telethon client
        folder_id: Folder ID to delete
    
    Returns:
        dict with status
    """
    await client(functions.messages.UpdateDialogFilterRequest(
        id=folder_id,
        filter=None,
    ))
    return {"deleted": True, "folder_id": folder_id}


async def get_folders(client: TelegramClient) -> list[dict]:
    """Get all chat folders.
    
    Args:
        client: Authenticated Telethon client
    
    Returns:
        list of folder dicts
    """
    result = await client(functions.messages.GetDialogFiltersRequest())
    folders = []
    for f in result.filters:
        folder = {
            "id": f.id if hasattr(f, "id") else 0,
            "title": f.title if hasattr(f, "title") else "All Chats",
            "has_peers": len(f.include_peers) if hasattr(f, "include_peers") else 0,
            "excluded_peers": len(f.exclude_peers) if hasattr(f, "exclude_peers") else 0,
        }
        folders.append(folder)
    return folders
