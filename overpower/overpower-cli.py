#!/usr/bin/env python3
"""
Overpower CLI — Unified command-line interface for the Overpower hub.

Provides a single entry point to control all connected platforms,
relay messages, run quests, and check status.

Usage:
    python overpower-cli.py init [--platforms telegram,discord,x]
    python overpower-cli.py status [--platform PLATFORM]
    python overpower-cli.py health
    python overpower-cli.py relay <source> <dest> <message> [--target ID]
    python overpower-cli.py post <message> [--platforms telegram,discord,x]
    python overpower-cli.py quests [--platform PLATFORM] [--limit N]
    python overpower-cli.py pipeline <quest_id>
    python overpower-cli.py presence <status> [--custom TEXT]
    python overpower-cli.py events [--platform PLATFORM] [--limit N]
    python overpower-cli.py shutdown
"""

import argparse
import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from overpower.hub import OverpowerHub


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="overpower",
        description="Overpower Hub CLI — Unified multi-platform control",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize hub and connect platforms")
    init_parser.add_argument(
        "--platforms", "-p",
        default="telegram,discord,x",
        help="Comma-separated list of platforms to initialize",
    )
    init_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip credential validation",
    )

    # status
    status_parser = subparsers.add_parser("status", help="Show unified status dashboard")
    status_parser.add_argument(
        "--platform",
        help="Show status for specific platform only",
    )
    status_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    # health
    subparsers.add_parser("health", help="Quick health check across all platforms")

    # relay
    relay_parser = subparsers.add_parser("relay", help="Relay message between platforms")
    relay_parser.add_argument("source", help="Source platform")
    relay_parser.add_argument("dest", help="Destination platform")
    relay_parser.add_argument("message", help="Message content")
    relay_parser.add_argument("--target", type=int, default=None, help="Target chat/channel ID")

    # post
    post_parser = subparsers.add_parser("post", help="Post to multiple platforms")
    post_parser.add_argument("message", help="Content to post")
    post_parser.add_argument(
        "--platforms", "-p",
        default="telegram,discord,x",
        help="Comma-separated list of platforms",
    )
    post_parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Target chat/channel ID (applied to all platforms)",
    )

    # quests
    quests_parser = subparsers.add_parser("quests", help="Discover available quests")
    quests_parser.add_argument("--platform", help="Platform to search on")
    quests_parser.add_argument("--limit", type=int, default=20, help="Max results")

    # pipeline
    pipeline_parser = subparsers.add_parser("pipeline", help="Run quest pipeline")
    pipeline_parser.add_argument("quest_id", help="Quest identifier")

    # presence
    presence_parser = subparsers.add_parser("presence", help="Sync presence across platforms")
    presence_parser.add_argument("status", help="Status: online, offline, dnd, idle")
    presence_parser.add_argument("--custom", help="Custom status text")
    presence_parser.add_argument(
        "--platforms", "-p",
        default=None,
        help="Platforms to update (default: all)",
    )

    # events
    events_parser = subparsers.add_parser("events", help="Show event history")
    events_parser.add_argument("--platform", help="Filter by platform")
    events_parser.add_argument("--type", help="Filter by event type")
    events_parser.add_argument("--limit", type=int, default=20, help="Max events")

    # shutdown
    subparsers.add_parser("shutdown", help="Shutdown the hub")

    return parser


