"""
Event Bus — Cross-platform event system for Overpower hub.

Provides a publish/subscribe mechanism that allows all connected clients
to react to events from any other platform in real time.

Event Types:
    message.received   — New message on any platform
    message.sent        — Message sent via relay or sync
    quest.completed     — Quest/task completed on Galxe/Gleam/Zealy
    quest.failed        — Quest/task failed
    account.status      — Account status change (banned, restricted, etc.)
    engagement.action   — Social engagement action (like, retweet, react)
    credential.expired  — Credential/token expired
    sync.completed      — Cross-platform sync action completed

Usage:
    bus = EventBus()

    @bus.on("message.received", platform="telegram")
    async def on_telegram_message(event: OverpowerEvent):
        print(f"TG message from {event.data['sender']}: {event.data['text']}")

    await bus.publish(OverpowerEvent(
        type="message.received",
        platform="telegram",
        source="telegram-userbot",
        data={"sender": "user123", "text": "Hello", "chat_id": 456}
    ))
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional
from collections import defaultdict

logger = logging.getLogger("overpower.event_bus")


@dataclass
class OverpowerEvent:
    """Represents a single event in the Overpower system."""
    type: str
    platform: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.platform}.{self.type}.{int(self.timestamp.timestamp())}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "platform": self.platform,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


# Type alias for event handlers
EventHandler = Callable[[OverpowerEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Central event bus for cross-platform communication.

    Supports filtering by event type, platform, and source.
    Handlers are called asynchronously in order of subscription.
    """

    def __init__(self, max_history: int = 1000):
        self._handlers: list[tuple[str, Optional[str], EventHandler]] = []
        self._history: list[OverpowerEvent] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()
        self._global_handlers: list[EventHandler] = []

    def on(
        self,
        event_type: str,
        platform: Optional[str] = None,
    ) -> Callable[[EventHandler], EventHandler]:
        """Register an event handler (decorator).

        Args:
            event_type: Event type to listen for (e.g. "message.received")
            platform: Optional platform filter (e.g. "telegram")
        """
        def decorator(handler: EventHandler) -> EventHandler:
            self._handlers.append((event_type, platform, handler))
            logger.debug(
                "Handler registered: type=%s platform=%s handler=%s",
                event_type, platform, handler.__name__
            )
            return handler
        return decorator

    def on_any(self, handler: EventHandler) -> None:
        """Register a handler that fires for ALL events."""
        self._global_handlers.append(handler)

    def remove_handler(self, handler: EventHandler) -> bool:
        """Remove a specific handler. Returns True if found and removed."""
        initial_len = len(self._handlers)
        self._handlers = [
            (et, p, h) for et, p, h in self._handlers if h is not handler
        ]
        self._global_handlers = [h for h in self._global_handlers if h is not handler]
        return len(self._handlers) + len(self._global_handlers) < initial_len

    async def publish(self, event: OverpowerEvent) -> int:
        """Publish an event to all matching handlers.

        Args:
            event: The event to publish

        Returns:
            Number of handlers that were invoked
        """
        async with self._lock:
            # Add to history
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        invoked = 0

        # Fire global handlers (all events)
        for handler in self._global_handlers:
            try:
                await handler(event)
                invoked += 1
            except Exception as e:
                logger.error(
                    "Global handler error: %s — %s", handler.__name__, e
                )

        # Fire type/platform-specific handlers
        for event_type, platform, handler in self._handlers:
            if event_type != event.type:
                continue
            if platform is not None and platform != event.platform:
                continue
            try:
                await handler(event)
                invoked += 1
            except Exception as e:
                logger.error(
                    "Handler error [%s/%s]: %s — %s",
                    event.platform, event.type, handler.__name__, e
                )

        logger.debug(
            "Event published: %s.%s -> %d handlers",
            event.platform, event.type, invoked
        )
        return invoked

    async def publish_simple(
        self,
        event_type: str,
        platform: str,
        source: str,
        data: Optional[dict[str, Any]] = None,
    ) -> int:
        """Convenience method to publish an event without creating OverpowerEvent."""
        event = OverpowerEvent(
            type=event_type,
            platform=platform,
            source=source,
            data=data or {},
        )
        return await self.publish(event)

    def get_history(
        self,
        event_type: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get event history with optional filters."""
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        if platform:
            events = [e for e in events if e.platform == platform]
        return [e.to_dict() for e in events[-limit:]]

    def clear_history(self) -> int:
        """Clear all event history. Returns count of cleared events."""
        count = len(self._history)
        self._history.clear()
        return count

    @property
    def handler_count(self) -> int:
        """Total number of registered handlers."""
        return len(self._handlers) + len(self._global_handlers)

    @property
    def event_count(self) -> int:
        """Total number of events in history."""
        return len(self._history)
