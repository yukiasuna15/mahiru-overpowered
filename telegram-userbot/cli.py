#!/usr/bin/env python3
"""Telegram userbot CLI — unified entry point for all operations."""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from auth import get_client
from messages import send_message, get_messages, reply_to_message, delete_message, forward_message
from groups import get_dialogs, join_group, get_group_members, leave_group, get_group_info
from media import send_file, send_photo, download_media, send_voice
from users import get_me, get_user, block_user, unblock_user
from reactions import add_reaction, remove_reaction, get_reactions, set_default_reaction
from edit import edit_message, edit_media
from chat_actions import set_typing, send_chat_action
from search import search_messages, search_global
from pinned import pin_message, unpin_message, get_pinned
from scheduled import send_scheduled, get_scheduled, edit_scheduled, delete_scheduled
from drafts import save_draft, get_draft, delete_draft
from profile import update_name, update_bio, update_avatar, update_username, get_profile
from read import mark_read, mark_unread, set_folder
from polls import send_poll, vote_poll, get_poll_results
from stories import post_story, view_story, delete_story, get_stories
from folders import create_folder, edit_folder, delete_folder, get_folders
from notifications import mute_chat, unmute_chat, get_notification_settings
from privacy import get_privacy, set_privacy, get_blocked
from account import update_password, get_password, delete_account, get_authorizations, reset_authorizations
from inline import send_inline, answer_inline
from callback import answer_callback, send_callback
from contacts import add_contact, delete_contact, get_contacts, import_contacts
from stickers import send_sticker, get_stickers, create_sticker_set
from gifs import search_gif, send_gif
from forum import create_topic, edit_topic, delete_topic, get_topics
from boost import boost_channel, get_boosts
from giveaways import create_giveaway, get_giveaway
from payments import get_payments
from stats import get_channel_stats, get_message_stats
from emoji_status import set_emoji_status, get_emoji_status
from saved import send_saved, get_saved
from translate import translate_message
from wallpaper import get_wallpapers, set_wallpaper
from peer_settings import get_peer_settings, report_peer


