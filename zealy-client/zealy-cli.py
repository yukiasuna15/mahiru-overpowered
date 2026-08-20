#!/usr/bin/env python3
"""
Zealy CLI — quest discovery, task inspection, and claim automation.

Usage:
    python zealy-cli.py me                          # Show current user
    python zealy-cli.py communities [--search X]    # List communities
    python zealy-cli.py community <slug>            # Community details
    python zealy-cli.py quests <slug>               # List quests (flat)
    python zealy-cli.py quest <slug> <quest-id>     # Quest detail
    python zealy-cli.py claim <slug> <quest-id>     # Claim a quest
    python zealy-cli.py clear <slug> [--dry-run]    # Clear all quests
    python zealy-cli.py recommended                 # Recommended quests
    python zealy-cli.py sprints                     # Active sprints
    python zealy-cli.py login                       # Re-login via OTP
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add parent to path for import
sys.path.insert(0, str(Path(__file__).parent))
from zealy import ZealyClient, AUTO_VERIFY_TYPES, TWITTER_TYPES, TWITTER_AUTOMATABLE


def fmt_task_type(t: str) -> str:
    """Format task type with emoji indicator."""
    if t in AUTO_VERIFY_TYPES:
        return f"[auto] {t}"
    if t in TWITTER_AUTOMATABLE:
        return f"[x-auto] {t}"
    if t in TWITTER_TYPES:
        return f"[twitter] {t}"
    return f"[manual] {t}"


def fmt_twitter_actions(twitter_actions: dict) -> str:
    """Flatten a {taskId: {action: status}} map into a compact one-line string."""
    parts = []
    for actions in (twitter_actions or {}).values():
        for label, status in actions.items():
            parts.append(label if label == "_" else f"{label}={status}")
    return ", ".join(parts)


def cmd_me(client: ZealyClient, args):
    user = client.get_me()
    print(f"Name:     {user.get('name')}")
    print(f"ID:       {user.get('id')}")
    print(f"Email:    {user.get('email', 'N/A')}")
    print(f"Twitter:  @{user.get('twitterUsername', 'N/A')}")
    print(f"Discord:  {user.get('discordHandle', 'N/A')}")
    addrs = user.get("addresses", {})
    if addrs:
        for chain, addr in addrs.items():
            print(f"Wallet:   {chain}={addr}")
    print(f"Country:  {user.get('country', 'N/A')}")
    print(f"City:     {user.get('city', 'N/A')}")


def cmd_communities(client: ZealyClient, args):
    search = args.search or ""
    category = args.category or "all"
    comms = client.list_communities(category=category, limit=args.limit, search=search)
    print(f"{'Name':<30} {'Slug':<20} {'Blockchain':<12} {'Members':>8}")
    print("-" * 75)
    for c in comms:
        name = c.get("name", "?")[:28]
        slug = c.get("subdomain", c.get("urlName", "?"))
        chain = c.get("blockchain", "?")
        members = c.get("memberCount", c.get("membersCount", "?"))
        print(f"{name:<30} {slug:<20} {chain:<12} {str(members):>8}")


def cmd_community(client: ZealyClient, args):
    slug = args.slug
    c = client.get_community(slug)
    print(f"Name:        {c.get('name')}")
    print(f"ID:          {c.get('id')}")
    print(f"Subdomain:   {c.get('subdomain')}")
    print(f"Blockchain:  {c.get('blockchain')}")
    print(f"Website:     {c.get('website')}")
    print(f"Twitter:     @{c.get('twitter', 'N/A')}")
    print(f"Discord:     {c.get('discord', 'N/A')}")
    print(f"Description: {(c.get('description') or '')[:120]}")

    # Show required fields
    rf = c.get("requiredFields", {})
    if rf:
        print(f"\nRequired fields:")
        for k, v in rf.items():
            if v:
                print(f"  - {k}")

    # Show subscription
    try:
        sub = client.get_subscription_status(slug)
        print(f"\nSubscription: limit_reached={sub.get('isLimitReached')}, free_trial={sub.get('canAccessFreeTrial')}")
    except Exception:
        pass


def cmd_quests(client: ZealyClient, args):
    slug = args.slug
    quests = client.list_quests(slug)

    if not quests:
        print("No quests found.")
        return

    print(f"{'Status':<10} {'Name':<45} {'Tasks':<40} {'Reward':<15} {'ID'}")
    print("-" * 140)
    for q in quests:
        qid = q.get("id", "?")
        name = (q.get("name") or q.get("title") or "?")[:43]
        claimed = q.get("claimed", False)
        tasks = q.get("tasks", [])
        task_strs = [t.get("type", "?") for t in tasks]
        rewards = q.get("rewards", [])
        reward_strs = [f"{r.get('value', '?')}{r.get('type', '?')}" for r in rewards]

        status = "DONE" if claimed else "TODO"
        print(f"{status:<10} {name:<45} {', '.join(task_strs):<40} {', '.join(reward_strs):<15} {qid[:12]}")


def cmd_quest(client: ZealyClient, args):
    slug = args.slug
    quest_id = args.quest_id
    q = client.get_quest(slug, quest_id)

    print(f"Name:       {q.get('name')}")
    print(f"ID:         {q.get('id')}")
    print(f"Category:   {q.get('categoryId')}")
    print(f"Recurrence: {q.get('recurrence')}")
    print(f"Claimed:    {q.get('claimed')}")
    print(f"Completed:  {q.get('completed')}")
    print(f"In Review:  {q.get('inReview')}")
    print(f"Locked:     {q.get('locked')}")
    print(f"Can Retry:  {q.get('canRetry')}")

    # Tasks
    tasks = q.get("tasks", [])
    print(f"\nTasks ({len(tasks)}):")
    for i, t in enumerate(tasks, 1):
        ttype = t.get("type", "?")
        tid = t.get("id", "?")
        settings = t.get("settings", {})
        print(f"  {i}. [{fmt_task_type(ttype)}] {tid}")
        if ttype == "twitterFollow":
            print(f"     Follow: @{settings.get('username', '?')}")
        elif ttype == "tweetReact":
            print(f"     Actions: {', '.join(settings.get('actions', []))}")
            print(f"     Tweet:   {settings.get('tweetUrl', 'N/A')}")
        elif ttype == "visitLink":
            print(f"     Link:    {settings.get('linkUrl', 'N/A')}")
        elif ttype == "text":
            print(f"     Title:   {settings.get('title', 'N/A')}")
        elif ttype == "api":
            print(f"     Title:   {settings.get('title', 'N/A')}")
            print(f"     Network: {settings.get('network', 'N/A')}")
        elif ttype == "quiz":
            print(f"     Questions: {len(settings.get('questions', []))}")

    # Rewards
    rewards = q.get("rewards", [])
    if rewards:
        print(f"\nRewards ({len(rewards)}):")
        for r in rewards:
            rtype = r.get("type", "?")
            val = r.get("value", "?")
            method = r.get("method", {}).get("type", "?")
            print(f"  - {val} {rtype} (method: {method})")

    # Conditions
    conditions = q.get("conditions", [])
    if conditions:
        print(f"\nConditions ({len(conditions)}):")
        for cond in conditions:
            print(f"  - {cond}")


def cmd_claim(client: ZealyClient, args):
    from zealy import TWITTER_ACTION_DELAY

    slug = args.slug
    quest_id = args.quest_id
    do_twitter = not getattr(args, "no_twitter", False)

    detail = client.get_quest(slug, quest_id)
    print(f"Claiming: {detail.get('name')}")

    if detail.get("claimed"):
        print("Already claimed. Skipping.")
        return

    # Perform real Twitter actions for any Twitter-gated tasks first.
    tw_tasks = [t for t in detail.get("tasks", []) if t.get("type") in TWITTER_TYPES]
    if do_twitter and tw_tasks:
        print(f"\nPerforming Twitter actions via X client ({len(tw_tasks)} task(s))...")
        for t in tw_tasks:
            res = client.execute_twitter_task(t)
            line = ", ".join(v if k == "_" else f"{k}={v}" for k, v in res.items())
            print(f"  [{t.get('type')}] {line}")
        time.sleep(TWITTER_ACTION_DELAY)
    elif tw_tasks:
        print("\n(skipping Twitter actions: --no-twitter)")

    task_values = client.build_task_values(detail)
    print(f"\nTask values: {json.dumps(task_values, indent=2)}")

    result = client.claim_quest(slug, quest_id, task_values)
    print(f"\nStatus: {result['status_code']}")
    print(json.dumps(result["data"], indent=2))


def cmd_clear(client: ZealyClient, args):
    slug = args.slug
    dry_run = args.dry_run
    do_twitter = not getattr(args, "no_twitter", False)

    if dry_run:
        print(f"[DRY RUN] Scanning quests for {slug}...")
    else:
        print(f"Clearing quests for {slug} (Twitter automation: {'on' if do_twitter else 'off'})...")

    results = client.clear_community(slug, dry_run=dry_run, do_twitter=do_twitter)

    auto_count = 0
    success_count = 0
    fail_count = 0

    for r in results:
        name = r.get("name", "?")[:40]
        task_types = r.get("task_types", [])
        auto = r.get("auto_claimable", r.get("success"))

        if dry_run:
            marker = "AUTO" if auto else "SKIP"
            print(f"  [{marker}] {name} ({', '.join(task_types)})")
            if auto:
                auto_count += 1
        else:
            tw = fmt_twitter_actions(r.get("twitter_actions"))
            tw_suffix = f"  (x: {tw})" if tw else ""
            if r.get("skipped"):
                print(f"  [SKIP] {name}: {r.get('message', '')}")
            elif r.get("success"):
                print(f"  [OK]   {name}{tw_suffix}")
                success_count += 1
            else:
                data = r.get("data", {})
                validations = data.get("taskValidations", [])
                errors = [v.get("error", {}).get("code", "?") for v in validations if v.get("status") == "error"]
                print(f"  [FAIL] {name}: {', '.join(errors) or r.get('error', 'unknown')}{tw_suffix}")
                fail_count += 1

    print(f"\nSummary: {success_count} claimed, {fail_count} failed, {len(results) - success_count - fail_count} skipped")


def cmd_recommended(client: ZealyClient, args):
    quests = client.get_recommended_quests(limit=args.limit)
    print(f"{'Name':<50} {'Community':<20} {'ID'}")
    print("-" * 100)
    for q in quests:
        name = (q.get("name") or "?")[:48]
        comm = q.get("community", {})
        comm_name = comm.get("name", "?")[:18] if isinstance(comm, dict) else "?"
        qid = q.get("id", "?")
        print(f"{name:<50} {comm_name:<20} {qid[:12]}")


def cmd_sprints(client: ZealyClient, args):
    sprints = client.get_sprints()
    print(f"{'Name':<45} {'Community':<20} {'Ends':<22} {'Pool':>10}")
    print("-" * 100)
    for s in sprints:
        name = (s.get("name") or "?")[:43]
        comm = s.get("communityName", "?")[:18]
        ends = (s.get("endingAt") or "?")[:20]
        pool = s.get("usdcPool", 0) / 100
        print(f"{name:<45} {comm:<20} {ends:<22} ${pool:>8.0f}")


def cmd_login(client: ZealyClient, args):
    print("Starting OTP login flow...")
    client.login()
    print("Login successful!")
    user = client.get_me()
    print(f"Logged in as: {user.get('name')} ({user.get('id')})")


def main():
    parser = argparse.ArgumentParser(description="Zealy CLI — quest automation tool")
    sub = parser.add_subparsers(dest="command", help="Command")

    # me
    sub.add_parser("me", help="Show current user profile")

    # communities
    p = sub.add_parser("communities", help="List communities")
    p.add_argument("--search", "-s", default="", help="Search query")
    p.add_argument("--category", "-c", default="all", choices=["all", "featured", "upcoming"])
    p.add_argument("--limit", "-l", type=int, default=20)

    # community
    p = sub.add_parser("community", help="Community details")
    p.add_argument("slug", help="Community subdomain/slug")

    # quests
    p = sub.add_parser("quests", help="List quests in a community")
    p.add_argument("slug", help="Community subdomain/slug")

    # quest
    p = sub.add_parser("quest", help="Quest detail")
    p.add_argument("slug", help="Community subdomain/slug")
    p.add_argument("quest_id", help="Quest ID")

    # claim
    p = sub.add_parser("claim", help="Claim a quest (auto-performs Twitter actions)")
    p.add_argument("slug", help="Community subdomain/slug")
    p.add_argument("quest_id", help="Quest ID")
    p.add_argument("--no-twitter", action="store_true", help="Don't perform Twitter actions, just submit the claim")

    # clear
    p = sub.add_parser("clear", help="Clear all quests in a community")
    p.add_argument("slug", help="Community subdomain/slug")
    p.add_argument("--dry-run", "-n", action="store_true", help="Show what would be claimed")
    p.add_argument("--no-twitter", action="store_true", help="Don't perform Twitter actions while claiming")

    # recommended
    p = sub.add_parser("recommended", help="Show recommended quests")
    p.add_argument("--limit", "-l", type=int, default=10)

    # sprints
    sub.add_parser("sprints", help="Show active sprints")

    # login
    sub.add_parser("login", help="Re-login via OTP")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    client = ZealyClient()

    commands = {
        "me": cmd_me,
        "communities": cmd_communities,
        "community": cmd_community,
        "quests": cmd_quests,
        "quest": cmd_quest,
        "claim": cmd_claim,
        "clear": cmd_clear,
        "recommended": cmd_recommended,
        "sprints": cmd_sprints,
        "login": cmd_login,
    }

    fn = commands.get(args.command)
    if fn:
        fn(client, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
