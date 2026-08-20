"""Payments and invoices.

Note: send_invoice is a bot-only API (requires bot token) and is not usable
from a userbot. It is kept here for reference only.
"""

from telethon import TelegramClient
from telethon.tl import functions, types


async def get_payments(client: TelegramClient, entity: str | int = None, message_id: int = None) -> dict:
    """Get payment form for a specific invoice message.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity containing the invoice message
        message_id: Message ID of the invoice message
    
    Returns:
        dict with payment form info or error
    """
    if entity is None or message_id is None:
        return {"error": "Both entity and message_id are required to fetch a payment form"}
    
    try:
        peer = await client.get_input_entity(entity)
        result = await client(functions.payments.GetPaymentFormRequest(
            msg_id=message_id,
            theme_params=None,
        ))
        return {
            "payment_form_id": getattr(result, 'form_id', None),
            "bot_id": getattr(result, 'bot_id', None),
            "invoice": getattr(result, 'invoice', None),
            "provider_id": getattr(result, 'provider_id', None),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
