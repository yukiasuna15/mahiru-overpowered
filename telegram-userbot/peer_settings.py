"""Peer settings and reporting."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def get_peer_settings(client: TelegramClient, entity: str | int) -> dict:
    """Get peer-specific settings (spam protection, etc.).
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity
    
    Returns:
        dict with peer settings
    """
    e = await client.get_input_entity(entity)
    result = await client(functions.messages.GetPeerSettingsRequest(peer=e))
    
    settings = result.settings if hasattr(result, "settings") else result
    return {
        "entity": str(entity),
        "report_spam": getattr(settings, "report_spam", None),
        "add_contact": getattr(settings, "add_contact", None),
        "block_contact": getattr(settings, "block_contact", None),
        "share_contact": getattr(settings, "share_contact", None),
        "need_contacts_exception": getattr(settings, "need_contacts_exception", None),
        "report_geo": getattr(settings, "report_geo", None),
        "autoarchived": getattr(settings, "autoarchived", None),
        "geo_distance": getattr(settings, "geo_distance", None),
        "request_chat_title": getattr(settings, "request_chat_title", None),
        "request_chat_date": str(settings.request_chat_date) if hasattr(settings, "request_chat_date") and settings.request_chat_date else None,
    }


async def report_peer(client: TelegramClient, entity: str | int, reason: str = "spam", message: str = "") -> dict:
    """Report a user/chat.
    
    Args:
        client: Authenticated Telethon client
        entity: Chat entity to report
        reason: 'spam', 'violence', 'pornography', 'child_abuse', 'copyright',
                'illegal_drugs', 'personal_details', 'other'
        message: Additional details
    
    Returns:
        dict with report status
    """
    e = await client.get_input_entity(entity)
    
    reason_map = {
        "spam": types.InputReportReasonSpam(),
        "violence": types.InputReportReasonViolence(),
        "pornography": types.InputReportReasonPornography(),
        "child_abuse": types.InputReportReasonChildAbuse(),
        "copyright": types.InputReportReasonCopyright(),
        "illegal_drugs": types.InputReportReasonIllegalDrugs(),
        "personal_details": types.InputReportReasonPersonalDetails(),
        "other": types.InputReportReasonOther(text=message),
    }
    
    report_reason = reason_map.get(reason, types.InputReportReasonSpam())
    
    await client(functions.messages.ReportRequest(
        peer=e,
        id=[],
        reason=report_reason,
        message=message,
    ))
    return {"reported": True, "entity": str(entity), "reason": reason}