COMMANDS = {
    # Core messaging
    "me": "Get current user info",
    "send": "Send message: send <entity> <text>",
    "messages": "Get messages: messages <entity> [limit]",
    "reply": "Reply to message: reply <entity> <msg_id> <text>",
    "delete": "Delete message: delete <entity> <msg_id>",
    "forward": "Forward message: forward <from> <to> <msg_id>",
    # Dialogs/groups
    "dialogs": "List dialogs [limit]",
    "join": "Join group: join <invite_link>",
    "members": "Get group members: members <entity> [limit]",
    "info": "Get group info: info <entity>",
    "leave": "Leave group: leave <entity>",
    # Media
    "sendfile": "Send file: sendfile <entity> <path> [caption]",
    "sendphoto": "Send photo: sendphoto <entity> <path> [caption]",
    "download": "Download media: download <entity> <msg_id> [save_path]",
    "sendvoice": "Send voice: sendvoice <entity> <path>",
    # Users
    "user": "Get user info: user <username_or_id>",
    "block": "Block user: block <user>",
    "unblock": "Unblock user: unblock <user>",
    # Reactions
    "react": "Add reaction: react <entity> <msg_id> [emoji]",
    "unreact": "Remove reaction: unreact <entity> <msg_id> [emoji]",
    "reactions": "Get reactions: reactions <entity> <msg_id>",
    "setreaction": "Set default reaction: setreaction <entity> <emoji>",
    # Edit
    "editmsg": "Edit message: editmsg <entity> <msg_id> <text>",
    "editmedia": "Edit media: editmedia <entity> <msg_id> <path> [caption]",
    # Typing
    "typing": "Set typing action: typing <entity> [action]",
    # Search
    "search": "Search messages: search <entity> <query> [limit]",
    "searchglobal": "Search globally: searchglobal <query> [limit]",
    # Pinned
    "pin": "Pin message: pin <entity> <msg_id> [notify]",
    "unpin": "Unpin message: unpin <entity> <msg_id>",
    "getpinned": "Get pinned messages: getpinned <entity>",
    # Scheduled
    "schedule": "Schedule message: schedule <entity> <timestamp> <text>",
    "getscheduled": "Get scheduled: getscheduled <entity>",
    "delscheduled": "Delete scheduled: delscheduled <entity> <msg_id>",
    # Drafts
    "savedraft": "Save draft: savedraft <entity> <text>",
    "getdraft": "Get draft: getdraft <entity>",
    "deldraft": "Delete draft: deldraft <entity>",
    # Profile
    "updatename": "Update name: updatename <first> [last]",
    "updatebio": "Update bio: updatebio <text>",
    "updateavatar": "Update avatar: updateavatar <path>",
    "updateusername": "Update username: updateusername <username>",
    "profile": "Get full profile info",
    # Read
    "markread": "Mark read: markread <entity> [msg_id]",
    "markunread": "Mark unread: markunread <entity>",
    # Polls
    "poll": "Send poll: poll <entity> <question> <opt1> <opt2> [opt3...]",
    "vote": "Vote in poll: vote <entity> <msg_id> <opt_idx...>",
    "pollresults": "Get poll results: pollresults <entity> <msg_id>",
    # Stories
    "poststory": "Post story: poststory <media_path> [caption]",
    "viewstory": "View story: viewstory <user> <story_id>",
    "delstory": "Delete story: delstory <story_id>",
    "getstories": "Get stories: getstories [user]",
    # Folders
    "createfolder": "Create folder: createfolder <title>",
    "delfolder": "Delete folder: delfolder <folder_id>",
    "getfolders": "Get all folders",
    # Notifications
    "mute": "Mute chat: mute <entity>",
    "unmute": "Unmute chat: unmute <entity>",
    "notifysettings": "Get notification settings: notifysettings [entity]",
    # Privacy
    "privacy": "Get privacy: privacy [key]",
    "blocked": "Get blocked users",
    # Account
    "sessions": "Get active sessions",
    "resetsessions": "Reset all other sessions",
    "passwordinfo": "Get 2FA password info",
    # Inline
    "inline": "Send inline query: inline <bot> <query> [entity]",
    # Callback
    "callback": "Answer callback: callback <query_id> [text]",
    "clickbutton": "Click inline button: clickbutton <entity> <msg_id> [data]",
    # Contacts
    "addcontact": "Add contact: addcontact <user> [first] [last]",
    "delcontact": "Delete contact: delcontact <user>",
    "getcontacts": "Get all contacts",
    # Stickers
    "sendsticker": "Send sticker: sendsticker <entity> <path>",
    "stickers": "Search stickers: stickers <emoji>",
    # GIFs
    "searchgif": "Search GIFs: searchgif <query>",
    "sendgif": "Send GIF: sendgif <entity> <query>",
    # Forum
    "createtopic": "Create forum topic: createtopic <entity> <title>",
    "edittopic": "Edit topic: edittopic <entity> <topic_id> <title>",
    "deltopic": "Delete topic: deltopic <entity> <topic_id>",
    "gettopics": "Get forum topics: gettopics <entity>",
    # Boost
    "boost": "Boost channel: boost <entity>",
    "getboosts": "Get boost info: getboosts <entity>",
    # Giveaways
    "giveaway": "Create giveaway: giveaway <entity> <quantity> [months]",
    # Stats
    "channelstats": "Get channel stats: channelstats <entity>",
    "msgstats": "Get message stats: msgstats <entity> <msg_ids...>",
    # Emoji Status
    "emojistatus": "Set emoji status: emojistatus <emoji_doc_id>",
    "getemojistatus": "Get emoji status: getemojistatus [user]",
    # Saved
    "saved": "Get saved messages [limit]",
    "savesend": "Send to saved: savesend <text>",
    # Translate
    "translate": "Translate message: translate <entity> <msg_id> [lang]",
    # Wallpaper
    "wallpapers": "Get available wallpapers",
    "setwallpaper": "Set wallpaper: setwallpaper <entity> <path_or_id>",
    # Peer settings
    "peersettings": "Get peer settings: peersettings <entity>",
    "reportpeer": "Report peer: reportpeer <entity> [reason] [message]",
}


