# Mahiru Overpowered

Mahiru Overpowered is a Python-based multi-platform automation toolkit. It groups platform clients for Discord, Telegram, X, Galxe, Gleam, Zealy, Engage, and Outlook under a shared orchestration layer.

## Project scope

The repository contains independent platform clients together with the `overpower` coordination package. The coordination layer exposes a common hub for client initialization, event publication, message relaying, synchronized social actions, quest workflows, credential status, and platform health reporting.

## Main components

| Component | Purpose |
| --- | --- |
| `overpower/` | Central hub, event bus, relay, quest pipeline, synchronized actions, credential management, and status dashboard. |
| `discord-client/` | Discord client modules for messages, servers, users, moderation, webhooks, presence, and related operations. |
| `telegram-userbot/` | Telegram client modules for account, groups, messages, media, reactions, stories, settings, and other Telegram operations. |
| `x-client/` | X client modules for authentication, tweets, direct messages, lists, media, search, timelines, and users. |
| `galxe-client/` | Synchronous Galxe API/CLI client covering authentication, campaign discovery, quest completion, and reward claim workflows. |
| `gleam-client/` | Headless Gleam campaign client covering OAuth, campaign inspection, and entry-method completion. |
| `zealy-client/` | Zealy client and CLI for quest discovery and task workflows. |
| `engage-client/` | Engage client and CLI modules. |
| `outlook-creator/` | Outlook account-creation utilities with example configuration files. |
| `SOUL.md` | Project-specific operating and communication notes included in the original archive. |

## Architecture

The main entry point is `overpower.hub.OverpowerHub`. It can initialize selected platform adapters, connect them to shared services, relay messages, run quest pipelines, synchronize posts or presence, and report unified status.

```python
from overpower.hub import OverpowerHub

hub = OverpowerHub()
await hub.initialize(platforms=["telegram", "discord", "x"])
status = await hub.get_unified_status()
await hub.shutdown()
```

The individual client directories can also be used independently through their corresponding Python modules or CLI scripts.

## Configuration and credentials

This source snapshot expects credentials to be supplied externally at runtime. Do not commit `.env` files, private keys, session files, browser cookies, access tokens, passwords, or account exports. The repository only includes example configuration files where present.

Typical runtime dependencies referenced by the source include Python 3.11+, `requests`, `python-dotenv`, `twikit`, `telethon`, `discord.py`, `web3`, `eth-account`, `curl-cffi`, and Playwright. Exact dependency lockfiles are not included in this archive, so each deployment should define and pin its own environment.

## Current verification status

The archive contains 97 source and documentation files and is approximately 908 KB uncompressed. A Python bytecode compilation check currently reports a syntax error in `overpower/status_dashboard.py` at line 272. The source has been uploaded as provided; this issue should be corrected before relying on the orchestration layer in production.

## Security note

These clients can operate authenticated accounts and may interact with external platforms or on-chain services. Use isolated credentials, least-privilege accounts, explicit rate limits, and platform-compliant workflows. Treat all session material and account credentials as sensitive secrets.
