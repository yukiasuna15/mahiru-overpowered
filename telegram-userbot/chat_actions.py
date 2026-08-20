"""Typing indicators and chat actions."""

from telethon import TelegramClient
from telethon.tl import types


async def set_typing(client: TelegramClient, entity: str | int, action: str = "typing") -> dict:
    """Set a typing/chat action indicator.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        action: One of 'typing', 'cancel', 'record_video', 'upload_video',
                'record_audio', 'upload_audio', 'upload_photo', 'upload_document',
                'choose_sticker', 'location', 'playing', 'record_round', 'upload_round'
    
    Returns:
        dict with status
    """
    action_map = {
        "typing": types.SendMessageTypingAction(),
        "cancel": types.SendMessageCancelAction(),
        "record_video": types.SendMessageRecordVideoAction(),
        "upload_video": types.SendMessageUploadVideoAction(progress=0),
        "record_audio": types.SendMessageRecordAudioAction(),
        "upload_audio": types.SendMessageUploadAudioAction(progress=0),
        "upload_photo": types.SendMessageUploadPhotoAction(progress=0),
        "upload_document": types.SendMessageUploadDocumentAction(progress=0),
        "choose_sticker": types.SendMessageChooseStickerAction(),
        "location": types.SendMessageGeoLocationAction(),
        "playing": types.SendMessageGamePlayAction(),
        "record_round": types.SendMessageRecordRoundAction(),
        "upload_round": types.SendMessageUploadRoundAction(progress=0),
    }
    if action not in action_map:
        return {"error": f"Unknown action: {action}. Available: {list(action_map.keys())}"}
    
    await client.action(entity, action_map[action])
    return {"set": True, "action": action}


async def send_chat_action(client: TelegramClient, entity: str | int, action: str = "typing") -> dict:
    """Send a chat action (alias for set_typing with broader name).
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        action: Action type string
    
    Returns:
        dict with status
    """
    return await set_typing(client, entity, action)
