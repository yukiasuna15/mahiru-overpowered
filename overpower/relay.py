"""
Message Relay — Cross-platform message forwarding and synchronization.

Enables bidirectional message relay between Discord, Telegram, and X/Twitter.
Supports message transformation, filtering, and rate limiting.

Relay Paths:
    telegram -> discord   — Forward Telegram messages to Discord channel
    discord -> telegram   — Forward Discord messages to Telegram chat
    telegram -> x         — Post Telegram message as tweet
    x -> telegram         — Forward tweet to Telegram chat
    discord -> x          — Post Discord message as tweet
    x -> discord          — Forward tweet to Discord channel

Usage:
    relay = MessageRelay(hub.event_bus)

    # Configure relay route
    relay.add_route(
        source="telegram",
        destination="discord",
        config=RelayConfig(
            source_chat=123456,
            dest_channel=789012,
            prefix="[TG] ",
            include_media=True,
        )
    )

    # Start relay
    await relay.start()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .event_bus import EventBus, OverpowerEvent

logger = logging.getLogger("overpower.relay")


@dataclass
class RelayConfig:
    """Configuration for a single relay route."""
    source_chat: Optional[int] = None
    dest_channel: Optional[int] = None
    prefix: str = ""
    include_media: bool = True
    include_sender: bool = True
    filter_bot: bool = True
    filter_commands: bool = True
    rate_limit: float = 1.0  # Minimum seconds between messages
    max_length: int = 2000
    enabled: bool = True
    transform: Optional[str] = None  # "lowercase", "uppercase", "strip_mentions"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_chat": self.source_chat,
            "dest_channel": self.dest_channel,
            "prefix": self.prefix,
            "include_media": self.include_media,
            "include_sender": self.include_sender,
            "filter_bot": self.filter_bot,
            "filter_commands": self.filter_commands,
            "rate_limit": self.rate_limit,
            "max_length": self.max_length,
            "enabled": self.enabled,
            "transform": self.transform,
        }


@dataclass
class RelayRoute:
    """A single relay route from one platform to another."""
    source: str
    destination: str
    config: RelayConfig
    _last_sent: float = 0.0

    @property
    def key(self) -> str:
        return f"{self.source}->{self.destination}"


class MessageRelay:
    """
    Cross-platform message relay system.

    Manages bidirectional message forwarding between platforms.
    Integrates with the EventBus for automatic message handling.
    """

    SUPPORTED_PLATFORMS = {"discord", "telegram", "x"}

    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._routes: dict[str, RelayRoute] = {}
        self._stats: dict[str, dict[str, Any]] = {}
        self._running = False

    def add_route(
        self,
        source: str,
        destination: str,
        config: Optional[RelayConfig] = None,
    ) -> RelayRoute:
        """Add a relay route between two platforms.

        Args:
            source: Source platform name
            destination: Destination platform name
            config: Relay configuration

        Returns:
            The created RelayRoute
        """
        if source not in self.SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported source platform: {source}")
        if destination not in self.SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported destination platform: {destination}")

        cfg = config or RelayConfig()
        route = RelayRoute(source=source, destination=destination, config=cfg)
        self._routes[route.key] = route
        self._stats[route.key] = {
            "relayed": 0,
            "failed": 0,
            "filtered": 0,
            "last_relay": None,
        }
        logger.info("Relay route added: %s", route.key)
        return route

    def remove_route(self, source: str, destination: str) -> bool:
        """Remove a relay route."""
        key = f"{source}->{destination}"
        if key in self._routes:
            del self._routes[key]
            del self._stats[key]
            return True
        return False

    def get_routes(self) -> list[dict[str, Any]]:
        """Get all configured relay routes."""
        return [
            {
                "source": r.source,
                "destination": r.destination,
                "config": r.config.to_dict(),
                "stats": self._stats.get(r.key, {}),
            }
            for r in self._routes.values()
        ]

    async def start(self) -> None:
        """Start the relay system by registering event handlers."""
        if self._running:
            logger.warning("Relay already running")
            return

        self._running = True

        # Register handlers for each source platform
        @self._bus.on("message.received", platform="telegram")
        async def _on_telegram_msg(event: OverpowerEvent):
            await self._handle_relay(event, "telegram")

        @self._bus.on("message.received", platform="discord")
        async def _on_discord_msg(event: OverpowerEvent):
            await self._handle_relay(event, "discord")

        @self._bus.on("message.received", platform="x")
        async def _on_x_msg(event: OverpowerEvent):
            await self._handle_relay(event, "x")

        logger.info(
            "Message relay started with %d routes", len(self._routes)
        )

    async def stop(self) -> None:
        """Stop the relay system."""
        self._running = False
        logger.info("Message relay stopped")

    async def _handle_relay(self, event: OverpowerEvent, source: str) -> None:
        """Process an incoming message for relay."""
        if not self._running:
            return

        for key, route in self._routes.items():
            if route.source != source or not route.config.enabled:
                continue

            stats = self._stats[key]

            # Apply filters
            if not self._should_relay(event, route):
                stats["filtered"] += 1
                continue

            # Rate limiting
            now = time.monotonic()
            if now - route._last_sent < route.config.rate_limit:
                continue
            route._last_sent = now

            # Transform message
            message = self._transform_message(event, route)

            try:
                await self._bus.publish(OverpowerEvent(
                    type="message.sent",
                    platform=route.destination,
                    source="overpower.relay",
                    data={
                        "original_platform": source,
                        "original_event_id": event.event_id,
                        "message": message,
                        "target_chat": route.config.dest_channel,
                        "include_media": route.config.include_media,
                    },
                ))
                stats["relayed"] += 1
                stats["last_relay"] = event.timestamp.isoformat()
                logger.debug(
                    "Relayed %s -> %s: %s",
                    source, route.destination, message[:50]
                )
            except Exception as e:
                stats["failed"] += 1
                logger.error(
                    "Relay failed %s -> %s: %s",
                    source, route.destination, e
                )

    def _should_relay(self, event: OverpowerEvent, route: RelayRoute) -> bool:
        """Check if a message should be relayed based on filters."""
        data = event.data

        # Filter bot messages
        if route.config.filter_bot and data.get("is_bot"):
            return False

        # Filter commands (messages starting with / or !)
        if route.config.filter_commands:
            text = data.get("text", "")
            if text.startswith("/") or text.startswith("!"):
                return False

        # Filter by source chat
        if route.config.source_chat is not None:
            if data.get("chat_id") != route.config.source_chat:
                return False

        # Filter empty messages
        if not data.get("text") and not data.get("media"):
            return False

        return True

    def _transform_message(self, event: OverpowerEvent, route: RelayRoute) -> str:
        """Apply message transformations."""
        data = event.data
        parts = []

        # Add prefix
        if route.config.prefix:
            parts.append(route.config.prefix)

        # Add sender info
        if route.config.include_sender and data.get("sender"):
            parts.append(f"[{data['sender']}]")

        # Get text content
        text = data.get("text", "")
        if route.config.transform == "lowercase":
            text = text.lower()
        elif route.config.transform == "uppercase":
            text = text.upper()
        elif route.config.transform == "strip_mentions":
            text = " ".join(
                w for w in text.split()
                if not w.startswith("@") and not w.startswith("@")
            )

        parts.append(text)

        # Add media indicator
        if route.config.include_media and data.get("media"):
            parts.append("[media attached]")

        message = " ".join(parts)

        # Truncate to max length
        if len(message) > route.config.max_length:
            message = message[:route.config.max_length - 3] + "..."

        return message

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """Get relay statistics for all routes."""
        return dict(self._stats)
