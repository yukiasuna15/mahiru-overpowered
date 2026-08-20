#!/usr/bin/env python3
"""
Engage IO CLI — auto-engage to X/Twitter posts from The Engage Discord bot.

Usage:
  python3 engage-cli.py status                              # Check auth status
  python3 engage-cli.py list                                # List all engagements
  python3 engage-cli.py add <guild_id> <channel_id> [--name NAME] [--bot-id ID]
  python3 engage-cli.py switch <guild_id:channel_id>        # Switch active engagement
  python3 engage-cli.py remove <guild_id:channel_id>        # Remove an engagement
  python3 engage-cli.py latest [--count N] [--dry-run]      # Engage latest N posts
  python3 engage-cli.py watch [--dry-run]                   # Continuous monitor mode
  python3 engage-cli.py scan                                # One-shot: engage all unprocessed posts
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from engage import (
    load_discord_token,
    x_engage,
    x_reply,
    x_quote,
    fetch_latest_messages,
    extract_tweet_info,
    click_proceed_button,
    engage_latest,
    run_monitor,
    StateManager,
    ENGAGE_BOT_ID,
    ENGAGE_POLL_INTERVAL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("engage-cli")


def print_task(task):
    """Print an EngageTask result."""
    if task.skipped:
        print(f"  SKIP  msg={task.message_id} — {task.skip_reason}")
        return

    status_parts = []
    if task.x_liked:
        status_parts.append("liked")
    if task.x_retweeted:
        status_parts.append("RT'd")
    if task.x_replied:
        status_parts.append(f"replied({task.reply_text})")
    if task.x_quoted:
        status_parts.append(f"quoted({task.quote_text})")
    if task.proceed_clicked:
        status_parts.append("proceeded")
    if task.error:
        status_parts.append(f"ERR: {task.error}")

    icon = "OK" if not task.error else "!!"
    print(f"  [{icon}] {task.tweet_url}")
    print(f"      msg={task.message_id} | {', '.join(status_parts) if status_parts else 'no action'}")


def require_active(state: StateManager):
    """Print error and exit if no active engagement."""
    if not state.active_engagement:
        print("No active engagement configured.")
        print("Use: python3 engage-cli.py add <guild_id> <channel_id>")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def cmd_status(args):
    """Check auth status for Discord and X."""
    state = StateManager()
    eng = state.active_engagement

    # Discord
    print("Discord:")
    token = None
    try:
        token = load_discord_token()
        print(f"  Token loaded ({len(token)} chars)")
        import requests
        resp = requests.get(
            "https://discord.com/api/v9/users/@me",
            headers={"Authorization": token, "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Logged in as: {data['username']} (ID: {data['id']})")
        else:
            print(f"  Auth failed: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  Error: {e}")

    # X
    print("\nX/Twitter:")
    try:
        import sys as _sys
        _sys.path.insert(0, "/home/ubuntu/scripts/x-client")
        from auth import get_client
        client = await get_client()
        me = await client.user()
        print(f"  Logged in as: @{me.screen_name} (ID: {me.id})")
    except Exception as e:
        print(f"  Error: {e}")

    # Active engagement
    print("\nActive engagement:")
    if eng:
        print(f"  {state.active_key} ({eng.get('bot_name', '?')})")
        print(f"  Channel: {eng['channel_id']}")
        print(f"  Guild: {eng['guild_id']}")
        print(f"  Engaged messages: {eng.get('total_engaged', 0)}")
        print(f"  Last checked: {eng.get('last_checked', 'never')}")

        if token:
            try:
                messages = fetch_latest_messages(token, eng["channel_id"], limit=5)
                engage_msgs = [m for m in messages if m.get("author", {}).get("id") == eng.get("bot_id", ENGAGE_BOT_ID)]
                print(f"  Latest {len(engage_msgs)} Engage messages in channel")
                if engage_msgs:
                    latest = engage_msgs[0]
                    ts = latest.get("timestamp", "?")
                    info = extract_tweet_info(latest)
                    if info:
                        tweet_id, tweet_url, _, _ = info
                        print(f"  Latest post: {tweet_url} (posted {ts})")
                    else:
                        print(f"  Latest message (no tweet URL): {latest.get('content', '')[:80]}")
            except Exception as e:
                print(f"  Error fetching channel: {e}")
    else:
        print("  None configured. Use: python3 engage-cli.py add <guild_id> <channel_id>")

    # All engagements
    all_eng = state.list_engagements()
    if len(all_eng) > 1:
        print(f"\nAll engagements ({len(all_eng)}):")
        for key, e in all_eng.items():
            marker = " *" if key == state.active_key else ""
            print(f"  {marker} {key} ({e.get('bot_name', '?')}) — {e.get('total_engaged', 0)} engaged")


def cmd_list(args):
    """List all configured engagements."""
    state = StateManager()
    engagements = state.list_engagements()

    if not engagements:
        print("No engagements configured.")
        print("Use: python3 engage-cli.py add <guild_id> <channel_id>")
        return

    print(f"Engagements ({len(engagements)}):\n")
    for key, eng in engagements.items():
        marker = " *" if key == state.active_key else " "
        print(f" [{marker}] {key}")
        print(f"      Bot: {eng.get('bot_name', '?')} (ID: {eng.get('bot_id', '?')})")
        print(f"      Engaged: {eng.get('total_engaged', 0)} messages")
        print(f"      Last checked: {eng.get('last_checked', 'never')}")
        print()
    print("  * = active")


def cmd_add(args):
    """Add a new engagement target."""
    state = StateManager()
    key = state.add_engagement(
        guild_id=args.guild_id,
        channel_id=args.channel_id,
        bot_id=args.bot_id,
        bot_name=args.name,
    )
    print(f"Added engagement: {key}")
    if state.active_key == key:
        print("Set as active engagement.")
    else:
        print(f"Active engagement is still: {state.active_key}")


def cmd_switch(args):
    """Switch active engagement."""
    state = StateManager()
    if state.switch_active(args.key):
        eng = state.active_engagement
        print(f"Switched to: {args.key} ({eng.get('bot_name', '?')})")
    else:
        print(f"Engagement not found: {args.key}")
        print("Available:")
        for key in state.list_engagements():
            print(f"  {key}")


def cmd_remove(args):
    """Remove an engagement."""
    state = StateManager()
    if state.remove_engagement(args.key):
        print(f"Removed: {args.key}")
        if state.active_key:
            print(f"Active: {state.active_key}")
        else:
            print("No active engagement remaining.")
    else:
        print(f"Engagement not found: {args.key}")


async def cmd_latest(args):
    """Engage the latest N posts."""
    state = StateManager()
    require_active(state)

    eng = state.active_engagement
    print(f"Engaging latest {args.count} posts from {state.active_key} (dry_run={args.dry_run}):\n")

    results = await engage_latest(
        state=state,
        count=args.count,
        do_like=not args.no_like,
        do_retweet=not args.no_retweet,
        do_reply=not args.no_reply,
        do_quote=not args.no_quote,
        do_proceed=not args.no_proceed,
        dry_run=args.dry_run,
    )

    if not results:
        print("  No new Engage messages found.")
        return

    for task in results:
        print_task(task)
        print()

    ok = sum(1 for t in results if not t.skipped and not t.error)
    skip = sum(1 for t in results if t.skipped)
    err = sum(1 for t in results if t.error)
    print(f"Summary: {ok} engaged, {skip} skipped, {err} errors")


async def cmd_watch(args):
    """Continuous monitor mode."""
    state = StateManager()
    require_active(state)

    eng = state.active_engagement
    print(f"Watching {state.active_key} every {ENGAGE_POLL_INTERVAL}s")
    print(f"Actions: like={not args.no_like}, rt={not args.no_retweet}, reply={not args.no_reply}, quote={not args.no_quote}, proceed={not args.no_proceed}")
    print(f"Dry run: {args.dry_run}")
    print("Press Ctrl+C to stop.\n")

    await run_monitor(
        state=state,
        do_like=not args.no_like,
        do_retweet=not args.no_retweet,
        do_reply=not args.no_reply,
        do_quote=not args.no_quote,
        do_proceed=not args.no_proceed,
        dry_run=args.dry_run,
    )


async def cmd_scan(args):
    """One-shot: scan and engage all unprocessed posts."""
    state = StateManager()
    require_active(state)

    print(f"Scanning for unprocessed Engage posts on {state.active_key}...\n")

    results = await engage_latest(
        state=state,
        count=50,
        do_like=not args.no_like,
        do_retweet=not args.no_retweet,
        do_reply=not args.no_reply,
        do_proceed=not args.no_proceed,
        dry_run=args.dry_run,
    )

    if not results:
        print("  No new Engage messages found.")
        return

    for task in results:
        print_task(task)
        print()

    ok = sum(1 for t in results if not t.skipped and not t.error)
    skip = sum(1 for t in results if t.skipped)
    err = sum(1 for t in results if t.error)
    print(f"Summary: {ok} engaged, {skip} skipped, {err} errors")


def main():
    parser = argparse.ArgumentParser(description="Engage IO auto-engagement CLI")
    sub = parser.add_subparsers(dest="command", help="Command")

    # status
    sub.add_parser("status", help="Check auth status and active engagement")

    # list
    sub.add_parser("list", help="List all configured engagements")

    # add
    p_add = sub.add_parser("add", help="Add a new engagement target")
    p_add.add_argument("guild_id", help="Discord guild/server ID")
    p_add.add_argument("channel_id", help="Discord channel ID")
    p_add.add_argument("--name", default="Unknown", help="Friendly name (default: Unknown)")
    p_add.add_argument("--bot-id", default=ENGAGE_BOT_ID, help=f"Bot author ID (default: {ENGAGE_BOT_ID})")

    # switch
    p_switch = sub.add_parser("switch", help="Switch active engagement")
    p_switch.add_argument("key", help="Engagement key (guild_id:channel_id)")

    # remove
    p_remove = sub.add_parser("remove", help="Remove an engagement")
    p_remove.add_argument("key", help="Engagement key (guild_id:channel_id)")

    # latest
    p_latest = sub.add_parser("latest", help="Engage latest N posts")
    p_latest.add_argument("--count", type=int, default=5, help="Number of posts (default: 5)")
    p_latest.add_argument("--dry-run", action="store_true", help="Don't actually engage")
    p_latest.add_argument("--no-like", action="store_true", help="Skip liking")
    p_latest.add_argument("--no-retweet", action="store_true", help="Skip retweeting")
    p_latest.add_argument("--no-reply", action="store_true", help="Skip replying to tweet")
    p_latest.add_argument("--no-quote", action="store_true", help="Skip quote tweeting")
    p_latest.add_argument("--no-proceed", action="store_true", help="Skip proceed button")

    # watch
    p_watch = sub.add_parser("watch", help="Continuous monitor mode")
    p_watch.add_argument("--dry-run", action="store_true", help="Don't actually engage")
    p_watch.add_argument("--no-like", action="store_true", help="Skip liking")
    p_watch.add_argument("--no-retweet", action="store_true", help="Skip retweeting")
    p_watch.add_argument("--no-reply", action="store_true", help="Skip replying to tweet")
    p_watch.add_argument("--no-quote", action="store_true", help="Skip quote tweeting")
    p_watch.add_argument("--no-proceed", action="store_true", help="Skip proceed button")

    # scan
    p_scan = sub.add_parser("scan", help="One-shot: engage all unprocessed posts")
    p_scan.add_argument("--dry-run", action="store_true", help="Don't actually engage")
    p_scan.add_argument("--no-like", action="store_true", help="Skip liking")
    p_scan.add_argument("--no-retweet", action="store_true", help="Skip retweeting")
    p_scan.add_argument("--no-reply", action="store_true", help="Skip replying to tweet")
    p_scan.add_argument("--no-quote", action="store_true", help="Skip quote tweeting")
    p_scan.add_argument("--no-proceed", action="store_true", help="Skip proceed button")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    sync_cmds = {"list", "add", "switch", "remove"}
    async_cmds = {"status", "latest", "watch", "scan"}

    if args.command in sync_cmds:
        {"list": cmd_list, "add": cmd_add, "switch": cmd_switch, "remove": cmd_remove}[args.command](args)
    elif args.command in async_cmds:
        asyncio.run({"status": cmd_status, "latest": cmd_latest, "watch": cmd_watch, "scan": cmd_scan}[args.command](args))


if __name__ == "__main__":
    main()
