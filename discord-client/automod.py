"""
Discord AutoMod module — create, edit, delete automod rules.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def get_automod_rules(guild: discord.Guild) -> List[dict]:
    """List all AutoMod rules in a guild."""
    rules = await guild.automod_rules()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "creator": r.creator.name if r.creator else None,
            "event_type": str(r.event_type),
            "trigger_type": str(r.trigger_type),
            "enabled": r.enabled,
            "actions": [
                {"type": str(a.type), "channel_id": str(a.channel_id) if hasattr(a, "channel_id") and a.channel_id else None}
                for a in r.actions
            ],
        }
        for r in rules
    ]


async def create_automod_rule(
    guild: discord.Guild,
    name: str,
    event_type: discord.AutoModEventType,
    trigger_type: discord.AutoModTriggerType,
    actions: List[discord.AutoModRuleAction],
    trigger_metadata: Optional[discord.AutoModTriggerMetadata] = None,
    enabled: bool = True,
    exempt_roles: Optional[List[discord.Role]] = None,
    exempt_channels: Optional[List[discord.TextChannel]] = None,
    reason: Optional[str] = None,
) -> discord.AutoModRule:
    """Create an AutoMod rule."""
    kwargs = {
        "name": name,
        "event_type": event_type,
        "trigger_type": trigger_type,
        "actions": actions,
        "enabled": enabled,
    }
    if trigger_metadata:
        kwargs["trigger_metadata"] = trigger_metadata
    if exempt_roles:
        kwargs["exempt_roles"] = exempt_roles
    if exempt_channels:
        kwargs["exempt_channels"] = exempt_channels
    if reason:
        kwargs["reason"] = reason
    return await guild.create_automod_rule(**kwargs)


async def edit_automod_rule(
    rule: discord.AutoModRule,
    name: Optional[str] = None,
    enabled: Optional[bool] = None,
    actions: Optional[List[discord.AutoModRuleAction]] = None,
    trigger_metadata: Optional[discord.AutoModTriggerMetadata] = None,
    exempt_roles: Optional[List[discord.Role]] = None,
    exempt_channels: Optional[List[discord.TextChannel]] = None,
    reason: Optional[str] = None,
) -> None:
    """Edit an AutoMod rule."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if enabled is not None:
        kwargs["enabled"] = enabled
    if actions is not None:
        kwargs["actions"] = actions
    if trigger_metadata is not None:
        kwargs["trigger_metadata"] = trigger_metadata
    if exempt_roles is not None:
        kwargs["exempt_roles"] = exempt_roles
    if exempt_channels is not None:
        kwargs["exempt_channels"] = exempt_channels
    if reason is not None:
        kwargs["reason"] = reason
    await rule.edit(**kwargs)


async def delete_automod_rule(rule: discord.AutoModRule, reason: Optional[str] = None) -> None:
    """Delete an AutoMod rule."""
    await rule.delete(reason=reason)
