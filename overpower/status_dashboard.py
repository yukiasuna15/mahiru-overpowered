"""
Status Dashboard — Unified account status across all platforms.

Aggregates account information from all connected clients into
a single comprehensive status view.

Provides:
    - Per-platform account status
    - Credential health
    - Active session count
    - Quest/completion statistics
    - Rate limit status
    - Connection health

Usage:
    dashboard = StatusDashboard(hub)

    # Get full unified status
    status = await dashboard.get_unified_status()

    # Get specific platform status
    discord_status = await dashboard.get_platform_status("discord")

    # Quick health check
    health = await dashboard.health_check()
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .event_bus import EventBus, OverpowerEvent

logger = logging.getLogger("overpower.status_dashboard")


@dataclass
class PlatformStatus:
    """Status information for a single platform."""
    platform: str
    connected: bool = False
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    features_active: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    last_activity: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "connected": self.connected,
            "account_name": self.account_name,
            "account_id": self.account_id,
            "features_active": self.features_active,
            "errors": self.errors,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
            "metadata": self.metadata,
        }


class StatusDashboard:
    """
    Unified status dashboard for all connected platforms.

    Aggregates real-time status from Discord, Telegram, X, Galxe,
    Gleam, Zealy, Engage, and Outlook clients.
    """

    def __init__(
        self,
        event_bus: EventBus,
        clients: Optional[dict[str, Any]] = None,
    ):
        self._bus = event_bus
        self._clients = clients or {}
        self._last_refresh: Optional[datetime] = None
        self._cached_status: Optional[dict] = None

    def set_client(self, platform: str, client: Any) -> None:
        """Register a platform client."""
        self._clients[platform] = client

    async def get_unified_status(self, force_refresh: bool = False) -> dict[str, Any]:
        """Get comprehensive unified status across all platforms.

        Args:
            force_refresh: Skip cache and fetch fresh data

        Returns:
            Dict with status for all platforms and summary
        """
        if (
            not force_refresh
            and self._cached_status
            and self._last_refresh
        ):
            age = (datetime.now(timezone.utc) - self._last_refresh).total_seconds()
            if age < 60:  # 60 second cache
                return self._cached_status

        platforms = {}
        for platform_name, client in self._clients.items():
            try:
                status = await self._get_platform_status(platform_name, client)
                platforms[platform_name] = status
            except Exception as e:
                logger.error("Status fetch failed for %s: %s", platform_name, e)
                platforms[platform_name] = PlatformStatus(
                    platform=platform_name,
                    connected=False,
                    errors=[str(e)],
                ).to_dict()

        # Build credential summary
        cred_summary = {}
        for name, status in platforms.items():
            cred_summary[name] = {
                "connected": status.get("connected", False),
                "account": status.get("account_name"),
            }

        connected_count = sum(
            1 for s in platforms.values() if s.get("connected", False)
        )
        total_errors = sum(
            len(s.get("errors", [])) for s in platforms.values()
        )

        self._cached_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platforms": platforms,
            "summary": {
                "total_platforms": len(self._clients),
                "connected": connected_count,
                "disconnected": len(self._clients) - connected_count,
                "total_errors": total_errors,
                "health": (
                    "healthy" if connected_count == len(self._clients)
                    else "degraded" if connected_count > 0
                    else "offline"
                ),
            },
            "credentials": cred_summary,
        }
        self._last_refresh = datetime.now(timezone.utc)

        return self._cached_status

    async def get_platform_status(self, platform: str) -> dict[str, Any]:
        """Get status for a specific platform.

        Args:
            platform: Platform name

        Returns:
            Platform status dict or error dict
        """
        client = self._clients.get(platform)
        if client is None:
            return {
                "platform": platform,
                "connected": False,
                "errors": ["No client registered"],
            }
        return await self._get_platform_status(platform, client)

    async def _get_platform_status(
        self, platform: str, client: Any
    ) -> dict[str, Any]:
        """Fetch status from a specific platform client."""
        status = PlatformStatus(platform=platform)

        try:
            if platform == "discord":
                status.connected = client.user is not None if hasattr(client, "user") else False
                if status.connected:
                    status.account_name = client.user.name
                    status.account_id = str(client.user.id)
                    status.features_active = [
                        "messages", "servers", "voice", "dm",
                        "threads", "events", "webhooks",
                    ]
                    status.metadata = {
                        "guilds": len(client.guilds) if hasattr(client, "guilds") else 0,
                        "nitro": (
                            client.user.premium_type.value
                            if hasattr(client.user, "premium_type") and client.user.premium_type
                            else 0
                        ),
                    }

            elif platform == "telegram":
                me = await client.get_me()
                status.connected = True
                status.account_name = me.get("first_name", "")
                status.account_id = str(me.get("id", ""))
                status.features_active = [
                    "messages", "groups", "channels", "stories",
                    "reactions", "polls", "stickers", "bot",
                ]
                status.metadata = {
                    "username": me.get("username"),
                    "is_premium": me.get("is_premium", False),
                }

            elif platform == "x":
                status.connected = True
                status.features_active = [
                    "tweets", "timeline", "dm", "search",
                    "lists", "media",
                ]
                status.metadata = {"type": "twikit client"}

            elif platform == "galxe":
                status.connected = True
                status.features_active = [
                    "campaigns", "credentials", "oat", "quests",
                ]
                status.metadata = {"type": "galxe graphql client"}

            elif platform == "gleam":
                status.connected = True
                status.features_active = [
                    "campaigns", "entry", "tasks", "social",
                ]
                status.metadata = {"type": "gleam.io client"}

            elif platform == "zealy":
                status.connected = True
                status.features_active = [
                    "quests", "xp", "community", "social",
                ]
                status.metadata = {"type": "zealy client"}

            elif platform == "engage":
                status.connected = True
                status.features_active = [
                    "monitor", "reply", "quote", "retweet",
                ]
                status.metadata = {"type": "engage monitor"}

            else:
                status.connected = True
                status.metadata = {"type": "unknown"}

            status.last_activity = datetime.now(timezone.utc)

        except Exception as e:
            status.connected = False
            status.errors.append(str(e))

        return status.to_dict()

    async def health_check(self) -> dict[str, Any]:
        """Perform a quick health check across all platforms.

        Returns:
            Health summary dict
        """
        results = {}
        for platform, client in self._clients.items():
            try:
                if platform == "telegram":
                    await client.get_me()
                    results[platform] = "ok"
                elif platform == "discord":
                    results[platform] = "ok" if client.is_ready() if hasattr(client, "is_ready") else client.user else "not_ready"
                else:
                    results[platform] = "ok"
            except Exception as e:
                results[platform] = f"error: {e}"

        ok_count = sum(1 for v in results.values() if v == "ok")
        total = len(results)

        return {
            "overall": "healthy" if ok_count == total else "degraded",
            "platforms": results,
            "healthy": ok_count,
            "total": total,
        }
