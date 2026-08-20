"""
Overpower Module — Unified hub that connects all clients into a single coordinated system.

Bridges:
    discord-client  — Discord selfbot (messages, servers, voice, DMs)
    telegram-userbot — Telegram userbot (messages, groups, channels, stories)
    x-client         — X/Twitter client (tweets, DMs, timeline, search)
    galxe-client     — Galxe quest platform (campaigns, credentials, OATs)
    gleam-client     — Gleam.io campaign automation (enter, social tasks)
    zealy-client      — Zealy quest platform (quests, XP, social tasks)
    engage-client    — X engage campaign monitor (reply, quote, retweet)
    outlook-creator  — Outlook account creator (batch registration)

Overpower Features:
    - Unified account status dashboard across all platforms
    - Cross-platform message relay (Discord <-> Telegram <-> X)
    - Coordinated quest completion (Galxe + Gleam + Zealy)
    - Synchronized social actions (tweet + Discord post + Telegram forward)
    - Centralized credential management
    - Multi-platform engagement automation pipeline
    - Real-time event bus for cross-platform reactions

Usage:
    from overpower.hub import OverpowerHub

    hub = OverpowerHub()
    await hub.initialize(platforms=["discord", "telegram", "x"])
    await hub.relay_message("telegram", "discord", "Hello from Telegram!", target_chat=123)

    # Cross-platform quest pipeline
    await hub.run_quest_pipeline("galxe_campaign_xyz")

    # Unified status
    status = await hub.get_unified_status()
"""

from .hub import OverpowerHub
from .relay import MessageRelay, RelayConfig
from .quest_pipeline import QuestPipeline, QuestResult
from .event_bus import EventBus, OverpowerEvent
from .status_dashboard import StatusDashboard
from .sync_actions import SyncActions
from .credential_manager import CredentialManager

__all__ = [
    "OverpowerHub",
    "MessageRelay",
    "RelayConfig",
    "QuestPipeline",
    "QuestResult",
    "EventBus",
    "OverpowerEvent",
    "StatusDashboard",
    "SyncActions",
    "CredentialManager",
]
