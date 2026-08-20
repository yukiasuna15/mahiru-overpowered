"""Group and channel management."""

from telethon import TelegramClient, errors
from telethon.tl import functions
from telethon.tl.types import User, Chat, Channel, ChannelParticipantsRecent
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest


async def get_dialogs(client: TelegramClient, limit: int = 50) -> list[dict]:
    """List all dialogs (chats, groups, channels)."""
    dialogs = []
    async for dialog in client.iter_dialogs(limit=limit):
        entity = dialog.entity
        dtype = "user"
        if isinstance(entity, Chat):
            dtype = "group"
        elif isinstance(entity, Channel):
            dtype = "channel" if entity.broadcast else "supergroup"

        dialogs.append({
            "id": dialog.id,
            "name": dialog.name,
            "type": dtype,
            "unread": dialog.unread_count,
            "is_pinned": dialog.pinned,
        })
    return dialogs


async def join_group(client: TelegramClient, invite_link: str) -> dict:
    """Join a group/channel by public @username, t.me link, or private invite link.

    Handles: "@name", "name", "https://t.me/name", "t.me/+HASH",
    "t.me/joinchat/HASH". Idempotent — returns ok if already a member.
    """
    link = invite_link.strip()
    for pre in ("https://", "http://"):
        if link.startswith(pre):
            link = link[len(pre):]
    link = link.removeprefix("t.me/").removeprefix("telegram.me/").lstrip("@")

    # Private invite link → +HASH or joinchat/HASH
    invite_hash = None
    if link.startswith("+"):
        invite_hash = link[1:]
    elif link.startswith("joinchat/"):
        invite_hash = link[len("joinchat/"):]

    try:
        if invite_hash is not None:
            try:
                res = await client(functions.messages.ImportChatInviteRequest(invite_hash))
                chat = res.chats[0] if getattr(res, "chats", None) else None
                return {"joined": True, "title": getattr(chat, "title", "Unknown"),
                        "id": getattr(chat, "id", None)}
            except errors.UserAlreadyParticipantError:
                return {"joined": True, "already_member": True}
        else:
            # Public channel/group by username (drop any trailing path/query)
            username = link.split("/")[0].split("?")[0]
            entity = await client.get_entity(username)
            try:
                await client(functions.channels.JoinChannelRequest(entity))
            except errors.UserAlreadyParticipantError:
                return {"joined": True, "already_member": True,
                        "title": getattr(entity, "title", username), "id": entity.id}
            return {"joined": True,
                    "title": getattr(entity, "title", getattr(entity, "username", username)),
                    "id": entity.id}
    except Exception as e:
        return {"joined": False, "error": f"{type(e).__name__}: {e}"}


async def join_public_channel(client: TelegramClient, username: str) -> dict:
    """Join a public channel/group by username."""
    entity = await client.get_entity(username)
    await client(functions.channels.JoinChannelRequest(entity))
    return {"joined": True, "title": entity.title, "id": entity.id}


async def get_group_members(client: TelegramClient, entity: str | int, limit: int = 100) -> list[dict]:
    """Get members of a group/supergroup."""
    members = []
    async for user in client.iter_participants(entity, limit=limit):
        members.append({
            "id": user.id,
            "name": (user.first_name or "") + (" " + user.last_name if user.last_name else ""),
            "username": user.username,
            "is_bot": user.bot,
            "is_premium": user.premium,
        })
    return members


async def get_group_info(client: TelegramClient, entity: str | int) -> dict:
    """Get detailed info about a group/channel."""
    e = await client.get_entity(entity)
    full = await client(GetFullChannelRequest(e) if isinstance(e, Channel) else GetFullChatRequest(e))
    return {
        "id": e.id,
        "title": e.title if hasattr(e, "title") else "DM",
        "username": getattr(e, "username", None),
        "participants_count": full.full_chat.participants_count if hasattr(full.full_chat, "participants_count") else None,
        "about": getattr(full.full_chat, "about", None),
        "is_channel": isinstance(e, Channel) and e.broadcast,
    }


async def leave_group(client: TelegramClient, entity: str | int) -> bool:
    """Leave a group/channel."""
    e = await client.get_entity(entity)
    if isinstance(e, Channel):
        await client(functions.channels.LeaveChannelRequest(e))
    else:
        await client(functions.messages.DeleteChatUserRequest(e.id, "me"))
    return True


async def invite_to_group(client: TelegramClient, entity: str | int, user: str | int) -> bool:
    """Invite a user to a group/channel."""
    e = await client.get_entity(entity)
    u = await client.get_entity(user)
    if isinstance(e, Channel):
        await client(functions.channels.InviteToChannelRequest(e, [u]))
    else:
        await client(functions.messages.AddChatUserRequest(e.id, u, fwd_limit=0))
    return True