async def cmd_init(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Initialize the hub."""
    platforms = [p.strip() for p in args.platforms.split(",")]
    print(f"Initializing Overpower Hub with platforms: {', '.join(platforms)}")
    result = await hub.initialize(
        platforms=platforms,
        validate_credentials=not args.no_validate,
    )
    print(f"Status: {result['status']}")
    print(f"Connected: {', '.join(result['connected'])}")
    for platform, status in result['platforms'].items():
        print(f"  {platform}: {status}")
    print(f"Event handlers: {result['event_handlers']}")


async def cmd_status(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Show status."""
    if args.platform:
        status = await hub.dashboard.get_platform_status(args.platform)
    else:
        status = await hub.get_unified_status()

    if args.json:
        print(json.dumps(status, indent=2, default=str))
    else:
        if "summary" in status:
            s = status["summary"]
            print(f"=== Overpower Status ===")
            print(f"  Health: {s['health']}")
            print(f"  Connected: {s['connected']}/{s['total_platforms']}")
            print(f"  Errors: {s['total_errors']}")
            print()
        for name, info in status.get("platforms", {}).items() if isinstance(status.get("platforms"), dict) else []:
            icon = "+" if info.get("connected") else "-"
            account = info.get("account_name") or info.get("account_id") or "N/A"
            print(f"  [{icon}] {name}: {account}")
            if info.get("errors"):
                for err in info["errors"]:
                    print(f"      Error: {err}")


async def cmd_health(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Quick health check."""
    health = await hub.dashboard.health_check()
    print(f"Overall: {health['overall']}")
    print(f"Healthy: {health['healthy']}/{health['total']}")
    for platform, status in health["platforms"].items():
        icon = "+" if status == "ok" else "!"
        print(f"  [{icon}] {platform}: {status}")


async def cmd_relay(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Relay a message."""
    success = await hub.relay_message(
        source=args.source,
        destination=args.dest,
        message=args.message,
        target=args.target,
    )
    if success:
        print(f"Relayed: {args.source} -> {args.dest}")
    else:
        print(f"Relay failed: {args.source} -> {args.dest}")


async def cmd_post(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Post to multiple platforms."""
    platforms = [p.strip() for p in args.platforms.split(",")]
    targets = {}
    if args.target:
        targets = {p: args.target for p in platforms}

    results = await hub.sync_post(
        content=args.message,
        platforms=platforms,
        targets=targets if targets else None,
    )
    for platform, result in results.items():
        status = "OK" if result.success else f"FAILED: {result.error}"
        print(f"  [{platform}] {status}")


async def cmd_quests(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Discover quests."""
    platforms = [args.platform] if args.platform else None
    quests = await hub.discover_quests(platforms=platforms)
    print(f"Found {len(quests)} quests:")
    for q in quests[:args.limit]:
        print(
            f"  [{q.get('platform', '?')}] {q.get('name', 'Unknown')}"
            f" (ID: {q.get('id', '?')}) — {q.get('status', '?')}"
        )


async def cmd_pipeline(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Run quest pipeline."""
    print(f"Running pipeline for: {args.quest_id}")
    result = await hub.run_quest_pipeline(args.quest_id)
    r = result
    print(f"  Status: {r.status.value}")
    print(f"  Tasks: {r.tasks_completed}/{r.tasks_total} completed, {r.tasks_failed} failed")
    print(f"  Duration: {r.duration_seconds:.1f}s")
    if r.rewards:
        print(f"  Rewards: {r.rewards}")
    if r.errors:
        print(f"  Errors:")
        for err in r.errors:
            print(f"    - {err}")


async def cmd_presence(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Sync presence."""
    platforms = (
        [p.strip() for p in args.platforms.split(",")]
        if args.platforms
        else None
    )
    results = await hub.sync_presence(
        status=args.status,
        platforms=platforms,
        custom_text=args.custom,
    )
    for platform, result in results.items():
        status = "OK" if result.success else f"FAILED: {result.error}"
        print(f"  [{platform}] {status}")


async def cmd_events(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Show event history."""
    events = hub.event_bus.get_history(
        event_type=args.type,
        platform=args.platform,
        limit=args.limit,
    )
    print(f"Events ({len(events)}):")
    for event in events:
        ts = event.get("timestamp", "")[:19]
        print(
            f"  [{ts}] {event.get('platform', '?')}.{event.get('type', '?')}"
        )


async def cmd_shutdown(hub: OverpowerHub, args: argparse.Namespace) -> None:
    """Shutdown the hub."""
    await hub.shutdown()
    print("Overpower Hub shut down.")


async def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    hub = OverpowerHub()

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "health": cmd_health,
        "relay": cmd_relay,
        "post": cmd_post,
        "quests": cmd_quests,
        "pipeline": cmd_pipeline,
        "presence": cmd_presence,
        "events": cmd_events,
        "shutdown": cmd_shutdown,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return

    try:
        await handler(hub, args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
