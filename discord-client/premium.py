"""
Discord premium/Nitro module — subscriptions, payments, payment sources.
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def get_premium_type(client: discord.Client) -> int:
    """Get the Nitro subscription type of the account (0=none, 1=Nitro Classic, 2=Nitro, 3=Nitro Basic)."""
    return client.user.premium_type.value if client.user.premium_type else 0


async def get_premium_guild_subscriptions(client: discord.Client) -> List[dict]:
    """List all server boost subscriptions."""
    subs = await client.premium_guild_subscriptions()
    return [
        {
            "id": str(s.id),
            "guild": s.guild.name if s.guild else None,
            "guild_id": str(s.guild_id) if s.guild_id else None,
            "ended": s.ended,
            "canceled": s.canceled,
            "cooldown_ends_at": str(s.cooldown_ends_at) if s.cooldown_ends_at else None,
        }
        for s in subs
    ]


async def get_premium_guild_subscription_slots(client: discord.Client) -> List[dict]:
    """List all boost subscription slots."""
    slots = await client.premium_guild_subscription_slots()
    return [
        {
            "id": str(s.id),
            "guild": s.guild.name if s.guild else None,
            "cooldown_ends_at": str(s.cooldown_ends_at) if s.cooldown_ends_at else None,
        }
        for s in slots
    ]


async def get_payment_sources(client: discord.Client) -> List[dict]:
    """List all payment sources (cards, PayPal, etc)."""
    sources = await client.payment_sources()
    return [
        {
            "id": str(s.id),
            "type": str(s.type),
            "invalid": s.invalid,
            "default": s.default,
            "expires_year": s.expires_year if hasattr(s, "expires_year") else None,
            "expires_month": s.expires_month if hasattr(s, "expires_month") else None,
        }
        for s in sources
    ]


async def get_payments(client: discord.Client) -> List[dict]:
    """List recent payments."""
    payments = await client.payments()
    return [
        {
            "id": str(p.id),
            "amount": p.amount if hasattr(p, "amount") else None,
            "currency": p.currency if hasattr(p, "currency") else None,
            "status": str(p.status) if hasattr(p, "status") else None,
            "created_at": str(p.created_at) if hasattr(p, "created_at") else None,
        }
        for p in payments
    ]


async def get_subscriptions(client: discord.Client) -> List[dict]:
    """List all subscriptions."""
    subs = await client.subscriptions()
    return [
        {
            "id": str(s.id),
            "type": str(s.type),
            "status": str(s.status),
            "interval": str(s.interval) if hasattr(s, "interval") else None,
            "current_period_start": str(s.current_period_start) if hasattr(s, "current_period_start") else None,
            "current_period_end": str(s.current_period_end) if hasattr(s, "current_period_end") else None,
            "canceled": s.canceled if hasattr(s, "canceled") else None,
        }
        for s in subs
    ]


async def get_entitlements(client: discord.Client) -> List[dict]:
    """List entitlements (gifts, trials, etc)."""
    entitlements = await client.entitlements()
    return [
        {
            "id": str(e.id),
            "type": str(e.type),
            "sku_id": str(e.sku_id) if hasattr(e, "sku_id") else None,
            "guild_id": str(e.guild_id) if hasattr(e, "guild_id") else None,
            "starts_at": str(e.starts_at) if hasattr(e, "starts_at") else None,
            "ends_at": str(e.ends_at) if hasattr(e, "ends_at") else None,
        }
        for e in entitlements
    ]


async def get_promotions(client: discord.Client) -> list:
    """Get available promotions."""
    try:
        promotions = await client.promotions()
        return [
            {
                "id": str(p.id) if hasattr(p, "id") else str(p),
                "title": p.title if hasattr(p, "title") else None,
            }
            for p in promotions
        ]
    except Exception:
        return []
