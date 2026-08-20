#!/usr/bin/env python3
"""
Mute Telegram chat(s) forever (until 2038).
Usage:
  python3 mute_chat.py <chat_id_or_username>   # mute single chat
  python3 mute_chat.py --all-new                # mute all unmuted groups/channels
"""
import asyncio
import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / '.hermes' / 'credentials' / 'telegram-userbot.env')

MUTE_UNTIL = int(time.time()) + (86400 * 365 * 10)  # ~10 years from now


async def mute_single(client, chat_id):
    """Mute a single chat by ID or username."""
    from telethon.tl.functions.account import UpdateNotifySettingsRequest
    from telethon.tl.types import InputPeerNotifySettings, InputNotifyPeer

    entity = await client.get_entity(chat_id)
    peer = await client.get_input_entity(entity)
    await client(UpdateNotifySettingsRequest(
        peer=InputNotifyPeer(peer=peer),
        settings=InputPeerNotifySettings(mute_until=MUTE_UNTIL, show_previews=False)
    ))
    name = getattr(entity, 'title', None) or getattr(entity, 'first_name', '') or str(chat_id)
    print(f'[MUTED] {name}')


async def mute_all_new(client):
    """Mute all groups/channels that are not already muted."""
    from telethon.tl.functions.account import UpdateNotifySettingsRequest, GetNotifySettingsRequest
    from telethon.tl.types import InputPeerNotifySettings, InputNotifyPeer
    from datetime import datetime

    muted = 0
    skipped = 0
    async for d in client.iter_dialogs():
        entity = d.entity
        is_channel = hasattr(entity, 'broadcast')
        is_group = d.is_group

        if not (is_channel or is_group):
            continue

        # Check if already muted
        try:
            peer = await client.get_input_entity(entity)
            settings = await client(GetNotifySettingsRequest(
                peer=InputNotifyPeer(peer=peer)
            ))
            mute = settings.mute_until
            if mute and isinstance(mute, datetime) and mute.year > 2030:
                skipped += 1
                continue
        except Exception:
            pass

        try:
            await client(UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(peer=peer),
                settings=InputPeerNotifySettings(mute_until=MUTE_UNTIL, show_previews=False)
            ))
            name = d.name or str(entity.id)
            print(f'[MUTED] {name}')
            muted += 1
        except Exception as e:
            print(f'[ERR] {d.name}: {e}')

    print(f'\nMuted: {muted} | Already muted: {skipped}')


async def main():
    from telethon import TelegramClient

    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')
    if not api_id or not api_hash:
        print('Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment')
        return

    client = TelegramClient(
        str(Path.home() / '.hermes' / 'credentials' / 'telegram-userbot.session'),
        int(api_id),
        api_hash
    )
    await client.start()

    if len(sys.argv) < 2:
        print('Usage: python3 mute_chat.py <chat_id_or_username>')
        print('       python3 mute_chat.py --all-new')
        return

    arg = sys.argv[1]
    if arg == '--all-new':
        await mute_all_new(client)
    else:
        await mute_single(client, arg)

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
