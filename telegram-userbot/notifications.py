"""Notification settings — mute/unmute chats."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def mute_chat(client: TelegramClient, entity: str | int, mute_until: int = None) -> dict:
    """Mute notifications for a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        mute_until: Unix timestamp to mute until (None = mute forever, 0 = unmute)
    
    Returns:
        dict with status
    """
    if mute_until is None:
        mute_until = 2**31 - 1  # effectively forever
    
    await client(functions.account.UpdateNotifySettingsRequest(
        peer=types.InputNotifyPeer(peer=await client.get_input_entity(entity)),
        settings=types.InputPeerNotifySettings(
            mute_until=mute_until,
        ),
    ))
    return {"muted": True, "entity": str(entity), "mute_until": mute_until}


async def unmute_chat(client: TelegramClient, entity: str | int) -> dict:
    """Unmute notifications for a chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
    
    Returns:
        dict with status
    """
    await client(functions.account.UpdateNotifySettingsRequest(
        peer=types.InputNotifyPeer(peer=await client.get_input_entity(entity)),
        settings=types.InputPeerNotifySettings(
            mute_until=0,
        ),
    ))
    return {"unmuted": True, "entity": str(entity)}


async def get_notification_settings(client: TelegramClient, entity: str | int = None) -> dict | list[dict]:
    """Get notification settings for a chat or all chats.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity (None for all settings)
    
    Returns:
        dict or list of dicts with notification settings
    """
    if entity:
        e = await client.get_input_entity(entity)
        result = await client(functions.account.GetNotifySettingsRequest(
            peer=types.InputNotifyPeer(peer=e),
        ))
        return {
            "entity": str(entity),
            "mute_until": result.mute_until,
            "silent": result.silent,
            "show_previews": result.show_previews,
        }
    
    # Get peer notification settings (all muted chats)
    result = await client(functions.account.GetGlobalPrivacySettingsRequest())
    return {
        "archive_and_mute_new_noncontact_peers": result.archive_and_mute_new_noncontact_peers if hasattr(result, "archive_and_mute_new_noncontact_peers") else None,
    }
