"""
Engage IO Discord Client — auto-engage to X/Twitter posts from The Engage bot.

Flow:
  1. Monitor channel for new messages from The Engage bot
  2. Extract tweet URL from message embed/content
  3. Like + Retweet the tweet via twikit
  4. Click the "proceed" button via Discord interaction API
  5. Report result

Dependencies:
  - twikit (X/Twitter)
  - discord.py-self (Discord userbot)
  - requests (HTTP)
"""

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("engage")

# ---------------------------------------------------------------------------
# Config & Constants
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR / ".env"


def _load_env() -> dict:
    """Load key=value pairs from .env file (no quotes, no export)."""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


_env = _load_env()

ENGAGE_BOT_ID = "1077740178476630129"  # The Engage bot — constant, not configurable
ENGAGE_POLL_INTERVAL = int(_env.get("ENGAGE_POLL_INTERVAL", "300"))
STATE_PATH = Path(_env.get("ENGAGE_STATE_FILE", str(SCRIPT_DIR / "state.json")))

DISCORD_TOKEN_PATH = Path.home() / ".hermes" / "credentials" / "discord-token.json"
X_COOKIES_PATH = Path.home() / ".hermes" / "credentials" / "x-cookies.json"

TWEET_URL_RE = re.compile(r"https?://(?:x|twitter)\.com/\w+/status/(\d+)")
ENGAGES_IO_RE = re.compile(r"https?://www\.engages\.io/tweets/(\w+)")
PROCEED_RE = re.compile(r"proceed-(\d+)-(\d+)")
COMMENT_RE = re.compile(r"comment-(\d+)-(\w+)")

# Emoji ID → task mapping (detected from Engage bot button structure)
EMOJI_TASK_MAP = {
    "1248398311350603806": "like",      # chatcirclefill25
    "1248398306166440026": "retweet",   # chatcirclefill27
    "1248397181962948739": "reply",     # chatcircleddddfill26
    "1248398314169434144": "quote",     # chatcirclefill28
}

DISCORD_API = "https://discord.com/api/v9"

# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------


class StateManager:
    """Manages multi-server engagement state in JSON."""

    def __init__(self, path: Path = STATE_PATH):
        self._path = path
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return {"engagements": {}, "active": None}

    def save(self):
        self._path.write_text(json.dumps(self._data, indent=2) + "\n")

    @property
    def active_key(self) -> Optional[str]:
        return self._data.get("active")

    @property
    def active_engagement(self) -> Optional[dict]:
        key = self.active_key
        if key and key in self._data["engagements"]:
            return self._data["engagements"][key]
        return None

    def list_engagements(self) -> dict:
        return self._data.get("engagements", {})

    def add_engagement(self, guild_id: str, channel_id: str,
                       bot_id: str = ENGAGE_BOT_ID, bot_name: str = "Unknown"):
        """Add a new engagement target. Returns the key."""
        key = f"{guild_id}:{channel_id}"
        if key not in self._data["engagements"]:
            self._data["engagements"][key] = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "bot_id": bot_id,
                "bot_name": bot_name,
                "engaged_messages": [],
                "total_engaged": 0,
                "last_checked": None,
            }
        # Auto-switch to new engagement if nothing is active
        if not self._data.get("active"):
            self._data["active"] = key
        self.save()
        return key

    def switch_active(self, key: str) -> bool:
        """Switch active engagement. Returns True if key exists."""
        if key in self._data["engagements"]:
            self._data["active"] = key
            self.save()
            return True
        return False

    def remove_engagement(self, key: str) -> bool:
        """Remove an engagement. Returns True if existed."""
        if key in self._data["engagements"]:
            del self._data["engagements"][key]
            if self._data.get("active") == key:
                remaining = list(self._data["engagements"].keys())
                self._data["active"] = remaining[0] if remaining else None
            self.save()
            return True
        return False

    def is_engaged(self, message_id: str) -> bool:
        """Check if a message has already been engaged."""
        eng = self.active_engagement
        if not eng:
            return False
        return message_id in eng.get("engaged_messages", [])

    def mark_engaged(self, message_id: str):
        """Mark a message as engaged."""
        eng = self.active_engagement
        if not eng:
            return
        if message_id not in eng["engaged_messages"]:
            eng["engaged_messages"].append(message_id)
            eng["total_engaged"] = len(eng["engaged_messages"])
        eng["last_checked"] = datetime.now(timezone.utc).isoformat()
        self.save()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EngageTask:
    """Represents a single engage task from The Engage bot."""

    message_id: str
    tweet_id: str
    tweet_url: str
    proceed_custom_id: str
    expires_at: Optional[int] = None
    x_liked: bool = False
    x_retweeted: bool = False
    x_replied: bool = False
    x_quoted: bool = False
    reply_text: Optional[str] = None
    quote_text: Optional[str] = None
    proceed_clicked: bool = False
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Discord helpers
# ---------------------------------------------------------------------------


