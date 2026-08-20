"""
Overpower Hub — Central orchestrator that connects all clients.

The Hub is the main entry point for the Overpower system.
It initializes all platform clients, wires up the event bus,
and provides unified access to all subsystems.

Subsystems:
    EventBus         — Cross-platform event publish/subscribe
    MessageRelay    — Bidirectional message forwarding
    QuestPipeline    — Multi-platform quest automation
    SyncActions      — Coordinated social actions
    StatusDashboard — Unified status/health dashboard
    CredentialManager — Centralized credential management

Usage:
    hub = OverpowerHub()

    # Initialize specific platforms
    await hub.initialize(platforms=["telegram", "discord", "x"])

    # Relay messages between platforms
    await hub.relay_message("telegram", "discord", "Hello!", target=123)

    # Run quest pipeline
    result = await hub.run_quest_pipeline("galxe_campaign_123")

    # Get unified status
    status = await hub.get_unified_status()

    # Synchronized post
    await hub.sync_post("Hello World!", ["telegram", "discord", "x"])

    # Shutdown
    await hub.shutdown()
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Any, Optional

from .event_bus import EventBus, OverpowerEvent
from .relay import MessageRelay, RelayConfig
from .quest_pipeline import QuestPipeline, QuestResult
from .sync_actions import SyncActions
from .status_dashboard import StatusDashboard
from .credential_manager import CredentialManager

logger = logging.getLogger("overpower.hub")

# Base directory for all client modules
BASE_DIR = Path(__file__).parent.parent


class OverpowerHub:
    """
    Central orchestrator for the Overpower multi-platform system.

    Manages client lifecycle, event routing, and provides a unified
    API for cross-platform operations.
    """

    def __init__(self, credentials_dir: Optional[Path] = None):
        self._event_bus = EventBus()
        self._credential_mgr = CredentialManager(credentials_dir)
        self._relay = MessageRelay(self._event_bus)
        self._pipeline = QuestPipeline(self._event_bus)
        self._sync = SyncActions(self._event_bus)
        self._dashboard = StatusDashboard(self._event_bus)

        self._clients: dict[str, Any] = {}
        self._platforms_initialized: list[str] = []
        self._running = False

        # Wire credential events to event bus
        self._credential_mgr.set_event_callback(self._on_credential_event)

    # === Properties ===

    @property
    def event_bus(self) -> EventBus:
        """Access the global event bus."""
        return self._event_bus

    @property
    def relay(self) -> MessageRelay:
        """Access the message relay subsystem."""
        return self._relay

    @property
    def pipeline(self) -> QuestPipeline:
        """Access the quest pipeline subsystem."""
        return self._pipeline

    @property
    def sync(self) -> SyncActions:
        """Access the sync actions subsystem."""
        return self._sync

    @property
    def dashboard(self) -> StatusDashboard:
        """Access the status dashboard subsystem."""
        return self._dashboard

    @property
    def credentials(self) -> CredentialManager:
        """Access the credential manager."""
        return self._credential_mgr

    @property
    def clients(self) -> dict[str, Any]:
        """Access all registered platform clients."""
        return dict(self._clients)

    @property
    def is_running(self) -> bool:
        """Check if the hub is running."""
        return self._running

    # === Initialization ===

    async def initialize(
        self,
        platforms: Optional[list[str]] = None,
        validate_credentials: bool = True,
    ) -> dict[str, Any]:
        """Initialize the hub and connect specified platform clients.

        Args:
            platforms: List of platforms to initialize.
                       Supported: discord, telegram, x, galxe, gleam, zealy, engage
            validate_credentials: Whether to validate credentials before init

        Returns:
            Initialization status dict
        """
        if self._running:
            logger.warning("Hub already initialized")
            return {"status": "already_running", "platforms": self._platforms_initialized}

        platforms = platforms or ["telegram", "discord", "x"]
        results = {}

        # Load and validate credentials
        if validate_credentials:
            await self._credential_mgr.load_all()
            cred_status = self._credential_mgr.get_status()
            logger.info(
                "Credentials: %d/%d valid",
                cred_status["summary"]["valid"],
                cred_status["summary"]["total"],
            )

        # Initialize each platform
        for platform in platforms:
            try:
                client = await self._init_platform(platform)
                if client:
                    self._clients[platform] = client
                    self._sync.set_client(platform, client)
                    self._pipeline.set_client(platform, client)
                    self._dashboard.set_client(platform, client)
                    self._platforms_initialized.append(platform)
                    results[platform] = "initialized"
                    logger.info("Platform initialized: %s", platform)
                else:
                    results[platform] = "skipped"
                    logger.info("Platform skipped (no credentials): %s", platform)
            except Exception as e:
                results[platform] = f"error: {e}"
                logger.error("Platform init failed for %s: %s", platform, e)

        # Start subsystems
        self._running = True
        await self._relay.start()

        logger.info(
            "Overpower Hub initialized: %d platforms",
            len(self._platforms_initialized)
        )

        return {
            "status": "running",
            "platforms": results,
            "connected": self._platforms_initialized,
            "event_handlers": self._event_bus.handler_count,
        }

    async def _init_platform(self, platform: str) -> Optional[Any]:
        """Initialize a specific platform client."""
        if not await self._credential_mgr.validate(platform):
            logger.info("Skipping %s: credentials invalid or missing", platform)
            return None

        try:
            if platform == "telegram":
                return await self._init_telegram()
            elif platform == "discord":
                return await self._init_discord()
            elif platform == "x":
                return await self._init_x()
            elif platform == "galxe":
                return await self._init_galxe()
            elif platform == "gleam":
                return await self._init_gleam()
            elif platform == "zealy":
                return await self._init_zealy()
            else:
                logger.warning("Unknown platform: %s", platform)
                return None
        except Exception as e:
            logger.error("Failed to initialize %s: %s", platform, e)
            raise

    async def _init_telegram(self) -> Any:
        """Initialize Telegram userbot client."""
        tg_path = BASE_DIR / "telegram-userbot"
        if str(tg_path) not in sys.path:
            sys.path.insert(0, str(tg_path))

        from auth import get_client
        client = await get_client()
        logger.info("Telegram client connected")
        return client

    async def _init_discord(self) -> Any:
        """Initialize Discord selfbot client."""
        discord_path = BASE_DIR / "discord-client"
        if str(discord_path) not in sys.path:
            sys.path.insert(0, str(discord_path))

        from auth import load_token, create_client
        token = load_token()
        client = create_client()
        # Note: actual login happens via client.start(token) which is async
        # The client is created but not yet connected — user should call start()
        logger.info("Discord client created (not yet connected)")
        return client

    async def _init_x(self) -> Any:
        """Initialize X/Twitter client."""
        x_path = BASE_DIR / "x-client"
        if str(x_path) not in sys.path:
            sys.path.insert(0, str(x_path))

        from auth import get_client
        client = await get_client()
        logger.info("X client connected")
        return client

    async def _init_galxe(self) -> Any:
        """Initialize Galxe client."""
        galxe_path = BASE_DIR / "galxe-client"
        if str(galxe_path) not in sys.path:
            sys.path.insert(0, str(galxe_path))
        logger.info("Galxe client initialized")
        return {"platform": "galxe", "connected": True}

    async def _init_gleam(self) -> Any:
        """Initialize Gleam client."""
        gleam_path = BASE_DIR / "gleam-client"
        if str(gleam_path) not in sys.path:
            sys.path.insert(0, str(gleam_path))
        logger.info("Gleam client initialized")
        return {"platform": "gleam", "connected": True}

    async def _init_zealy(self) -> Any:
        """Initialize Zealy client."""
        zealy_path = BASE_DIR / "zealy-client"
        if str(zealy_path) not in sys.path:
            sys.path.insert(0, str(zealy_path))
        logger.info("Zealy client initialized")
        return {"platform": "zealy", "connected": True}

    # === Unified Operations ===

    async def relay_message(
        self,
        source: str,
        destination: str,
        message: str,
        target: Optional[Any] = None,
    ) -> bool:
        """Relay a message between platforms.

        Args:
            source: Source platform name
            destination: Destination platform name
            message: Message content
            target: Target chat/channel ID on destination

        Returns:
            True if relay was successful
        """
        results = await self._sync.post(
            content=message,
            platforms=[destination],
            targets={destination: target},
        )
        return results.get(destination, None) is not None

    async def run_quest_pipeline(self, quest_id: str) -> QuestResult:
        """Run a quest pipeline.

        Args:
            quest_id: Quest identifier

        Returns:
            QuestResult with completion details
        """
        return await self._pipeline.run(quest_id)

    async def get_unified_status(self) -> dict[str, Any]:
        """Get unified status across all platforms."""
        return await self._dashboard.get_unified_status()

    async def sync_post(
        self,
        content: str,
        platforms: list[str],
        targets: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Post content to multiple platforms simultaneously.

        Args:
            content: Text to post
            platforms: Platforms to post to
            targets: Platform-specific target IDs

        Returns:
            Results dict
        """
        return await self._sync.post(
            content=content,
            platforms=platforms,
            targets=targets,
        )

    async def sync_presence(
        self,
        status: str,
        platforms: Optional[list[str]] = None,
        custom_text: Optional[str] = None,
    ) -> dict[str, Any]:
        """Synchronize presence/status across platforms.

        Args:
            status: Status string (online, offline, dnd, idle)
            platforms: Platforms to update (None = all)
            custom_text: Optional custom status text

        Returns:
            Results dict
        """
        platforms = platforms or list(self._clients.keys())
        return await self._sync.set_presence(
            status=status,
            platforms=platforms,
            custom_text=custom_text,
        )

    async def discover_quests(
        self,
        platforms: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Discover available quests across platforms.

        Args:
            platforms: Platforms to search (None = all)

        Returns:
            List of quest summaries
        """
        return await self._pipeline.discover(platforms=platforms)

    # === Event Handling ===

    async def _on_credential_event(self, event_data: dict) -> None:
        """Handle credential manager events."""
        await self._event_bus.publish_simple(
            "credential.expired",
            platform="overpower",
            source="overpower.credentials",
            data=event_data,
        )

    # === Shutdown ===

    async def shutdown(self) -> None:
        """Shutdown the hub and disconnect all clients."""
        self._running = False

        await self._relay.stop()

        for platform, client in self._clients.items():
            try:
                if hasattr(client, "disconnect"):
                    await client.disconnect()
                elif hasattr(client, "close"):
                    await client.close()
                logger.info("Disconnected: %s", platform)
            except Exception as e:
                logger.error("Disconnect failed for %s: %s", platform, e)

        self._clients.clear()
        self._platforms_initialized.clear()
        logger.info("Overpower Hub shut down")

    # === Status ===

    def get_info(self) -> dict[str, Any]:
        """Get hub information (non-async)."""
        return {
            "running": self._running,
            "platforms_initialized": list(self._platforms_initialized),
            "clients_registered": list(self._clients.keys()),
            "relay_routes": len(self._relay.get_routes()),
            "event_handlers": self._event_bus.handler_count,
            "event_count": self._event_bus.event_count,
        }
