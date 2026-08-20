"""Message translation using Telegram's built-in translator."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def translate_message(client: TelegramClient, entity: str | int, message_id: int, to_lang: str = "en") -> dict:
    """Translate a message using Telegram's built-in translation.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
        message_id: Message ID to translate
        to_lang: Target language code (e.g. 'en', 'es', 'fr', 'de', 'ja')
    
    Returns:
        dict with translation
    """
    msg = await client.get_messages(entity, ids=message_id)
    if not msg or not msg.text:
        return {"error": "Message not found or has no text"}
    
    result = await client(functions.messages.TranslateTextRequest(
        peer=await client.get_input_entity(entity),
        id=[message_id],
        to_lang=to_lang,
    ))
    
    translations = []
    for t in result.result:
        translations.append({
            "text": t.text,
            "language": to_lang,
        })
    
    return {
        "translated": True,
        "original_text": msg.text,
        "translations": translations,
        "target_language": to_lang,
    }
