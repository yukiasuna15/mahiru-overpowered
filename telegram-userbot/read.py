"""Mark messages as read/unread and folder management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def mark_read(client: TelegramClient, entity: str | int, message_id: int = None) -> dict:
    """Mark messages as read up to a specific message or all.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Mark read up to this message ID (None for all)
    
    Returns:
        dict with status
    """
    if message_id:
        await client(functions.messages.ReadHistoryRequest(
            peer=entity,
            max_id=message_id + 1,
        ))
    else:
        await client.send_read_acknowledge(entity)
    return {"marked_read": True, "entity": str(entity), "up_to": message_id}


async def mark_unread(client: TelegramClient, entity: str | int) -> dict:
    """Mark a chat as unread.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
    
    Returns:
        dict with status
    """
    e = await client.get_input_entity(entity)
    await client(functions.messages.MarkDialogUnreadRequest(
        peer=e,
        unread=True,
    ))
    return {"marked_unread": True, "entity": str(entity)}


async def set_folder(client: TelegramClient, entity: str | int, folder_id: int) -> dict:
    """Move a chat to a specific folder.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        folder_id: Folder ID to move to
    
    Returns:
        dict with status
    """
    e = await client.get_input_entity(entity)
    await client(functions.messages.ToggleDialogPinRequest(
        peer=e,
        pinned=False,
    ))
    await client(functions.folders.EditPeerFoldersRequest(
        folder_peers=[types.InputFolderPeer(
            peer=e,
            folder_id=folder_id,
        )]
    ))
    return {"moved": True, "entity": str(entity), "folder_id": folder_id}
