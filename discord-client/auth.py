"""
Discord authentication module.
Uses discord.py-self (user token, no bot prefix).
"""

import json
import discord
from pathlib import Path

TOKEN_PATH = Path.home() / ".hermes" / "credentials" / "discord-token.json"


def load_token() -> str:
    """Load user token from credentials file."""
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"Token file not found: {TOKEN_PATH}\n"
            'Create it with: {{"token": "your_user_token"}}'
        )
    try:
        data = json.loads(TOKEN_PATH.read_text())
    except PermissionError:
        raise PermissionError(f"Permission denied reading token file: {TOKEN_PATH}")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(
            f"Token file is not valid JSON: {TOKEN_PATH}", doc="", pos=0
        )
    token = data.get("token", "")
    if not token:
        raise ValueError("Token is empty in credentials file")
    return token


def create_client(**kwargs) -> discord.Client:
    """Create discord.py-self Client (no intents needed)."""
    return discord.Client(**kwargs)


async def get_account_info(client: discord.Client) -> dict:
    """Get current account info (call after login)."""
    user = client.user
    return {
        "id": str(user.id),
        "username": user.name,
        "display_name": user.display_name,
        "discriminator": user.discriminator,
        "avatar_url": str(user.display_avatar.url) if user.display_avatar else None,
        "bot": user.bot,
        "guild_count": len(client.guilds),
        "dm_count": len(client.private_channels),
    }
