"""
Credential Manager — Centralized credential storage and lifecycle management.

Manages credentials for all platforms from a single interface.
Handles loading, validation, refresh, and expiration notifications.

Supported Platforms:
    discord   — User token (JSON)
    telegram  — Session file + API ID/Hash
    x        — Cookies (JSON)
    galxe    — JWT token + wallet keys
    gleam    — Session cookies
    zealy    — Session cookies + API key
    engage   — X cookies (shared with x-client)
    outlook  — Account data (JSON)

Credential Directory Structure:
    ~/.hermes/credentials/
        discord-token.json
        telegram-userbot.session
        telegram-userbot.env     (API_ID, API_HASH)
        x-cookies.json
        galxe-credentials.json
        gleam-cookies.json
        zealy-cookies.json
        outlook-accounts.json

Usage:
    mgr = CredentialManager()
    await mgr.load_all()
    status = mgr.get_status()
    await mgr.validate("discord")
    await mgr.refresh("telegram")
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("overpower.credential_manager")

CREDENTIALS_DIR = Path.home() / ".hermes" / "credentials"


@dataclass
class CredentialEntry:
    """Represents a single platform credential."""
    platform: str
    path: Path
    exists: bool = False
    valid: Optional[bool] = None
    last_checked: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "path": str(self.path),
            "exists": self.exists,
            "valid": self.valid,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }


class CredentialManager:
    """
    Centralized credential management for all platforms.

    Loads, validates, and tracks credential lifecycle.
    Integrates with the EventBus for expiration notifications.
    """

    PLATFORM_CREDENTIALS = {
        "discord": {
            "path": "discord-token.json",
            "type": "json",
            "key": "token",
        },
        "telegram": {
            "path": "telegram-userbot.session",
            "type": "session",
        },
        "telegram_env": {
            "path": "telegram-userbot.env",
            "type": "env",
            "keys": ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"],
        },
        "x": {
            "path": "x-cookies.json",
            "type": "json",
            "key": "cookies",
        },
        "galxe": {
            "path": "galxe-credentials.json",
            "type": "json",
            "key": "token",
        },
        "gleam": {
            "path": "gleam-cookies.json",
            "type": "json",
            "key": "cookies",
        },
        "zealy": {
            "path": "zealy-cookies.json",
            "type": "json",
            "key": "cookies",
        },
        "outlook": {
            "path": "outlook-accounts.json",
            "type": "json",
            "key": "accounts",
        },
    }

    def __init__(self, credentials_dir: Optional[Path] = None):
        self._dir = credentials_dir or CREDENTIALS_DIR
        self._entries: dict[str, CredentialEntry] = {}
        self._event_callback = None

    def set_event_callback(self, callback) -> None:
        """Set callback for credential events (e.g., EventBus.publish)."""
        self._event_callback = callback

    async def load_all(self) -> dict[str, CredentialEntry]:
        """Load and check all platform credentials."""
        for platform, config in self.PLATFORM_CREDENTIALS.items():
            cred_path = self._dir / config["path"]
            entry = CredentialEntry(
                platform=platform,
                path=cred_path,
                exists=cred_path.exists(),
            )
            if entry.exists:
                entry.last_checked = datetime.now(timezone.utc)
                entry.valid = await self._validate_credential(platform, config)
            self._entries[platform] = entry
            logger.info(
                "Credential loaded: %s (exists=%s, valid=%s)",
                platform, entry.exists, entry.valid
            )
        return self._entries

    async def _validate_credential(
        self, platform: str, config: dict
    ) -> bool:
        """Validate a credential file format and basic integrity."""
        cred_path = self._dir / config["path"]
        try:
            if config["type"] == "json":
                with open(cred_path, "r") as f:
                    data = json.load(f)
                key = config.get("key")
                if key and isinstance(data, dict):
                    return key in data and bool(data[key])
                return bool(data)
            elif config["type"] == "session":
                return cred_path.stat().st_size > 0
            elif config["type"] == "env":
                with open(cred_path, "r") as f:
                    content = f.read()
                required_keys = config.get("keys", [])
                return all(k in content for k in required_keys)
            return False
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Credential validation failed for %s: %s", platform, e)
            return False

    async def validate(self, platform: str) -> bool:
        """Re-validate a specific platform's credential."""
        if platform not in self.PLATFORM_CREDENTIALS:
            raise ValueError(f"Unknown platform: {platform}")

        config = self.PLATFORM_CREDENTIALS[platform]
        cred_path = self._dir / config["path"]
        entry = self._entries.get(platform)
        if entry is None:
            entry = CredentialEntry(platform=platform, path=cred_path)

        entry.exists = cred_path.exists()
        entry.last_checked = datetime.now(timezone.utc)
        if entry.exists:
            entry.valid = await self._validate_credential(platform, config)
        else:
            entry.valid = False

        self._entries[platform] = entry
        return entry.valid

    async def refresh(self, platform: str) -> dict[str, Any]:
        """Refresh/reload a credential from disk.

        Returns:
            Updated credential entry as dict.
        """
        await self.validate(platform)
        entry = self._entries.get(platform)
        if entry and entry.valid:
            logger.info("Credential refreshed: %s", platform)
            return entry.to_dict()
        return {"platform": platform, "valid": False, "error": "Credential invalid or missing"}

    def get_status(self) -> dict[str, Any]:
        """Get status of all loaded credentials."""
        return {
            "credentials_dir": str(self._dir),
            "platforms": {
                name: entry.to_dict()
                for name, entry in self._entries.items()
            },
            "summary": {
                "total": len(self._entries),
                "loaded": sum(1 for e in self._entries.values() if e.exists),
                "valid": sum(1 for e in self._entries.values() if e.valid),
                "invalid": sum(
                    1 for e in self._entries.values()
                    if e.exists and e.valid is False
                ),
                "missing": sum(1 for e in self._entries.values() if not e.exists),
            },
        }

    def get_credential_path(self, platform: str) -> Optional[Path]:
        """Get the file path for a platform's credential."""
        if platform not in self.PLATFORM_CREDENTIALS:
            return None
        return self._dir / self.PLATFORM_CREDENTIALS[platform]["path"]