def load_discord_token() -> str:
    """Load Discord user token from credentials."""
    data = json.loads(DISCORD_TOKEN_PATH.read_text())
    token = data.get("token", "")
    if not token:
        raise ValueError("Empty Discord token")
    return token


def discord_headers(token: str) -> dict:
    """Standard Discord API headers for selfbot."""
    return {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }


def make_nonce() -> str:
    """Generate a Discord snowflake nonce."""
    ts = int(time.time() * 1000) - 1420070400000
    return str((ts << 22) | random.randint(0, 2**22 - 1))


def fetch_latest_messages(token: str, channel_id: str, limit: int = 10) -> list:
    """Fetch latest messages from a Discord channel."""
    url = f"{DISCORD_API}/channels/{channel_id}/messages?limit={limit}"
    resp = requests.get(url, headers={"Authorization": token, "User-Agent": "Mozilla/5.0"}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def extract_tweet_info(message: dict) -> Optional[tuple]:
    """Extract (tweet_id, tweet_url, proceed_custom_id, required_tasks) from an Engage bot message.

    required_tasks is a set of task names: {"like", "retweet", "reply", "quote"}
    Returns None if the message doesn't contain valid engage data.
    """
    # Extract tweet URL from content or embeds
    tweet_id = None
    tweet_url = None

    content = message.get("content", "")
    m = TWEET_URL_RE.search(content)
    if m:
        tweet_id = m.group(1)
        tweet_url = m.group(0)

    # Fallback: check embeds
    if not tweet_id:
        for embed in message.get("embeds", []):
            embed_url = embed.get("url", "")
            m2 = ENGAGES_IO_RE.search(embed_url)
            if m2:
                pass

            desc = embed.get("description", "")
            m3 = TWEET_URL_RE.search(desc)
            if m3:
                tweet_id = m3.group(1)
                tweet_url = m3.group(0)

    # Extract proceed button custom_id and detect required tasks from emoji
    proceed_id = None
    required_tasks = set()
    for action_row in message.get("components", []):
        for comp in action_row.get("components", []):
            cid = comp.get("custom_id", "")
            if comp.get("disabled"):
                # For expired posts, still detect tasks from disabled buttons
                emoji = comp.get("emoji", {})
                emoji_id = emoji.get("id", "")
                if emoji_id in EMOJI_TASK_MAP:
                    required_tasks.add(EMOJI_TASK_MAP[emoji_id])
                continue

            # Detect task from emoji
            emoji = comp.get("emoji", {})
            emoji_id = emoji.get("id", "")
            if emoji_id in EMOJI_TASK_MAP:
                required_tasks.add(EMOJI_TASK_MAP[emoji_id])

            if PROCEED_RE.match(cid):
                proceed_id = cid
                if not tweet_id:
                    m4 = PROCEED_RE.match(cid)
                    tweet_id = m4.group(1)
                    tweet_url = f"https://x.com/i/status/{tweet_id}"

    if not tweet_id or not proceed_id:
        return None

    if not tweet_url:
        tweet_url = f"https://x.com/i/status/{tweet_id}"

    return tweet_id, tweet_url, proceed_id, required_tasks


def click_proceed_button(token: str, message_id: str, custom_id: str,
                         guild_id: str, channel_id: str) -> bool:
    """Click the proceed button on an Engage message via REST API interaction.

    Returns True on success (HTTP 204).
    """
    payload = {
        "type": 3,
        "nonce": make_nonce(),
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_flags": 0,
        "message_id": message_id,
        "application_id": ENGAGE_BOT_ID,
        "session_id": str(random.randint(10**18, 10**19)),
        "data": {
            "component_type": 2,
            "custom_id": custom_id,
        },
    }

    resp = requests.post(
        f"{DISCORD_API}/interactions",
        json=payload,
        headers=discord_headers(token),
        timeout=15,
    )

    if resp.status_code == 204:
        logger.info("Proceed button clicked on message %s", message_id)
        return True

    logger.warning("Proceed click returned %d: %s", resp.status_code, resp.text[:200])
    return False


# ---------------------------------------------------------------------------
# X/Twitter helpers (via twikit)
# ---------------------------------------------------------------------------

# Context-aware reply pools — selected based on tweet content
REPLY_POOLS = {
    "announcement": [
        "LFG 🚀",
        "Big things coming 🔥",
        "Been waiting for this announcement",
        "This is huge, congrats team",
        "Love the progress 👏",
        "Finally! Excited for this",
        "Great update, keep building",
        "This is what we've been waiting for",
    ],
    "community": [
        "The community keeps growing 🤝",
        "Love to see it, fam strong",
        "Best community in the space",
        "W community 🫡",
        "Together we build",
        "Community is everything",
        "This is why I'm here",
        "Fam showing up as always",
    ],
    "nft_mint": [
        "Minted! LFG 🎨",
        "Ready to mint",
        "Art looks fire 🔥",
        "Need this in my collection",
        "GM, let's get it",
        "WAGMI fam 🚀",
        "Bullish on the art",
        "Take my money",
    ],
    "game": [
        "Can't stop playing",
        "GM, grinding as always",
        "Leaderboard next 🏆",
        "Addictive gameplay",
        "Ready for the next round",
        "LFG gamers 🎮",
        "This game is different",
        "Bullish on gaming",
    ],
    "partnership": [
        "Great partnership 🤝",
        "Two powerhouses together",
        "This collab is massive",
        "Bullish on this partnership",
        "Perfect match",
        "Excited to see what comes next",
        "W collab 🫡",
    ],
    "general": [
        "LFG 🚀",
        "Bullish 🔥",
        "gm, love this",
        "WAGMI 💪",
        "This is the way",
        "Let's gooo 🐋",
        "Huge if true",
        "Been waiting for this",
        "Big things coming 🔥",
        "Count me in",
        "LFG fam 🤝",
        "Love the vision",
        "So bullish on this",
        "This is fire 🔥",
        "gm gm, amazing work",
        "Great update 👏",
        "Excited for what's next",
        "W project 🫡",
        "Can't wait for more",
    ],
}

# Keyword mappings for topic detection
TOPIC_KEYWORDS = {
    "announcement": ["announce", "launch", "live", "now available", "introducing", "reveal", "dropping", "drop"],
    "community": ["community", "family", "fam", "together", "team", "holder", "member", "milestone", "thank you"],
    "nft_mint": ["mint", "nft", "collection", "art", "opensea", "allowlist", "whitelist", "wl"],
    "game": ["game", "play", "score", "leaderboard", "round", "match", "win", "reward", "grind"],
    "partnership": ["partner", "collab", "together with", "teaming", "integration", "alliance"],
}


def detect_topic(tweet_text: str) -> str:
    """Detect tweet topic from content. Returns best-matching pool key."""
    text_lower = tweet_text.lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"


async def fetch_tweet_text(tweet_id: str) -> str:
    """Fetch tweet text via fxtwitter API (no auth needed)."""
    try:
        import urllib.request
        import json as _json

        url = f"https://api.fxtwitter.com/status/{tweet_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = _json.loads(resp.read().decode())
        return data.get("tweet", {}).get("text", "")
    except Exception as e:
        logger.debug("Failed to fetch tweet text via fxtwitter: %s", e)
        return ""


async def generate_reply_text(tweet_text: str) -> str:
    """Generate a contextual reply using Groq LLM."""
    api_key = _env.get("GROQ_API_KEY", "")
    if not api_key:
        topic = detect_topic(tweet_text)
        return random.choice(REPLY_POOLS[topic])

    prompt = f"""You are a crypto/NFT community member on X/Twitter. Write a short reply (max 280 chars) to this tweet.


Tweet: {tweet_text}

Rules:
- Be enthusiastic but natural, like a real community member
- No hashtags
- Keep it under 280 characters
- Use 1-2 emojis max
- Don't be generic — reference something specific from the tweet
- Sound like a real person, not a bot
- Don't use "LFG" or "WAGMI" every time — vary your language
- No quotation marks in the reply
- Reply ONLY with the reply text, nothing else"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.9,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        reply = data["choices"][0]["message"]["content"].strip().strip('"').strip("'")

        if len(reply) > 280:
            reply = reply[:277] + "..."

        return reply
    except Exception as e:
        logger.warning("Groq API failed, falling back to template: %s", e)
        topic = detect_topic(tweet_text)
        return random.choice(REPLY_POOLS[topic])


async def x_reply(tweet_id: str, text: str = "") -> dict:
    """Reply to a tweet via twikit.

    If no text provided, fetches tweet content and generates a contextual reply via Groq LLM.
    Returns {"replied": bool, "reply_text": str, "error": str|None}.
    """
    import sys
    sys.path.insert(0, "/home/ubuntu/scripts/x-client")
    from auth import get_client

    if not text:
        # Fetch tweet content for context-aware reply
        tweet_text = await fetch_tweet_text(tweet_id)
        if tweet_text:
            text = await generate_reply_text(tweet_text)
            logger.info("Generated reply for tweet %s: %s", tweet_id, text)
        else:
            # Fallback if fxtwitter fails
            topic = detect_topic("")
            text = random.choice(REPLY_POOLS[topic])
            logger.info("Using fallback template reply for tweet %s", tweet_id)

    result = {"replied": False, "reply_text": text, "error": None}

    try:
        client = await get_client()
        await client.create_tweet(text, reply_to=tweet_id)
        result["replied"] = True
        logger.info("Replied to tweet %s: %s", tweet_id, text)
    except Exception as e:
        err = str(e)
        result["error"] = f"reply: {err}"
        logger.warning("Failed to reply to tweet %s: %s", tweet_id, err)

    return result


async def x_quote(tweet_id: str, text: str = "") -> dict:
    """Quote tweet via twikit (retweet with comment).

    If no text provided, fetches tweet content and generates contextual quote text via Groq LLM.
    Returns {"quoted": bool, "quote_text": str, "error": str|None}.
    """
    import sys
    sys.path.insert(0, "/home/ubuntu/scripts/x-client")
    from auth import get_client

    if not text:
        tweet_text = await fetch_tweet_text(tweet_id)
        if tweet_text:
            text = await generate_reply_text(tweet_text)
            logger.info("Generated quote text for tweet %s: %s", tweet_id, text)
        else:
            topic = detect_topic("")
            text = random.choice(REPLY_POOLS[topic])
            logger.info("Using fallback template quote for tweet %s", tweet_id)

    result = {"quoted": False, "quote_text": text, "error": None}

    try:
        client = await get_client()
        await client.create_tweet(text, attachment_url=f"https://x.com/i/status/{tweet_id}")
        result["quoted"] = True
        logger.info("Quote tweeted %s: %s", tweet_id, text)
    except Exception as e:
        err = str(e)
        result["error"] = f"quote: {err}"
        logger.warning("Failed to quote tweet %s: %s", tweet_id, err)

    return result


async def x_engage(tweet_id: str, like: bool = True, retweet: bool = True) -> dict:
    """Like and/or retweet a tweet via twikit.

    Returns {"liked": bool, "retweeted": bool, "error": str|None}.
    """
    import sys
    sys.path.insert(0, "/home/ubuntu/scripts/x-client")
    from auth import get_client

    result = {"liked": False, "retweeted": False, "error": None}

    try:
        client = await get_client()

        if like:
            try:
                await client.favorite_tweet(tweet_id)
                result["liked"] = True
                logger.info("Liked tweet %s", tweet_id)
            except Exception as e:
                err = str(e)
                if "already" in err.lower():
                    result["liked"] = True  # Already liked
                    logger.info("Already liked tweet %s", tweet_id)
                else:
                    logger.warning("Failed to like tweet %s: %s", tweet_id, err)
                    result["error"] = f"like: {err}"

        # Random delay between like and RT to look human
        if like and retweet:
            await asyncio.sleep(random.uniform(3.0, 8.0))

        if retweet:
            try:
                await client.retweet(tweet_id)
                result["retweeted"] = True
                logger.info("Retweeted tweet %s", tweet_id)
            except Exception as e:
                err = str(e)
                if "already" in err.lower():
                    result["retweeted"] = True  # Already RT'd
                    logger.info("Already retweeted tweet %s", tweet_id)
                else:
                    logger.warning("Failed to retweet tweet %s: %s", tweet_id, err)
                    if result["error"]:
                        result["error"] += f"; rt: {err}"
                    else:
                        result["error"] = f"rt: {err}"

    except Exception as e:
        result["error"] = f"client: {e}"
        logger.error("X client error: %s", e)

    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def process_message(message: dict, token: str, guild_id: str, channel_id: str,
                          do_like: bool = True, do_retweet: bool = True,
                          do_reply: bool = True, do_quote: bool = True,
                          do_proceed: bool = True, dry_run: bool = False) -> EngageTask:
    """Process a single Engage bot message end-to-end.

    Tasks are auto-detected from button emojis. The do_* flags act as overrides:
    if False, that task is skipped even if detected. If True (default), the task
    runs only if detected in the message.
    """
    info = extract_tweet_info(message)
    if info is None:
        return EngageTask(
            message_id=message["id"],
            tweet_id="",
            tweet_url="",
            proceed_custom_id="",
            skipped=True,
            skip_reason="no tweet/proceed found in message",
        )

    tweet_id, tweet_url, proceed_id, required_tasks = info
    task = EngageTask(
        message_id=message["id"],
        tweet_id=tweet_id,
        tweet_url=tweet_url,
        proceed_custom_id=proceed_id,
    )

    logger.info("Detected tasks for %s: %s", tweet_url, required_tasks or "none (full engage)")

    if dry_run:
        logger.info("[DRY RUN] Would engage: %s (tasks: %s)", tweet_url, required_tasks)
        return task

    # Step 1: Like + RT (if detected or no tasks detected — fallback to full engage)
    should_like = do_like and ("like" in required_tasks or not required_tasks)
    should_rt = do_retweet and ("retweet" in required_tasks or not required_tasks)
    if should_like or should_rt:
        x_result = await x_engage(tweet_id, like=should_like, retweet=should_rt)
        task.x_liked = x_result["liked"]
        task.x_retweeted = x_result["retweeted"]
        if x_result["error"]:
            task.error = x_result["error"]

    # Step 2: Reply (if detected)
    if do_reply and ("reply" in required_tasks or not required_tasks):
        await asyncio.sleep(random.uniform(3.0, 8.0))
        reply_result = await x_reply(tweet_id)
        task.x_replied = reply_result["replied"]
        task.reply_text = reply_result["reply_text"]
        if reply_result["error"]:
            if task.error:
                task.error += f"; {reply_result['error']}"
            else:
                task.error = reply_result["error"]

    # Step 3: Quote tweet (if detected)
    if do_quote and ("quote" in required_tasks or not required_tasks):
        await asyncio.sleep(random.uniform(3.0, 8.0))
        quote_result = await x_quote(tweet_id)
        task.x_quoted = quote_result["quoted"]
        task.quote_text = quote_result["quote_text"]
        if quote_result["error"]:
            if task.error:
                task.error += f"; {quote_result['error']}"
            else:
                task.error = quote_result["error"]

    # Step 4: Click proceed button
    if do_proceed:
        success = click_proceed_button(token, task.message_id, proceed_id, guild_id, channel_id)
        task.proceed_clicked = success
        if not success and not task.error:
            task.error = "proceed button click failed"

    return task


async def run_monitor(state: StateManager,
                      do_like: bool = True, do_retweet: bool = True,
                      do_reply: bool = True, do_quote: bool = True,
                      do_proceed: bool = True, dry_run: bool = False) -> None:
    """Monitor active engagement channel for new Engage bot messages and auto-engage."""
    eng = state.active_engagement
    if not eng:
        logger.error("No active engagement configured. Use 'engage-cli.py add' first.")
        return

    token = load_discord_token()
    guild_id = eng["guild_id"]
    channel_id = eng["channel_id"]
    interval = ENGAGE_POLL_INTERVAL

    logger.info("Starting engage monitor on channel %s (interval=%ds)", channel_id, interval)

    while True:
        try:
            messages = fetch_latest_messages(token, channel_id, limit=20)
        except Exception as e:
            logger.error("Failed to fetch messages: %s", e)
            await asyncio.sleep(interval)
            continue

        # Filter for Engage bot messages
        engage_msgs = [m for m in messages if m.get("author", {}).get("id") == eng.get("bot_id", ENGAGE_BOT_ID)]

        for msg in engage_msgs:
            msg_id = msg["id"]

            # Skip already-engaged messages (persistent via state.json)
            if state.is_engaged(msg_id):
                continue

            task = await process_message(
                msg, token, guild_id, channel_id,
                do_like=do_like,
                do_retweet=do_retweet,
                do_reply=do_reply,
                do_quote=do_quote,
                do_proceed=do_proceed,
                dry_run=dry_run,
            )

            if task.skipped:
                logger.debug("Skipped message %s: %s", msg_id, task.skip_reason)
                continue

            # Mark as engaged in state
            state.mark_engaged(msg_id)

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
                status_parts.append(f"error: {task.error}")

            logger.info(
                "Engaged %s — %s",
                task.tweet_url,
                ", ".join(status_parts) if status_parts else "no action",
            )

            # Human-like delay between messages
            await asyncio.sleep(random.uniform(5.0, 15.0))

        # Update last_checked timestamp
        eng["last_checked"] = datetime.now(timezone.utc).isoformat()
        state.save()

        await asyncio.sleep(interval)


async def engage_latest(state: StateManager, count: int = 5,
                        do_like: bool = True, do_retweet: bool = True,
                        do_reply: bool = True, do_quote: bool = True,
                        do_proceed: bool = True, dry_run: bool = False) -> list:
    """Engage the latest N messages from The Engage bot (one-shot).

    Returns list of EngageTask results.
    """
    eng = state.active_engagement
    if not eng:
        return []

    token = load_discord_token()
    guild_id = eng["guild_id"]
    channel_id = eng["channel_id"]

    messages = fetch_latest_messages(token, channel_id, limit=count)

    engage_msgs = [m for m in messages if m.get("author", {}).get("id") == eng.get("bot_id", ENGAGE_BOT_ID)]

    results = []
    for msg in engage_msgs:
        msg_id = msg["id"]

        # Skip already-engaged unless it's a dry run
        if not dry_run and state.is_engaged(msg_id):
            continue

        task = await process_message(
            msg, token, guild_id, channel_id,
            do_like=do_like,
            do_retweet=do_retweet,
            do_reply=do_reply,
            do_quote=do_quote,
            do_proceed=do_proceed,
            dry_run=dry_run,
        )
        results.append(task)

        if not task.skipped and not dry_run:
            state.mark_engaged(msg_id)
            await asyncio.sleep(random.uniform(5.0, 15.0))

    # Update last_checked
    eng["last_checked"] = datetime.now(timezone.utc).isoformat()
    state.save()

    return results