async def run_command(cmd: str, args: list[str]) -> dict | list | str:
    client = await get_client()
    try:
        match cmd:
            # === Core messaging ===
            case "me":
                return await get_me(client)
            case "send":
                if len(args) < 2:
                    return {"error": "Usage: send <entity> <text>"}
                return await send_message(client, args[0], " ".join(args[1:]))
            case "messages":
                if not args:
                    return {"error": "Usage: messages <entity> [limit]"}
                limit = int(args[1]) if len(args) > 1 else 20
                return await get_messages(client, args[0], limit)
            case "reply":
                if len(args) < 3:
                    return {"error": "Usage: reply <entity> <msg_id> <text>"}
                return await reply_to_message(client, args[0], int(args[1]), " ".join(args[2:]))
            case "delete":
                if len(args) < 2:
                    return {"error": "Usage: delete <entity> <msg_id>"}
                await delete_message(client, args[0], int(args[1]))
                return {"deleted": True}
            case "forward":
                if len(args) < 3:
                    return {"error": "Usage: forward <from> <to> <msg_id>"}
                return await forward_message(client, args[0], args[1], int(args[2]))
            # === Dialogs/groups ===
            case "dialogs":
                limit = int(args[0]) if args else 50
                return await get_dialogs(client, limit)
            case "join":
                return await join_group(client, args[0])
            case "members":
                limit = int(args[1]) if len(args) > 1 else 100
                return await get_group_members(client, args[0], limit)
            case "info":
                return await get_group_info(client, args[0])
            case "leave":
                await leave_group(client, args[0])
                return {"left": True}
            # === Media ===
            case "sendfile":
                caption = " ".join(args[2:]) if len(args) > 2 else ""
                return await send_file(client, args[0], args[1], caption)
            case "sendphoto":
                caption = " ".join(args[2:]) if len(args) > 2 else ""
                return await send_photo(client, args[0], args[1], caption)
            case "download":
                save_path = args[2] if len(args) > 2 else "/tmp/"
                path = await download_media(client, args[0], int(args[1]), save_path)
                return {"path": path}
            case "sendvoice":
                return await send_voice(client, args[0], args[1])
            # === Users ===
            case "user":
                return await get_user(client, args[0])
            case "block":
                await block_user(client, args[0])
                return {"blocked": True}
            case "unblock":
                await unblock_user(client, args[0])
                return {"unblocked": True}
            # === Reactions ===
            case "react":
                emoji = args[2] if len(args) > 2 else "👍"
                return await add_reaction(client, args[0], int(args[1]), emoji)
            case "unreact":
                emoji = args[2] if len(args) > 2 else "👍"
                return await remove_reaction(client, args[0], int(args[1]), emoji)
            case "reactions":
                return await get_reactions(client, args[0], int(args[1]))
            case "setreaction":
                return await set_default_reaction(client, args[0], args[1])
            # === Edit ===
            case "editmsg":
                return await edit_message(client, args[0], int(args[1]), " ".join(args[2:]))
            case "editmedia":
                caption = " ".join(args[3:]) if len(args) > 3 else ""
                return await edit_media(client, args[0], int(args[1]), args[2], caption)
            # === Typing ===
            case "typing":
                action = args[1] if len(args) > 1 else "typing"
                return await set_typing(client, args[0], action)
            # === Search ===
            case "search":
                limit = int(args[-1]) if len(args) > 2 and args[-1].isdigit() else 20
                query = " ".join(args[1:-1]) if len(args) > 2 and args[-1].isdigit() else " ".join(args[1:])
                return await search_messages(client, args[0], query, limit)
            case "searchglobal":
                limit = int(args[-1]) if len(args) > 1 and args[-1].isdigit() else 20
                query = " ".join(args[:-1]) if len(args) > 1 and args[-1].isdigit() else " ".join(args)
                return await search_global(client, query, limit)
            # === Pinned ===
            case "pin":
                notify = len(args) > 2 and args[2].lower() in ("true", "1", "yes")
                return await pin_message(client, args[0], int(args[1]), notify)
            case "unpin":
                return await unpin_message(client, args[0], int(args[1]))
            case "getpinned":
                return await get_pinned(client, args[0])
            # === Scheduled ===
            case "schedule":
                ts = datetime.fromtimestamp(int(args[1]))
                return await send_scheduled(client, args[0], " ".join(args[2:]), ts)
            case "getscheduled":
                return await get_scheduled(client, args[0])
            case "delscheduled":
                return await delete_scheduled(client, args[0], [int(args[1])])
            # === Drafts ===
            case "savedraft":
                return await save_draft(client, args[0], " ".join(args[1:]))
            case "getdraft":
                return await get_draft(client, args[0])
            case "deldraft":
                return await delete_draft(client, args[0])
            # === Profile ===
            case "updatename":
                last = args[1] if len(args) > 1 else None
                return await update_name(client, args[0], last)
            case "updatebio":
                return await update_bio(client, " ".join(args))
            case "updateavatar":
                return await update_avatar(client, args[0])
            case "updateusername":
                return await update_username(client, args[0])
            case "profile":
                return await get_profile(client)
            # === Read ===
            case "markread":
                msg_id = int(args[1]) if len(args) > 1 else None
                return await mark_read(client, args[0], msg_id)
            case "markunread":
                return await mark_unread(client, args[0])
            # === Polls ===
            case "poll":
                if len(args) < 4:
                    return {"error": "Usage: poll <entity> <question> <opt1> <opt2> [opt3...]"}
                return await send_poll(client, args[0], args[1], args[2:])
            case "vote":
                return await vote_poll(client, args[0], int(args[1]), [int(x) for x in args[2:]])
            case "pollresults":
                return await get_poll_results(client, args[0], int(args[1]))
            # === Stories ===
            case "poststory":
                caption = " ".join(args[1:]) if len(args) > 1 else ""
                return await post_story(client, args[0], caption)
            case "viewstory":
                return await view_story(client, args[0], int(args[1]))
            case "delstory":
                return await delete_story(client, int(args[0]))
            case "getstories":
                user = args[0] if args else "me"
                return await get_stories(client, user)
            # === Folders ===
            case "createfolder":
                return await create_folder(client, " ".join(args))
            case "delfolder":
                return await delete_folder(client, int(args[0]))
            case "getfolders":
                return await get_folders(client)
            # === Notifications ===
            case "mute":
                return await mute_chat(client, args[0])
            case "unmute":
                return await unmute_chat(client, args[0])
            case "notifysettings":
                entity = args[0] if args else None
                return await get_notification_settings(client, entity)
            # === Privacy ===
            case "privacy":
                key = args[0] if args else "status"
                return await get_privacy(client, key)
            case "blocked":
                return await get_blocked(client)
            # === Account ===
            case "sessions":
                return await get_authorizations(client)
            case "resetsessions":
                return await reset_authorizations(client)
            case "passwordinfo":
                return await get_password(client)
            # === Inline ===
            case "inline":
                entity = args[2] if len(args) > 2 else None
                return await send_inline(client, args[0], " ".join(args[1:]), entity)
            # === Callback ===
            case "callback":
                text = " ".join(args[1:]) if len(args) > 1 else None
                return await answer_callback(client, int(args[0]), text)
            case "clickbutton":
                data = args[2].encode() if len(args) > 2 else b""
                return await send_callback(client, args[0], int(args[1]), data)
            # === Contacts ===
            case "addcontact":
                first = args[1] if len(args) > 1 else ""
                last = args[2] if len(args) > 2 else ""
                return await add_contact(client, args[0], first, last)
            case "delcontact":
                return await delete_contact(client, args[0])
            case "getcontacts":
                return await get_contacts(client)
            # === Stickers ===
            case "sendsticker":
                return await send_sticker(client, args[0], args[1])
            case "stickers":
                return await get_stickers(client, args[0])
            # === GIFs ===
            case "searchgif":
                return await search_gif(client, " ".join(args))
            case "sendgif":
                return await send_gif(client, args[0], " ".join(args[1:]))
            # === Forum ===
            case "createtopic":
                return await create_topic(client, args[0], " ".join(args[1:]))
            case "edittopic":
                return await edit_topic(client, args[0], int(args[1]), " ".join(args[2:]))
            case "deltopic":
                return await delete_topic(client, args[0], int(args[1]))
            case "gettopics":
                return await get_topics(client, args[0])
            # === Boost ===
            case "boost":
                return await boost_channel(client, args[0])
            case "getboosts":
                return await get_boosts(client, args[0])
            # === Giveaways ===
            case "giveaway":
                quantity = int(args[1]) if len(args) > 1 else 1
                months = int(args[2]) if len(args) > 2 else 12
                return await create_giveaway(client, args[0], quantity, months)
            # === Stats ===
            case "channelstats":
                return await get_channel_stats(client, args[0])
            case "msgstats":
                return await get_message_stats(client, args[0], [int(x) for x in args[1:]])
            # === Emoji Status ===
            case "emojistatus":
                return await set_emoji_status(client, int(args[0]))
            case "getemojistatus":
                user = args[0] if args else None
                return await get_emoji_status(client, user)
            # === Saved ===
            case "saved":
                limit = int(args[0]) if args else 20
                return await get_saved(client, limit)
            case "savesend":
                return await send_saved(client, " ".join(args))
            # === Translate ===
            case "translate":
                lang = args[2] if len(args) > 2 else "en"
                return await translate_message(client, args[0], int(args[1]), lang)
            # === Wallpaper ===
            case "wallpapers":
                return await get_wallpapers(client)
            case "setwallpaper":
                if len(args) < 2:
                    return {"error": "Usage: setwallpaper <entity> <path_or_id>"}
                if args[1].isdigit():
                    return await set_wallpaper(client, args[0], wallpaper_id=int(args[1]))
                return await set_wallpaper(client, args[0], wallpaper_path=args[1])
            # === Peer settings ===
            case "peersettings":
                return await get_peer_settings(client, args[0])
            case "reportpeer":
                reason = args[1] if len(args) > 1 else "spam"
                message = " ".join(args[2:]) if len(args) > 2 else ""
                return await report_peer(client, args[0], reason, message)
            case _:
                return {"error": f"Unknown command: {cmd}", "available": list(COMMANDS.keys())}
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Telegram Userbot CLI")
    parser.add_argument("command", nargs="?", help="Command to run")
    parser.add_argument("args", nargs="*", help="Command arguments")
    parser.add_argument("--list", "-l", action="store_true", help="List available commands")
    args = parser.parse_args()

    if args.list or not args.command:
        print("Available commands:")
        for cmd, desc in COMMANDS.items():
            print(f"  {cmd:<16} {desc}")
        return

    result = asyncio.run(run_command(args.command, args.args))
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
