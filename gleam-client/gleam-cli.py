#!/usr/bin/env python3
"""
Gleam.io CLI
=============
Command-line interface for Gleam.io giveaway automation.

Usage:
    ./gleam-cli.py me                          # Current contestant status
    ./gleam-cli.py campaign <key>              # Campaign details
    ./gleam-cli.py entries <key>               # List entry methods
    ./gleam-cli.py enter <key>                 # Enter contest (register + claim)
    ./gleam-cli.py clear <key> [--dry-run]     # Complete all tasks
    ./gleam-cli.py task <key> <method-id>      # Complete specific task
    ./gleam-cli.py oauth <key>                 # Twitter OAuth via X cookies (no browser)
    ./gleam-cli.py login                       # Auth instructions
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from gleam import GleamClient


def cmd_me(client: GleamClient, args):
    """Show current contestant status."""
    status = client.get_contestant_status()
    
    if not status["authenticated"]:
        print("Not authenticated. Run: ./gleam-cli.py login")
        return
    
    c = status["contestant"]
    print(f"Name:       {c.get('name', 'N/A')}")
    print(f"Email:      {c.get('email', 'N/A')}")
    print(f"ID:         {c.get('id', 'N/A')}")
    print(f"Country:    {c.get('country_code', 'N/A')}")
    
    auths = c.get("authentications", [])
    if auths:
        print(f"\nConnected Accounts:")
        for a in auths:
            print(f"  - {a.get('provider', '?')}: {a.get('reference', 'N/A')} ({a.get('url', '')})")


def cmd_campaign(client: GleamClient, args):
    """Show campaign details."""
    try:
        campaign = client.get_campaign(args.key)
    except Exception as e:
        print(f"Error: {e}")
        return
    
    print(f"Name:       {campaign.get('name', 'N/A')}")
    print(f"Key:        {args.key}")
    print(f"URL:        https://gleam.io/{args.key}")
    print(f"Status:     {campaign.get('state', 'N/A')}")
    
    # Prizes
    prizes = campaign.get("prizes", [])
    if prizes:
        print(f"\nPrizes ({len(prizes)}):")
        for p in prizes:
            print(f"  - {p.get('name', 'N/A')}: {p.get('description', '')}")
    
    # Entry methods
    entry_methods = campaign.get("entry_methods", [])
    if entry_methods:
        print(f"\nEntry Methods ({len(entry_methods)}):")
        for em in entry_methods:
            em_id = em.get("id", "?")
            em_type = em.get("entry_type", "custom")
            em_title = client._entry_method_title(em)
            print(f"  [{em_id}] {em_type}: {em_title}")


def cmd_entries(client: GleamClient, args):
    """List entry methods for a campaign."""
    try:
        entries = client.get_entry_methods(args.key)
    except Exception as e:
        print(f"Error: {e}")
        return
    
    print(f"Entry Methods for {args.key} ({len(entries)}):\n")
    for em in entries:
        em_id = em.get("id", "?")
        em_type = em.get("entry_type", "custom")
        em_title = client._entry_method_title(em)
        em_worth = em.get("worth", 0)

        print(f"[{em_id}] {em_type}")
        print(f"  Title: {em_title}")
        print(f"  Worth: {em_worth}")
        print()


def cmd_enter(client: GleamClient, args):
    """Enter a contest (register + claim)."""
    firstname = args.firstname or "Waguri"
    lastname = args.lastname or "Agent"
    email = args.email or "waguriagent@gmail.com"
    
    print(f"Entering contest {args.key} as {firstname} {lastname} ({email})...")
    
    try:
        result = client.enter_contest(args.key, firstname, lastname, email)
        
        if result.get("registered"):
            print("Registered successfully!")
        if result.get("claimed"):
            print("Claimed successfully!")
        
        c = result.get("contestant", {})
        if c:
            print(f"\nContestant: {c.get('name', 'N/A')} (ID: {c.get('id', 'N/A')})")
    except Exception as e:
        print(f"Error: {e}")


def cmd_clear(client: GleamClient, args):
    """Clear all tasks in a campaign."""
    firstname = args.firstname or "Waguri"
    lastname = args.lastname or "Agent"
    email = args.email or "waguriagent@gmail.com"
    
    print(f"Scanning tasks for {args.key}...")
    
    results = client.clear_campaign(
        args.key, firstname, lastname, email, dry_run=args.dry_run
    )
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for r in results:
        if "error" in r:
            print(f"  [ERROR] {r.get('error', 'Unknown')}")
            fail_count += 1
            continue
        
        entry_id = r.get("entry_method_id", "?")
        title = r.get("title", "Unknown")
        task_type = r.get("type", "custom")
        
        if args.dry_run:
            auto = r.get("auto_completable", False)
            action = "AUTO" if auto else "MANUAL"
            print(f"  [{action}] {title} ({task_type})")
            if auto:
                skip_count += 1
            continue
        
        success = r.get("success", False)
        if success:
            print(f"  [OK]    {title} ({task_type})")
            success_count += 1
        else:
            data = r.get("data")
            error = r.get("error")
            if not error and isinstance(data, dict):
                error = data.get("error") or data.get("raw") or "no worth credited"
            elif not error:
                error = str(data)[:80] if data else "Unknown error"
            print(f"  [FAIL]  {title} ({task_type}): {error}")
            fail_count += 1
    
    if args.dry_run:
        print(f"\nSummary: {skip_count} auto-completable, {len(results) - skip_count} manual")
    else:
        print(f"\nSummary: {success_count} completed, {fail_count} failed")


def cmd_task(client: GleamClient, args):
    """Complete a specific task (auto-detects CEX UID / Twitter / visit URL)."""
    print(f"Completing task {args.method_id} in {args.key}...")

    try:
        campaign = client.get_campaign(args.key)
    except Exception as e:
        print(f"Error fetching campaign: {e}")
        return

    em = next(
        (m for m in campaign.get("entry_methods", []) if str(m.get("id")) == str(args.method_id)),
        None,
    )
    if not em:
        print(f"Entry method {args.method_id} not found in campaign {args.key}")
        return

    try:
        result = client.complete_entry_method(args.key, em, value_override=args.value)
    except Exception as e:
        print(f"Error: {e}")
        return

    if result.get("success"):
        print("Task completed successfully!")
    else:
        error = result.get("error")
        if not error:
            data = result.get("data")
            error = data.get("error") if isinstance(data, dict) else str(data)
        print(f"Failed: {error}")
    print(json.dumps(result.get("data", {}), indent=2))


def cmd_oauth(client: GleamClient, args):
    """Run Twitter OAuth flow without a browser (uses X cookies)."""
    print(f"Running Twitter OAuth for campaign {args.key}...")

    try:
        data = client.oauth_twitter(args.key, args.method_id or "")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"OAuth failed: {e}")
        return

    c = data.get("contestant", {})
    print("OAuth successful!")
    print(f"  Name:   {c.get('name', 'N/A')}")
    print(f"  Email:  {c.get('email', 'N/A')}")
    print(f"  ID:     {c.get('id', 'N/A')}")
    print(f"  Cert:   {(c.get('cert') or '')[:32]}...")
    auths = c.get("authentications", [])
    if auths:
        for a in auths:
            print(f"  {a.get('provider', '?')}: @{a.get('reference', '?')}")


def cmd_login(client: GleamClient, args):
    """Show login instructions."""
    print("""
