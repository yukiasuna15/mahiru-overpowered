#!/usr/bin/env python3
"""Galxe CLI tool for interacting with Galxe quests and campaigns."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from galxe import (
    galxe_id_exist, user_info, list_campaigns, get_campaign,
    browse_space_campaigns, recommend_campaigns,
    get_space, follow_space, space_is_admin,
    recent_participation, notifications,
    gg_raffle_info, gg_raffle_history,
    space_earndrops, check_airdrop, star_boards,
    plus_subscription, smart_rank_info, global_banner, whitelist_sites,
    savings_balance, savings_profit,
    quest_cred_list, sync_credential, quest_claim_section,
    full_quest_status, prepare_participate, participate, participate_point,
    solve_geetest_captcha, execute_onchain_claim,
    login, complete_quest, claim_quest, complete_and_claim,
)


def fmt(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def cmd_info(args):
    info = user_info()
    print(f"Username: {info.get('username', 'N/A')}")
    print(f"GalxeID: {info.get('id', 'N/A')}")
    print(f"Address: {info.get('address', 'N/A')}")
    print(f"Level: {info.get('userLevel', {}).get('level', {}).get('name', 'N/A')}")
    print(f"XP Level: {info.get('userXPLevel', {}).get('levelName', 'N/A')}")
    print(f"XP: {info.get('userXPLevel', {}).get('validXP', 0)}")
    print(f"GG: {info.get('userLevel', {}).get('gold', 0)}")
    print(f"Twitter: {info.get('twitterUserName', 'Not linked')}")
    print(f"Discord: {info.get('discordUserName', 'Not linked')}")
    print(f"Email: {info.get('email', 'Not linked')}")
    if args.json:
        fmt(info)


def cmd_explore(args):
    campaigns = list_campaigns(first=args.limit)
    print(f"Total campaigns: {campaigns.get('totalCount', 0)}\n")
    for c in campaigns.get("list", []):
        status_icon = "Active" if c.get("status") == "Active" else c.get("status", "?")
        print(f"  [{status_icon}] {c.get('name', 'N/A')}")
        print(f"    ID: {c.get('id', 'N/A')} | Type: {c.get('type', 'N/A')} | Chain: {c.get('chain', 'N/A')}")
        if c.get('participants'):
            print(f"    Participants: {c['participants'].get('participantsCount', 0)}")
        print()
    if args.json:
        fmt(campaigns)


def cmd_campaign(args):
    campaign = get_campaign(args.id)
    if not campaign:
        print("Campaign not found")
        return
    print(f"Name: {campaign.get('name', 'N/A')}")
    print(f"ID: {campaign.get('id', 'N/A')}")
    print(f"Type: {campaign.get('type', 'N/A')}")
    print(f"Status: {campaign.get('status', 'N/A')}")
    print(f"Chain: {campaign.get('chain', 'N/A')}")
    print(f"Gas: {campaign.get('gasType', 'N/A')}")
    print(f"Cap: {campaign.get('cap', 'N/A')}")
    print(f"Start: {campaign.get('startTime', 'N/A')}")
    print(f"End: {campaign.get('endTime', 'N/A')}")
    space = campaign.get("space", {})
    print(f"Space: {space.get('name', 'N/A')} ({space.get('alias', 'N/A')})")
    reward_info = campaign.get("rewardInfo", {})
    if reward_info.get("premint"):
        premint = reward_info["premint"]
        print(f"Premint Price: {premint.get('price', 'N/A')} on {premint.get('chain', 'N/A')}")
    if campaign.get("quests"):
        print(f"\nQuests ({len(campaign['quests'])}):")
        for q in campaign["quests"]:
            print(f"  - [{q.get('type', '?')}] {q.get('name', 'N/A')} (reward: {q.get('rewardType', '?')})")
    if args.json:
        fmt(campaign)


def cmd_space(args):
    space = get_space(alias=args.alias, space_id=args.id)
    if not space:
        print("Space not found")
        return
    print(f"Name: {space.get('name', 'N/A')}")
    print(f"Alias: {space.get('alias', 'N/A')}")
    print(f"ID: {space.get('id', 'N/A')}")
    print(f"Verified: {space.get('isVerified', False)}")
    print(f"Followers: {space.get('followersCount', 0)}")
    print(f"Categories: {', '.join(space.get('categories', []))}")
    if args.json:
        fmt(space)


def cmd_space_campaigns(args):
    result = browse_space_campaigns(alias=args.alias, space_id=args.id, first=args.limit)
    if not result:
        print("Space not found")
        return
    print(f"Space: {result.get('name', 'N/A')} ({result.get('alias', 'N/A')})")
    campaigns = result.get("campaigns", {})
    print(f"Campaigns: {campaigns.get('pageInfo', {}).get('endCursor', '?')}\n")
    for c in campaigns.get("list", []):
        boost = c.get("boost", {})
        wl = c.get("whitelistInfo", {})
        print(f"  [{c.get('status', '?')}] {c.get('name', 'N/A')}")
        print(f"    ID: {c.get('id')} | Type: {c.get('type')} | Chain: {c.get('chain')}")
        if boost:
            print(f"    Boost: {boost.get('golden', 0)}")
        if wl and wl.get("usedCount", 0) > 0:
            print(f"    Whitelist: {wl['usedCount']} uses")
        print()
    if args.json:
        fmt(result)


def cmd_follow(args):
    ids = [int(x) for x in args.space_ids.split(",")]
    result = follow_space(ids)
    print(f"Followed {result} space(s)")


def cmd_participations(args):
    parts = recent_participation(first=args.limit)
    if not parts:
        print("No recent participations")
        return
    for p in parts:
        campaign = p.get("campaign", {})
        space = campaign.get("space", {})
        print(f"  [{p.get('status', '?')}] {campaign.get('name', 'N/A')}")
        print(f"    Space: {space.get('alias', '?')} | Chain: {p.get('chain', '?')}")
        print(f"    TX: {p.get('tx', 'N/A')} | Created: {p.get('createdAt', 'N/A')}")
        print()
    if args.json:
        fmt(parts)


def cmd_raffle(args):
    info = gg_raffle_info()
    if info:
        print(f"GG Raffle Round {info.get('roundId', '?')}")
        print(f"  Active: {info.get('isActive', False)}")
        print(f"  Chain: {info.get('chain', '?')}")
        print(f"  Token: {info.get('tokenType', '?')}")
        print(f"  Rate: {info.get('rate', '?')}")
        print(f"  Participants: {info.get('participateCount', 0)}")
        print(f"  Grand: {info.get('grandCount', 0)} | Small: {info.get('smallCount', 0)}")
    if args.json:
        fmt(info)


def cmd_notifications(args):
    notifs = notifications(limit=args.limit)
    total = notifs.get("total", 0)
    items = notifs.get("notifications", [])
    print(f"Notifications: {total}\n")
    for n in items:
        print(f"  [{n.get('category', '?')}] {n.get('title', 'N/A')}")
        if n.get("description"):
            print(f"    {n['description'][:100]}")
        print()
    if args.json:
        fmt(notifs)


def cmd_airdrops(args):
    earndrops = space_earndrops(args.space_id)
    airdrops = check_airdrop(args.space_id)
    print(f"Earndrops: {len(earndrops)}")
    for e in earndrops:
        print(f"  - {e.get('name', 'N/A')} ({e.get('alias', 'N/A')})")
    print(f"\nAirdrops: {len(airdrops or [])}")
    for a in airdrops or []:
        print(f"  - {a.get('name', 'N/A')} [{a.get('status', '?')}]")
    if args.json:
        fmt({"earndrops": earndrops, "airdrops": airdrops})


def cmd_savings(args):
    bal = savings_balance()
    print("Savings Balance:")
    for b in (bal if isinstance(bal, list) else [bal]):
        if isinstance(b, dict):
            token_info = b.get("token", {})
            print(f"  {token_info.get('symbol', '?')}: available={b.get('availableAmount', 0)}, pending={b.get('pendingAmount', 0)}")
    if args.json:
        fmt(bal)


def cmd_quest_status(args):
    status = full_quest_status(args.id)
    print(f"Campaign: {status.get('name', 'N/A')} ({status.get('campaign_id', 'N/A')})")
    print(f"Type: {status.get('type', 'N/A')} | Chain: {status.get('chain', 'N/A')} | Status: {status.get('status', 'N/A')}")
    space = status.get("space", {})
    print(f"Space: {space.get('name', '?')} ({space.get('alias', '?')})")
    print(f"Loyalty Points: {status.get('loyalty_points', 0)}")
    print(f"Already Claimed: {'YES' if status.get('already_claimed') else 'NO'}")
    if status.get("user_participation"):
        print(f"  Participation: {status['user_participation'].get('status', '?')}")

    pc = status.get("participate_condition")
    if pc:
        print(f"\nParticipate Condition: {'ELIGIBLE' if pc['eligible'] else 'NOT ELIGIBLE'} (formula: {pc['formula']})")
        for c in pc.get("conditions", []):
            icon = "OK" if c["eligible"] else "NO"
            print(f"  [{icon}] {c['name']} (id={c['id']}, source={c['source']})")

    for rc in status.get("reward_configs", []):
        print(f"\nReward Config [{rc['id']}]: {'ELIGIBLE' if rc['eligible'] else 'NOT ELIGIBLE'}")
        if rc.get("description"):
            print(f"  Description: {rc['description']}")
        for c in rc.get("conditions", []):
            icon = "OK" if c["eligible"] else "NO"
            ref = c.get("reference_link", "")
            print(f"  [{icon}] {c['name']} (id={c['id']}, source={c['source']})")
            if ref:
                print(f"       link: {ref}")

    if args.json:
        fmt(status)


def cmd_quest_creds(args):
    data = quest_cred_list(args.id)
    tc = data.get("taskConfig", {})
    pc = tc.get("participateCondition")
    if pc:
        print(f"Participate: {'eligible' if pc['eligible'] else 'NOT eligible'} ({pc['conditionalFormula']})")
        for c in pc.get("conditions", []):
            cred = c.get("cred", {})
            print(f"  [{'OK' if cred.get('eligible') else 'NO'}] {cred.get('name')} | id={cred.get('id')} | source={cred.get('credSource')} | synced={cred.get('lastSync')}")
    for rc in tc.get("rewardConfigs", []):
        print(f"\nReward [{rc['id']}]: {'eligible' if rc['eligible'] else 'NOT eligible'}")
        for c in rc.get("conditions", []):
            cred = c.get("cred", {})
            print(f"  [{'OK' if cred.get('eligible') else 'NO'}] {cred.get('name')} | id={cred.get('id')} | source={cred.get('credSource')} | synced={cred.get('lastSync')}")
    if args.json:
        fmt(data)


def cmd_login(args):
    """SIWE sign-in with the wallet key (~/wallet/.env); saves the JWT."""
    login()


def cmd_complete(args):
    """Complete all auto-completable tasks of a quest."""
    complete_quest(args.id)


def cmd_complete_and_claim(args):
    """Complete tasks, then claim on-chain."""
    complete_and_claim(args.id)


def cmd_claim(args):
    """Claim a quest on-chain (solves WASM captcha; pays the ~14.88 G claim fee)."""
    status = full_quest_status(args.id)
    print(f"Campaign: {status.get('name', 'N/A')} ({status.get('campaign_id', 'N/A')})")
    pc = status.get("participate_condition")
    if pc and not pc.get("eligible") and not args.force:
        print("Not eligible for participation. Missing:")
        for c in pc.get("conditions", []):
            if not c.get("eligible"):
                print(f"  - {c.get('name', '?')} (source={c.get('source', '?')})")
        print("Run `complete` first, or use --force to attempt anyway.")
        return
    try:
        if not claim_quest(args.id):
            print("Nothing claimed.")
    except Exception as e:
        print(f"Claim failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Galxe CLI")
    sub = parser.add_subparsers(dest="command")

    p_info = sub.add_parser("info", help="Show user info")
    p_info.add_argument("--json", action="store_true")
    p_info.set_defaults(func=cmd_info)

    p_explore = sub.add_parser("explore", help="List active campaigns")
    p_explore.add_argument("--limit", type=int, default=20)
    p_explore.add_argument("--json", action="store_true")
    p_explore.set_defaults(func=cmd_explore)

    p_campaign = sub.add_parser("campaign", help="Campaign details")
    p_campaign.add_argument("id", help="Campaign ID")
    p_campaign.add_argument("--json", action="store_true")
    p_campaign.set_defaults(func=cmd_campaign)

    p_space = sub.add_parser("space", help="Space info")
    p_space.add_argument("--alias", help="Space alias")
    p_space.add_argument("--id", type=int, help="Space ID")
    p_space.add_argument("--json", action="store_true")
    p_space.set_defaults(func=cmd_space)

    p_sc = sub.add_parser("space-campaigns", help="List space campaigns")
    p_sc.add_argument("--alias", help="Space alias")
    p_sc.add_argument("--id", type=int, help="Space ID")
    p_sc.add_argument("--limit", type=int, default=20)
    p_sc.add_argument("--json", action="store_true")
    p_sc.set_defaults(func=cmd_space_campaigns)

    p_follow = sub.add_parser("follow", help="Follow space(s)")
    p_follow.add_argument("space_ids", help="Comma-separated space IDs")
    p_follow.set_defaults(func=cmd_follow)

    p_parts = sub.add_parser("participations", help="Recent participations")
    p_parts.add_argument("--limit", type=int, default=30)
    p_parts.add_argument("--json", action="store_true")
    p_parts.set_defaults(func=cmd_participations)

    p_raffle = sub.add_parser("raffle", help="GG raffle info")
    p_raffle.add_argument("--json", action="store_true")
    p_raffle.set_defaults(func=cmd_raffle)

    p_notif = sub.add_parser("notifications", help="Recent notifications")
    p_notif.add_argument("--limit", type=int, default=30)
    p_notif.add_argument("--json", action="store_true")
    p_notif.set_defaults(func=cmd_notifications)

    p_air = sub.add_parser("airdrops", help="Check space airdrops")
    p_air.add_argument("space_id", type=int)
    p_air.add_argument("--json", action="store_true")
    p_air.set_defaults(func=cmd_airdrops)

    p_sav = sub.add_parser("savings", help="Savings/DeFi balance")
    p_sav.add_argument("--json", action="store_true")
    p_sav.set_defaults(func=cmd_savings)

    p_qs = sub.add_parser("quest-status", help="Full quest status (creds + claim)")
    p_qs.add_argument("id", help="Campaign ID")
    p_qs.add_argument("--json", action="store_true")
    p_qs.set_defaults(func=cmd_quest_status)

    p_qc = sub.add_parser("quest-creds", help="Raw credential list for campaign")
    p_qc.add_argument("id", help="Campaign ID")
    p_qc.add_argument("--json", action="store_true")
    p_qc.set_defaults(func=cmd_quest_creds)

    p_login = sub.add_parser("login", help="SIWE sign-in with wallet key; saves JWT")
    p_login.set_defaults(func=cmd_login)

    p_complete = sub.add_parser("complete", help="Complete a quest's auto-completable tasks")
    p_complete.add_argument("id", help="Campaign ID")
    p_complete.set_defaults(func=cmd_complete)

    p_cac = sub.add_parser("complete-and-claim", help="Complete tasks then claim on-chain")
    p_cac.add_argument("id", help="Campaign ID")
    p_cac.set_defaults(func=cmd_complete_and_claim)

    p_claim = sub.add_parser("claim", help="Claim a quest on-chain (solves WASM captcha; pays claim fee)")
    p_claim.add_argument("id", help="Campaign ID")
    p_claim.add_argument("--force", action="store_true", help="Claim even if not eligible")
    p_claim.set_defaults(func=cmd_claim)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
