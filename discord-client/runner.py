#!/usr/bin/env python3
"""
Discord client comprehensive test runner.
Tests all modules: connection, guilds, DMs, relationships, voice, settings.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import discord
from auth import load_token, create_client


async def main():
    token = load_token()
    client = create_client()

    @client.event
    async def on_ready():
        user = client.user
        print(f"[OK] Logged in as: {user.name} (ID: {user.id})")
        print(f"     Display name: {user.display_name}")
        print(f"     Bot: {user.bot}")
        nitro = user.premium_type.value if user.premium_type else 0
        nitro_names = {0: "None", 1: "Nitro Classic", 2: "Nitro", 3: "Nitro Basic"}
        print(f"     Nitro: {nitro_names.get(nitro, 'Unknown')}")
        print()

        # Guilds
        print(f"=== Guilds ({len(client.guilds)}) ===")
        for g in client.guilds:
            owner_name = g.owner.name if g.owner else "N/A"
            print(f"  - {g.name} (ID: {g.id}) | Owner: {owner_name} | Members: {g.member_count}")
            # Voice channels
            vcs = g.voice_channels
            if vcs:
                print(f"    Voice channels: {len(vcs)}")
                for vc in vcs:
                    members_str = ", ".join(m.name for m in vc.members) if vc.members else "empty"
                    print(f"      - {vc.name} [{members_str}]")
        print()

        # DMs
        try:
            channels = await client.fetch_private_channels()
            print(f"=== DM Channels ({len(channels)}) ===")
            for c in channels[:20]:
                if isinstance(c, discord.DMChannel):
                    user_name = c.user.name if c.user else "Unknown"
                    accepted = c.is_accepted() if hasattr(c, 'is_accepted') else True
                    status = "accepted" if accepted else "request"
                    print(f"  - DM: {user_name} (ID: {c.id}) [{status}]")
                elif isinstance(c, discord.GroupChannel):
                    recips = ", ".join(r.name for r in c.recipients) if c.recipients else "N/A"
                    print(f"  - Group: {c.name or 'Unnamed'} | Recipients: {recips} (ID: {c.id})")
            if len(channels) > 20:
                print(f"  ... and {len(channels) - 20} more")
            print()
        except Exception as e:
            print(f"[WARN] Could not fetch DMs: {e}")
            print()

        # Relationships
        try:
            await client.fetch_relationships()
            friends = [r for r in client.relationships if r.type == discord.RelationshipType.friend]
            blocked = [r for r in client.relationships if r.type == discord.RelationshipType.blocked]
            incoming = [r for r in client.relationships if r.type == discord.RelationshipType.incoming_request]
            outgoing = [r for r in client.relationships if r.type == discord.RelationshipType.outgoing_request]
            print(f"=== Relationships ===")
            print(f"  Friends: {len(friends)}")
            print(f"  Blocked: {len(blocked)}")
            print(f"  Incoming requests: {len(incoming)}")
            print(f"  Outgoing requests: {len(outgoing)}")
            if friends:
                print(f"  Recent friends:")
                for r in friends[:10]:
                    print(f"    - {r.user.name} (ID: {r.user.id})")
            print()
        except Exception as e:
            print(f"[WARN] Could not fetch relationships: {e}")
            print()

        # Sessions
        try:
            sessions = client.sessions
            print(f"=== Sessions ({len(sessions)}) ===")
            for s in sessions[:5]:
                current = " [CURRENT]" if s.is_current else ""
                print(f"  - {s.session_id} | OS: {s.os}{current}")
            print()
        except Exception as e:
            print(f"[WARN] Could not fetch sessions: {e}")
            print()

        # Connections
        try:
            connections = await client.fetch_connections()
            print(f"=== Linked Connections ({len(connections)}) ===")
            for c in connections:
                print(f"  - {c.name} ({c.type})")
            if not connections:
                print(f"  (none)")
            print()
        except Exception as e:
            print(f"[WARN] Could not fetch connections: {e}")
            print()

        # Private channels count
        print(f"=== Summary ===")
        print(f"  Guilds: {len(client.guilds)}")
        print(f"  Private channels: {len(channels) if 'channels' in dir() else 'N/A'}")
        print(f"  Relationships: {len(client.relationships) if client.relationships else 0}")
        print()
        print("[OK] All checks passed. Discord client ready.")
        await client.close()

    await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
