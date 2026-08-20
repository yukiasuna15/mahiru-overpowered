#!/usr/bin/env python3
"""Telegram userbot login with file-based OTP + password + QR support."""

import os
import sys
import time
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = 27677578
API_HASH = "a04f56ffb88b75b00d7d6f5cf44d5da8"
PHONE = "+628****5503"
SESSION_PATH = os.path.expanduser("~/.hermes/credentials/telegram-userbot.session")
OTP_FILE = "/tmp/tg_otp.txt"
PASS_FILE = "/tmp/tg_password.txt"
QR_FILE = "/tmp/tg_qr_token.txt"

def otp_callback():
    with open("/tmp/tg_waiting_for_otp", "w") as f:
        f.write("1")
    print("WAITING_FOR_OTP", flush=True)
    
    for _ in range(180):
        if os.path.exists(OTP_FILE):
            with open(OTP_FILE) as f:
                code = f.read().strip()
            if code:
                os.remove(OTP_FILE)
                if os.path.exists("/tmp/tg_waiting_for_otp"):
                    os.remove("/tmp/tg_waiting_for_otp")
                print(f"Got code: {code}", flush=True)
                return code
        time.sleep(1)
    raise TimeoutError("OTP timeout")

def password_callback():
    with open("/tmp/tg_waiting_for_pass", "w") as f:
        f.write("1")
    print("WAITING_FOR_PASSWORD", flush=True)
    
    for _ in range(180):
        if os.path.exists(PASS_FILE):
            with open(PASS_FILE) as f:
                pw = f.read().strip()
            if pw:
                os.remove(PASS_FILE)
                os.remove("/tmp/tg_waiting_for_pass")
                print("Got password", flush=True)
                return pw
        time.sleep(1)
    raise TimeoutError("Password timeout")


async def qr_login():
    """Login via QR code.
    
    Writes QR token to /tmp/tg_qr_token.txt as a tg://login?token=... URL.
    Polls until QR is scanned or times out.
    """
    for f in [QR_FILE, "/tmp/tg_waiting_for_qr"]:
        if os.path.exists(f):
            os.remove(f)

    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"LOGIN_SUCCESS:{me.id}:{me.first_name}:{me.username}", flush=True)
        await client.disconnect()
        return

    print("WAITING_FOR_QR", flush=True)
    with open("/tmp/tg_waiting_for_qr", "w") as f:
        f.write("1")

    qr_login = await client.qr_login()

    for _ in range(120):  # 2 min timeout
        try:
            # Write QR token URL
            token_hex = qr_login.token.hex()
            url = f"tg://login?token={token_hex}"
            with open(QR_FILE, "w") as f:
                f.write(url)
            print(f"QR_TOKEN:{url}", flush=True)

            # Wait for it to be accepted
            await asyncio.wait_for(qr_login.wait(), timeout=10)
            break
        except asyncio.TimeoutError:
            # Refresh QR
            try:
                qr_login = await client.qr_login()
            except Exception:
                pass
        except Exception as e:
            if "AUTH_TOKEN_EXPIRED" in str(e):
                try:
                    qr_login = await client.qr_login()
                except Exception:
                    pass
            else:
                raise

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"LOGIN_SUCCESS:{me.id}:{me.first_name}:{me.username}", flush=True)
    else:
        print("QR_LOGIN_FAILED", flush=True)

    if os.path.exists(QR_FILE):
        os.remove(QR_FILE)
    if os.path.exists("/tmp/tg_waiting_for_qr"):
        os.remove("/tmp/tg_waiting_for_qr")
    await client.disconnect()


async def phone_login():
    """Login via phone number + OTP."""
    for f in [OTP_FILE, PASS_FILE, "/tmp/tg_waiting_for_otp", "/tmp/tg_waiting_for_pass"]:
        if os.path.exists(f):
            os.remove(f)
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    print("Starting login...", flush=True)
    await client.start(phone=PHONE, code_callback=otp_callback, password=password_callback)
    
    me = await client.get_me()
    print(f"LOGIN_SUCCESS:{me.id}:{me.first_name}:{me.username}", flush=True)
    await client.disconnect()


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "phone"
    if mode == "qr":
        await qr_login()
    else:
        await phone_login()

asyncio.run(main())
