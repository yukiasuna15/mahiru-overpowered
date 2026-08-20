"""
Waguri X/Twitter Client - Authentication Module
Cookie-based auth via twikit.
"""
import json
import os
from twikit import Client

COOKIES_PATH = os.path.expanduser("~/.hermes/credentials/x-cookies.json")


def new_client():
    """Create a new twikit Client instance."""
    return Client('en-US')


def load_cookies(client: Client, path: str = COOKIES_PATH):
    """Load cookies from file into client."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cookie file not found: {path}")
    try:
        with open(path) as f:
            cookies = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to read/parse cookie file {path}: {e}")
    client.set_cookies(cookies)
    return client


def save_cookies(client: Client, path: str = COOKIES_PATH):
    """Save current client cookies to file."""
    client.save_cookies(path)


async def get_client():
    """Create and return an authenticated client."""
    client = new_client()
    load_cookies(client)
    return client


async def get_me(client: Client = None):
    """Get authenticated user info."""
    if client is None:
        client = await get_client()
    return await client.user()


async def get_user_by_id(user_id: str, client: Client = None):
    """Get user info by ID."""
    if client is None:
        client = await get_client()
    return await client.get_user_by_id(user_id)


async def get_user_by_screen_name(screen_name: str, client: Client = None):
    """Get user info by screen name."""
    if client is None:
        client = await get_client()
    return await client.get_user_by_screen_name(screen_name)
