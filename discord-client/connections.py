"""
Discord connections module — manage linked accounts (Spotify, GitHub, etc).
Uses discord.py-self.
"""

import discord
from typing import Optional, List


async def get_connections(client: discord.Client) -> List[dict]:
    """List all linked connections."""
    connections = await client.fetch_connections()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "type": c.type,
            "verified": c.verified if hasattr(c, "verified") else None,
            "visible": c.visible if hasattr(c, "visible") else None,
            "two_way_link": c.two_way_link if hasattr(c, "two_way_link") else None,
            "metadata_verbosity": c.metadata_verbosity if hasattr(c, "metadata_verbosity") else None,
        }
        for c in connections
    ]


async def edit_connection(
    connection: discord.Connection,
    name: Optional[str] = None,
    visible: Optional[bool] = None,
    metadata_verbosity: Optional[int] = None,
) -> None:
    """Edit a connection's settings."""
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if visible is not None:
        kwargs["visible"] = visible
    if metadata_verbosity is not None:
        kwargs["metadata_verbosity"] = metadata_verbosity
    await connection.edit(**kwargs)


async def delete_connection(connection: discord.Connection) -> None:
    """Delete/unlink a connection."""
    await connection.delete()


async def refresh_connection(connection: discord.Connection) -> None:
    """Refresh a connection's metadata."""
    await connection.refresh()


async def authorize_connection(
    client: discord.Client,
    url: str,
) -> None:
    """Authorize a new connection via OAuth2 URL."""
    await client.authorize_connection(url)
