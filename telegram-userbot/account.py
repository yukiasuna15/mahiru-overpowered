"""Account management — password, authorizations, deletion."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def update_password(client: TelegramClient, current_password: str, new_password: str) -> dict:
    """Update 2FA password.
    
    Args:
        client: Authenticated Telethon client
        current_password: Current password (empty string if none)
        new_password: New password
    
    Returns:
        dict with status
    """
    if current_password:
        # Get password info first for SRP
        password_info = await client(functions.account.GetPasswordRequest())
        # Use Telethon's built-in password handling
        result = await client.edit_2fa(current_password=current_password, new_password=new_password)
    else:
        result = await client.edit_2fa(new_password=new_password)
    return {"updated": True}


async def get_password(client: TelegramClient) -> dict:
    """Get 2FA password settings.
    
    Args:
        client: Authenticated Telethon client
    
    Returns:
        dict with password settings
    """
    result = await client(functions.account.GetPasswordRequest())
    return {
        "has_password": result.has_password,
        "hint": result.hint,
        "has_recovery": result.has_recovery,
        "unconfirmed_email_pattern": result.unconfirmed_email_pattern,
    }


async def delete_account(client: TelegramClient, reason: str = "") -> dict:
    """Delete Telegram account.
    
    Args:
        client: Authenticated Telethon client
        reason: Deletion reason
    
    Returns:
        dict with status
    
    WARNING: This is irreversible!
    """
    result = await client(functions.account.DeleteAccountRequest(reason=reason))
    return {"deleted": True, "result": str(result)}


async def get_authorizations(client: TelegramClient) -> list[dict]:
    """Get all active authorizations/sessions.
    
    Args:
        client: Authenticated Telethon client
    
    Returns:
        list of authorization dicts
    """
    result = await client(functions.account.GetAuthorizationsRequest())
    auths = []
    for auth in result.authorizations:
        auths.append({
            "hash": auth.hash,
            "device_model": auth.device_model,
            "platform": auth.platform,
            "system_version": auth.system_version,
            "api_id": auth.api_id,
            "app_name": auth.app_name,
            "app_version": auth.app_version,
            "date_created": str(auth.date_created),
            "date_active": str(auth.date_active),
            "ip": auth.ip,
            "country": auth.country,
            "region": auth.region,
            "is_current": auth.current,
        })
    return auths


async def reset_authorizations(client: TelegramClient) -> dict:
    """Terminate all other sessions.
    
    Args:
        client: Authenticated Telethon client
    
    Returns:
        dict with status
    """
    result = await client(functions.account.ResetAuthorizationRequest(hash=0))
    return {"reset": True, "result": result}
