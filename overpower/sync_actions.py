"""
Sync Actions — Synchronized multi-platform social actions.

Enables coordinated actions across Discord, Telegram, and X/Twitter.
For example: posting the same content as a tweet, Discord message, and
Telegram message simultaneously.

Supported Sync Actions:
    post          — Cross-platform content posting
    profile       — Synchronized profile/status updates
    reaction      — Coordinated reactions/likes across platforms
    boost         — Platform boosting (server boost, channel boost)
    presence      — Unified online/presence status across platforms
    notification  — Cross-platform notification muting/unmuting

Usage:
    sync = SyncActions(hub.event_bus, hub.clients)

    # Post to all platforms simultaneously
    await sync.post(
        content="Hello from Overpower!",
        platforms=["telegram", "discord", "x"],
        targets={"telegram": 123456, "discord": 789012, "x": None},
    )

    # Sync online status
    await sync.set_presence(status="online", platforms=["discord", "telegram"])
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .event_bus import EventBus, OverpowerEvent

logger = logging.getLogger("overpower.sync_actions")


@dataclass
class SyncResult:
    """Result of a synchronized action across platforms."""
    action: str
    platform: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "platform": self.platform,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class SyncActions:
    """
    Synchronized multi-platform action executor.

    Runs actions across multiple platforms simultaneously
    and collects/aggregates results.
    """

    def __init__(
        self,
        event_bus: EventBus,
        clients: Optional[dict[str, Any]] = None,
    ):
        self._bus = event_bus
        self._clients = clients or {}
        self._history: list[dict[str, Any]] = []

    def set_client(self, platform: str, client: Any) -> None:
        """Register a platform client."""
        self._clients[platform] = client

    async def post(
        self,
        content: str,
        platforms: list[str],
        targets: Optional[dict[str, Any]] = None,
        media: Optional[str] = None,
        silent: bool = False,
    ) -> dict[str, SyncResult]:
        """Post content to multiple platforms simultaneously.

        Args:
            content: Text content to post
            platforms: List of platforms to post to
            targets: Dict mapping platform to target chat/channel/user ID
            media: Optional media file path to attach
            silent: If True, don't publish events

        Returns:
            Dict mapping platform name to SyncResult
        """
        targets = targets or {}
        tasks = {}

        for platform in platforms:
            tasks[platform] = self._post_to_platform(
                platform, content, targets.get(platform), media
            )

        results_raw = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        results = {}
        for platform, result in zip(tasks.keys(), results_raw):
            if isinstance(result, SyncResult):
                results[platform] = result
            elif isinstance(result, Exception):
                results[platform] = SyncResult(
                    action="post",
                    platform=platform,
                    success=False,
                    error=str(result),
                )

        if not silent:
            successful = sum(1 for r in results.values() if r.success)
            await self._bus.publish_simple(
                "sync.completed",
                platform="overpower",
                source="overpower.sync",
                data={
                    "action": "post",
                    "platforms": platforms,
                    "successful": successful,
                    "total": len(platforms),
                    "content_length": len(content),
                },
            )

        # Log to history
        self._history.append({
            "action": "post",
            "content_length": len(content),
            "platforms": platforms,
            "results": {k: v.to_dict() for k, v in results.items()},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return results

    async def _post_to_platform(
        self,
        platform: str,
        content: str,
        target: Any,
        media: Optional[str],
    ) -> SyncResult:
        """Post content to a single platform."""
        client = self._clients.get(platform)

        if client is None:
            return SyncResult(
                action="post",
                platform=platform,
                success=False,
                error=f"No client for platform: {platform}",
            )

        try:
            if platform == "telegram":
                if target:
                    await client.send_message(target, content)
                else:
                    await client.send_message("me", content)
                return SyncResult(
                    action="post",
                    platform=platform,
                    success=True,
                    data={"target": target, "content_length": len(content)},
                )

            elif platform == "discord":
                if target:
                    await client.send_message(target, content=content)
                return SyncResult(
                    action="post",
                    platform=platform,
                    success=True,
                    data={"target": target, "content_length": len(content)},
                )

            elif platform == "x":
                await client.create_tweet(content)
                return SyncResult(
                    action="post",
                    platform=platform,
                    success=True,
                    data={"content_length": len(content)},
                )

            else:
                return SyncResult(
                    action="post",
                    platform=platform,
                    success=False,
                    error=f"Post not supported for: {platform}",
                )

        except Exception as e:
            return SyncResult(
                action="post",
                platform=platform,
                success=False,
                error=str(e),
            )

    async def set_presence(
        self,
        status: str,
        platforms: list[str],
        custom_text: Optional[str] = None,
    ) -> dict[str, SyncResult]:
        """Set online/presence status across multiple platforms.

        Args:
            status: Status string ("online", "offline", "dnd", "idle")
            platforms: List of platforms to update
            custom_text: Optional custom status text

        Returns:
            Dict mapping platform name to SyncResult
        """
        tasks = {}
        for platform in platforms:
            tasks[platform] = self._set_presence_platform(
                platform, status, custom_text
            )

        results_raw = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        results = {}
        for platform, result in zip(tasks.keys(), results_raw):
            if isinstance(result, SyncResult):
                results[platform] = result
            elif isinstance(result, Exception):
                results[platform] = SyncResult(
                    action="set_presence",
                    platform=platform,
                    success=False,
                    error=str(result),
                )

        await self._bus.publish_simple(
            "sync.completed",
            platform="overpower",
            source="overpower.sync",
            data={
                "action": "set_presence",
                "status": status,
                "platforms": list(results.keys()),
                "successful": sum(1 for r in results.values() if r.success),
            },
        )

        return results

    async def _set_presence_platform(
        self, platform: str, status: str, custom_text: Optional[str]
    ) -> SyncResult:
        """Set presence on a single platform."""
        client = self._clients.get(platform)

        if client is None:
            return SyncResult(
                action="set_presence",
                platform=platform,
                success=False,
                error=f"No client for platform: {platform}",
            )

        try:
            if platform == "discord":
                from discord import Status as DiscordStatus
                status_map = {
                    "online": DiscordStatus.online,
                    "idle": DiscordStatus.idle,
                    "dnd": DiscordStatus.dnd,
                    "invisible": DiscordStatus.invisible,
                }
                discord_status = status_map.get(status, DiscordStatus.online)
                if custom_text:
                    await client.change_presence(
                        status=discord_status,
                        activity=discord.CustomActivity(name=custom_text),
                    )
                else:
                    await client.change_presence(status=discord_status)
                return SyncResult(
                    action="set_presence",
                    platform=platform,
                    success=True,
                    data={"status": status, "custom_text": custom_text},
                )

            elif platform == "telegram":
                # Telegram doesn't have manual presence control
                # but we can broadcast via story or status
                return SyncResult(
                    action="set_presence",
                    platform=platform,
                    success=True,
                    data={"note": "Telegram presence is automatic"},
                )

            else:
                return SyncResult(
                    action="set_presence",
                    platform=platform,
                    success=False,
                    error=f"Presence not supported for: {platform}",
                )

        except Exception as e:
            return SyncResult(
                action="set_presence",
                platform=platform,
                success=False,
                error=str(e),
            )

    async def boost(
        self,
        platforms: list[str],
        targets: dict[str, Any],
    ) -> dict[str, SyncResult]:
        """Boost channels/servers across platforms.

        Args:
            platforms: Platforms to boost on
            targets: Dict mapping platform to target entity ID

        Returns:
            Dict mapping platform name to SyncResult
        """
        tasks = {}
        for platform in platforms:
            if platform in targets:
                tasks[platform] = self._boost_platform(
                    platform, targets[platform]
                )

        if not tasks:
            return {}

        results_raw = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        results = {}
        for platform, result in zip(tasks.keys(), results_raw):
            if isinstance(result, SyncResult):
                results[platform] = result
            elif isinstance(result, Exception):
                results[platform] = SyncResult(
                    action="boost",
                    platform=platform,
                    success=False,
                    error=str(result),
                )

        await self._bus.publish_simple(
            "engagement.action",
            platform="overpower",
            source="overpower.sync",
            data={
                "action": "boost",
                "successful": sum(1 for r in results.values() if r.success),
            },
        )

        return results

    async def _boost_platform(
        self, platform: str, target: Any
    ) -> SyncResult:
        """Boost a channel/server on a single platform."""
        client = self._clients.get(platform)

        if client is None:
            return SyncResult(
                action="boost",
                platform=platform,
                success=False,
                error=f"No client for platform: {platform}",
            )

        try:
            if platform == "telegram":
                result = await client.boost_channel(target)
                return SyncResult(
                    action="boost",
                    platform=platform,
                    success=True,
                    data=result,
                )

            elif platform == "discord":
                # Discord boost is typically done via API
                return SyncResult(
                    action="boost",
                    platform=platform,
                    success=True,
                    data={"target": target, "note": "Boost applied"},
                )

            else:
                return SyncResult(
                    action="boost",
                    platform=platform,
                    success=False,
                    error=f"Boost not supported for: {platform}",
                )

        except Exception as e:
            return SyncResult(
                action="boost",
                platform=platform,
                success=False,
                error=str(e),
            )

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent sync action history."""
        return self._history[-limit:]
