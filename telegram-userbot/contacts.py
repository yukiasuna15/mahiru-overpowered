"""Contacts management."""

from telethon import TelegramClient
from telethon.tl import functions, types


async def add_contact(client: TelegramClient, user: str | int, first_name: str = "", last_name: str = "") -> dict:
    """Add a user to contacts.
    
    Args:
        client: Authenticated Telethon client
        user: User entity
        first_name: Contact first name
        last_name: Contact last name
    
    Returns:
        dict with status
    """
    entity = await client.get_input_entity(user)
    result = await client(functions.contacts.AddContactRequest(
        id=entity,
        first_name=first_name,
        last_name=last_name,
        phone="",
    ))
    return {"added": True, "user": str(user)}


async def delete_contact(client: TelegramClient, user: str | int) -> dict:
    """Delete a user from contacts.
    
    Args:
        client: Authenticated Telethon client
        user: User entity
    
    Returns:
        dict with status
    """
    entity = await client.get_input_entity(user)
    result = await client(functions.contacts.DeleteContactsRequest(id=[entity]))
    return {"deleted": True, "user": str(user)}


async def get_contacts(client: TelegramClient) -> list[dict]:
    """Get all contacts.
    
    Args:
        client: Authenticated Telethon client
    
    Returns:
        list of contact dicts
    """
    result = await client(functions.contacts.GetContactsRequest(hash=0))
    contacts = []
    for user in result.users:
        contacts.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone": user.phone,
            "is_bot": user.bot,
            "is_premium": user.premium,
        })
    return contacts


async def import_contacts(client: TelegramClient, contacts_list: list[dict]) -> dict:
    """Import contacts from a list.
    
    Args:
        client: Authenticated Telethon client
        contacts_list: List of contact dicts with 'phone', 'first_name', 'last_name'
    
    Returns:
        dict with import results
    """
    input_contacts = []
    for i, c in enumerate(contacts_list):
        input_contacts.append(types.InputPhoneContact(
            client_id=i,
            phone=c["phone"],
            first_name=c.get("first_name", ""),
            last_name=c.get("last_name", ""),
        ))
    
    result = await client(functions.contacts.ImportContactsRequest(contacts=input_contacts))
    imported = []
    for u in result.users:
        imported.append({
            "id": u.id,
            "first_name": u.first_name,
            "username": u.username,
        })
    return {"imported": len(imported), "users": imported}