Gleam.io uses Twitter OAuth for authentication.
To get auth cookies:

1. Open Chrome and go to any Gleam.io giveaway
2. Click "Sign in with Twitter"
3. Complete the OAuth flow
4. Open DevTools (F12) → Application → Cookies
5. Copy these cookies:
   - gleam_csrf (CSRF token)
   - _gleam_session (session cookie)
   - contestant_cert (cert token, if present)

Then run:
    ./gleam-cli.py set-cookies --csrf <gleam_csrf> --session <_gleam_session> --cert <contestant_cert>

Or create ~/.hermes/credentials/gleam-cookies.json:
{
  "cookies": {
    "gleam_csrf": "...",
    "_gleam_session": "...",
    "contestant_cert": "..."
  },
  "csrf_token": "...",
  "contestant": {
    "id": 123456,
    "cert": "...",
    "name": "Waguri Agent",
    "email": "waguriagent@gmail.com"
  }
}
""")


def cmd_set_cookies(client: GleamClient, args):
    """Set cookies manually."""
    cookies = {}
    if args.session:
        cookies["_gleam_session"] = args.session
    if args.cert:
        cookies["contestant_cert"] = args.cert
    
    csrf_token = args.csrf or ""
    
    if client.login_with_cookies(cookies, csrf_token):
        print("Login successful!")
        cmd_me(client, args)
    else:
        print("Login failed. Check your cookies.")


def main():
    parser = argparse.ArgumentParser(
        description="Gleam.io CLI — giveaway automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # me
    subparsers.add_parser("me", help="Current contestant status")

    # campaign
    p_campaign = subparsers.add_parser("campaign", help="Campaign details")
    p_campaign.add_argument("key", help="Campaign key (e.g., MPPty)")

    # entries
    p_entries = subparsers.add_parser("entries", help="List entry methods")
    p_entries.add_argument("key", help="Campaign key")

    # enter
    p_enter = subparsers.add_parser("enter", help="Enter contest")
    p_enter.add_argument("key", help="Campaign key")
    p_enter.add_argument("--firstname", "-f", help="First name")
    p_enter.add_argument("--lastname", "-l", help="Last name")
    p_enter.add_argument("--email", "-e", help="Email")

    # clear
    p_clear = subparsers.add_parser("clear", help="Complete all tasks")
    p_clear.add_argument("key", help="Campaign key")
    p_clear.add_argument("--dry-run", "-n", action="store_true", help="Preview only")
    p_clear.add_argument("--firstname", "-f", help="First name")
    p_clear.add_argument("--lastname", "-l", help="Last name")
    p_clear.add_argument("--email", "-e", help="Email")

    # task
    p_task = subparsers.add_parser("task", help="Complete specific task")
    p_task.add_argument("key", help="Campaign key")
    p_task.add_argument("method_id", help="Entry method ID")
    p_task.add_argument("--value", "-v", help="Answer/URL to submit (for custom_action / visit_url)")

    # oauth
    p_oauth = subparsers.add_parser("oauth", help="Twitter OAuth via X cookies (no browser)")
    p_oauth.add_argument("key", help="Campaign key")
    p_oauth.add_argument("--method-id", "-m", help="Optional entry method ID")

    # login
    subparsers.add_parser("login", help="Login instructions")

    # set-cookies
    p_cookies = subparsers.add_parser("set-cookies", help="Set cookies manually")
    p_cookies.add_argument("--csrf", help="CSRF token")
    p_cookies.add_argument("--session", help="Session cookie")
    p_cookies.add_argument("--cert", help="Cert token")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    client = GleamClient()

    commands = {
        "me": cmd_me,
        "campaign": cmd_campaign,
        "entries": cmd_entries,
        "enter": cmd_enter,
        "clear": cmd_clear,
        "task": cmd_task,
        "oauth": cmd_oauth,
        "login": cmd_login,
        "set-cookies": cmd_set_cookies,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(client, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
