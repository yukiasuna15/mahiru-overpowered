"""
Discord audit logs module — view and filter audit log entries.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def get_audit_log(
    guild: discord.Guild,
    limit: int = 100,
    before: Optional[discord.AuditLogEntry] = None,
    after: Optional[discord.AuditLogEntry] = None,
    user: Optional[discord.User] = None,
    action: Optional[discord.AuditLogAction] = None,
) -> List[dict]:
    """Get audit log entries with optional filters."""
    kwargs = {"limit": limit}
    if before:
        kwargs["before"] = before
    if after:
        kwargs["after"] = after
    if user:
        kwargs["user"] = user
    if action:
        kwargs["action"] = action

    entries = []
    async for entry in guild.audit_logs(**kwargs):
        entries.append({
            "id": str(entry.id),
            "action": str(entry.action),
            "category": str(entry.action.category) if entry.action.category else None,
            "user": entry.user.name if entry.user else None,
            "target": str(entry.target) if entry.target else None,
            "reason": entry.reason,
            "created_at": str(entry.created_at),
            "changes": [
                {
                    "attr": c.attribute,
                    "type": c.type,
                    "old": str(c.old_value) if c.old_value is not None else None,
                    "new": str(c.new_value) if c.new_value is not None else None,
                }
                for c in entry.changes
            ] if entry.changes else [],
        })
    return entries


async def get_bans(guild: discord.Guild) -> List[dict]:
    """Get all bans in a guild."""
    bans = []
    async for ban_entry in guild.bans():
        bans.append({
            "user_id": str(ban_entry.user.id),
            "username": ban_entry.user.name,
            "reason": ban_entry.reason,
        })
    return bans


async def get_ban(guild: discord.Guild, user: discord.User) -> dict:
    """Get ban info for a specific user."""
    ban_entry = await guild.fetch_ban(user)
    return {
        "user_id": str(ban_entry.user.id),
        "username": ban_entry.user.name,
        "reason": ban_entry.reason,
    }
