"""
Discord Client — autonomous Discord integration via discord.py-self (v2.1.0).

Modules:
    auth.py             — Token management, client creation, account info
    messages.py         — Send, edit, delete, reply, react, history, pin, search, purge
    advanced_messages.py — Forward, publish, ack/unack, polls, attachments, bulk ops
    servers.py          — Guilds, channels, members, roles, invites, ban/kick/timeout
    users.py            — Profiles, friends, block/unblock, notes, mutuals
    dm.py               — DM 1:1, group DM, message requests
    voice.py            — Voice connect, play/pause/resume/stop audio, disconnect
    threads.py          — Thread create/join/leave, forum posts, tags
    events.py           — Scheduled events CRUD, RSVP, subscribers
    webhooks.py         — Webhook create/send/edit/delete
    emojis.py           — Emoji/sticker CRUD, sticker packs
    audit.py            — Audit logs, bans
    presence.py         — Status, activity, custom status, streaming
    settings.py         — Guild settings, welcome screen, widget, sessions, user settings
    templates.py        — Server templates CRUD, create guild from template
    automod.py          — AutoMod rules CRUD
    premium.py          — Nitro info, boosts, payments, subscriptions, entitlements
    connections.py      — Linked accounts (Spotify, GitHub, etc)

Auth:
    Token stored at ~/.hermes/credentials/discord-token.json
    Format: {"token": "user_token_here"}

Usage (async):
    from auth import create_client, load_token, get_account_info
    from messages import send_message, get_history, reply_to
    from advanced_messages import forward_message, vote_poll, mark_read
    from servers import list_guilds, get_channels, get_members
    from users import get_user, get_friends, block_user
    from dm import send_dm, create_group_dm, list_dms
    from voice import connect_voice, play_audio, disconnect_voice
    from threads import create_thread_from_message, join_thread
    from events import get_events, create_event, rsvp_event
    from webhooks import create_webhook, send_webhook
    from emojis import get_emojis, create_emoji, get_stickers
    from audit import get_audit_log, get_bans
    from presence import set_status, set_custom_status, set_activity
    from settings import edit_guild, get_sessions, get_connections
    from templates import get_templates, create_template
    from automod import get_automod_rules, create_automod_rule
    from premium import get_premium_type, get_payments, get_subscriptions
    from connections import get_connections as get_linked_connections

Quick test:
    python3 runner.py

Note:
    - Uses discord.py-self (user token, not bot token)
    - discord.py-self v2.1.0 — no Intents needed
    - All methods are async — use with asyncio.run() or in async context
    - Selfbot: violates Discord ToS — use at own risk
    - Token is long-lived (until password change or manual logout)
    - Voice playback requires ffmpeg installed on system

Credential files:
    ~/.hermes/credentials/discord-token.json  — Discord user token
    ~/.hermes/credentials/x-cookies.json      — X/Twitter cookies (twikit)
    ~/.hermes/credentials/google-credentials.txt — Gmail app password
"""
