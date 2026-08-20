"""User info and profile operations."""

from telethon import TelegramClient


async def get_me(client: TelegramClient) -> dict:
    """Get current user info."""
    me = await client.get_me()
    return {
        "id": me.id,
        "first_name": me.first_name,
        "last_name": me.last_name,
        "username": me.username,
        "phone": me.phone,
        "is_premium": me.premium,
        "lang_code": me.lang_code,
    }


async def get_user(client: TelegramClient, user: str | int) -> dict:
    """Get info about a user by username or ID."""
    entity = await client.get_entity(user)
    if not hasattr(entity, "first_name"):
        raise ValueError("Entity is not a user")
    return {
        "id": entity.id,
        "first_name": entity.first_name,
        "last_name": entity.last_name,
        "username": entity.username,
        "is_bot": entity.bot,
        "is_premium": entity.premium,
        "lang_code": entity.lang_code,
    }


async def search_users(client: TelegramClient, query: str, limit: int = 10) -> list[dict]:
    """Search for users by name/username."""
    results = []
    async for user in client.iter_participants(query, limit=limit, search=query):
        results.append({
            "id": user.id,
            "name": (user.first_name or "") + (" " + user.last_name if user.last_name else ""),
            "username": user.username,
            "is_bot": user.bot,
        })
    return results


async def block_user(client: TelegramClient, user: str | int) -> bool:
    """Block a user."""
    entity = await client.get_entity(user)
    await client(functions.contacts.BlockRequest(entity))
    return True


async def unblock_user(client: TelegramClient, user: str | int) -> bool:
    """Unblock a user."""
    entity = await client.get_entity(user)
    await client(functions.contacts.UnblockRequest(entity))
    return True


from telethon.tl import functions
