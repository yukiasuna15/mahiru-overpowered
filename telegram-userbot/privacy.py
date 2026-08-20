"""Privacy settings management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def get_privacy(client: TelegramClient, key: str = "status") -> dict:
    """Get privacy setting for a specific key.
    
    Args:
        client: Authenticated Telethon client
        key: Privacy key - 'status', 'chat_invite', 'phone_call', 'phone_number',
             'forwards', 'profile_photo', 'phone_number_privacy'
    
    Returns:
        dict with privacy settings
    """
    key_map = {
        "status": types.InputPrivacyKeyStatusTimestamp(),
        "chat_invite": types.InputPrivacyKeyChatInvite(),
        "phone_call": types.InputPrivacyKeyPhoneCall(),
        "phone_number": types.InputPrivacyKeyPhoneNumber(),
        "forwards": types.InputPrivacyKeyForwards(),
        "profile_photo": types.InputPrivacyKeyProfilePhoto(),
    }
    
    if key not in key_map:
        return {"error": f"Unknown key: {key}. Available: {list(key_map.keys())}"}
    
    result = await client(functions.account.GetPrivacyRequest(key=key_map[key]))
    
    rules = []
    for rule in result.rules:
        rule_type = type(rule).__name__
        allow = "allow" in rule_type.lower()
        rules.append({
            "type": rule_type,
            "allow": "Allow" in rule_type,
            "users": [u.user_id for u in rule.users] if hasattr(rule, "users") else [],
        })
    
    return {"key": key, "rules": rules, "users": [{"id": u.id, "username": u.username} for u in result.users]}


async def set_privacy(client: TelegramClient, key: str, rules: list[dict]) -> dict:
    """Set privacy rules for a key.
    
    Args:
        client: Authenticated Telethon client
        key: Privacy key name
        rules: List of rule dicts, e.g. [{"type": "allow_all"}, {"type": "disallow_contacts"}]
    
    Returns:
        dict with status
    """
    key_map = {
        "status": types.InputPrivacyKeyStatusTimestamp(),
        "chat_invite": types.InputPrivacyKeyChatInvite(),
        "phone_call": types.InputPrivacyKeyPhoneCall(),
        "phone_number": types.InputPrivacyKeyPhoneNumber(),
        "forwards": types.InputPrivacyKeyForwards(),
        "profile_photo": types.InputPrivacyKeyProfilePhoto(),
    }
    
    if key not in key_map:
        return {"error": f"Unknown key: {key}"}
    
    rule_map = {
        "allow_all": types.InputPrivacyValueAllowAll(),
        "disallow_all": types.InputPrivacyValueDisallowAll(),
        "allow_contacts": types.InputPrivacyValueAllowContacts(),
        "disallow_contacts": types.InputPrivacyValueDisallowContacts(),
        "allow_premium": types.InputPrivacyValueAllowPremium(),
        "allow_close_friends": types.InputPrivacyValueAllowCloseFriends(),
    }
    
    privacy_rules = []
    for r in rules:
        rtype = r.get("type", "")
        if rtype in rule_map:
            privacy_rules.append(rule_map[rtype])
        elif rtype == "allow_users":
            users = [await client.get_input_entity(u) for u in r.get("users", [])]
            privacy_rules.append(types.InputPrivacyValueAllowUsers(users=users))
        elif rtype == "disallow_users":
            users = [await client.get_input_entity(u) for u in r.get("users", [])]
            privacy_rules.append(types.InputPrivacyValueDisallowUsers(users=users))
    
    result = await client(functions.account.SetPrivacyRequest(
        key=key_map[key],
        rules=privacy_rules,
    ))
    return {"set": True, "key": key, "rules_count": len(privacy_rules)}


async def get_blocked(client: TelegramClient, limit: int = 100) -> list[dict]:
    """Get list of blocked users.
    
    Args:
        client: Authenticated Telethon client
        limit: Max results
    
    Returns:
        list of blocked user dicts
    """
    result = await client(functions.contacts.GetBlockedRequest(
        offset=0,
        limit=limit,
    ))
    blocked = []
    for user in result.users:
        blocked.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone": user.phone,
        })
    return blocked
