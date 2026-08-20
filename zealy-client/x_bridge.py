"""
x_bridge.py
===========
Bridge between the (synchronous) Zealy client and the (async, twikit-based)
Waguri X/Twitter client at /home/ubuntu/scripts/x-client.

Exposes a small synchronous facade — `XBridge` — so the Zealy client can perform
the real Twitter actions that Twitter-gated quests require (follow, like,
retweet, reply, quote, bookmark) before submitting a claim.

The async x-client is driven on a single persistent event loop with one cached
twikit client (cookie auth from x-cookies.json), so every action reuses the same
authenticated session.

Requires the runtime that has `twikit` installed:
    /home/ubuntu/.hermes/hermes-agent/venv/bin/python3
"""
import asyncio
import os
import sys

# Location of the X/Twitter client package (overridable for testing/relocation).
X_CLIENT_PATH = os.getenv("X_CLIENT_PATH", "/home/ubuntu/scripts/x-client")

# Short, varied replies used for `reply` / `quote` actions. Rotated so we don't
# post identical text repeatedly. Override the whole behaviour with a single
# fixed text via the ZEALY_X_REPLY env var, or pass reply_pool to XBridge.
DEFAULT_REPLIES = [
    "🔥🔥🔥",
    "Let's go 🚀",
    "Amazing 🙌",
    "Love this ✨",
    "Great update 👏",
    "LFG 🚀",
    "So good 🔥",
    "🙌🙌",
]


class XBridge:
    """Synchronous facade over the async (twikit) X/Twitter client."""

    def __init__(self, x_client_path: str = X_CLIENT_PATH, reply_pool=None):
        self.x_client_path = x_client_path
        env_reply = os.getenv("ZEALY_X_REPLY")
        self.reply_pool = reply_pool or ([env_reply] if env_reply else DEFAULT_REPLIES)
        self._loop = None
        self._client = None
        self._mods = None
        self._reply_idx = 0

    # ──────────────────────────────────────────────
    # Lazy import / event loop / client
    # ──────────────────────────────────────────────

    def _load_modules(self):
        """Import the x-client modules (auth, tweets, users). Raises if twikit missing."""
        if self._mods is None:
            if self.x_client_path not in sys.path:
                sys.path.insert(0, self.x_client_path)
            import auth as xauth
            import tweets as xtweets
            import users as xusers
            self._mods = (xauth, xtweets, xusers)
        return self._mods

    def available(self) -> bool:
        """True if the x-client + twikit can be imported in this runtime."""
        try:
            self._load_modules()
            return True
        except Exception:
            return False

    def _loop_obj(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _get_client(self):
        """Create (once) and return the authenticated twikit client."""
        if self._client is None:
            xauth = self._load_modules()[0]
            self._client = self._loop_obj().run_until_complete(xauth.get_client())
        return self._client

    def _run(self, coro):
        return self._loop_obj().run_until_complete(coro)

    def _next_reply(self) -> str:
        txt = self.reply_pool[self._reply_idx % len(self.reply_pool)]
        self._reply_idx += 1
        return txt

    @staticmethod
    def _status(action) -> str:
        """
        Run an action callable and map the result to a short status string.
        An 'already done' error (e.g. already following/retweeted) counts as
        success, because Zealy only checks the end state.
        """
        try:
            action()
            return "ok"
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ("already", "duplicate", "has already favorited")):
                return "already"
            return f"error: {type(e).__name__}: {str(e)[:140]}"

    # ──────────────────────────────────────────────
    # Public synchronous actions
    # ──────────────────────────────────────────────

    def whoami(self) -> str:
        xauth = self._load_modules()[0]
        c = self._get_client()
        me = self._run(xauth.get_me(c))
        return f"@{me.screen_name}"

    def follow(self, user_id: str) -> str:
        _, _, xusers = self._load_modules()
        c = self._get_client()
        return self._status(lambda: self._run(xusers.follow(str(user_id), client=c)))

    def like(self, tweet_id: str) -> str:
        _, xtweets, _ = self._load_modules()
        c = self._get_client()
        return self._status(lambda: self._run(xtweets.like(str(tweet_id), client=c)))

    def retweet(self, tweet_id: str) -> str:
        _, xtweets, _ = self._load_modules()
        c = self._get_client()
        return self._status(lambda: self._run(xtweets.retweet(str(tweet_id), client=c)))

    def bookmark(self, tweet_id: str) -> str:
        _, xtweets, _ = self._load_modules()
        c = self._get_client()
        return self._status(lambda: self._run(xtweets.bookmark(str(tweet_id), client=c)))

    def reply(self, tweet_id: str, text: str = None) -> str:
        _, xtweets, _ = self._load_modules()
        c = self._get_client()
        body = text or self._next_reply()
        return self._status(
            lambda: self._run(xtweets.create_tweet(text=body, reply_to=str(tweet_id), client=c))
        )

    def quote(self, tweet_url: str, text: str = None) -> str:
        _, xtweets, _ = self._load_modules()
        c = self._get_client()
        body = text or self._next_reply()
        clean_url = (tweet_url or "").split("?")[0]
        return self._status(
            lambda: self._run(xtweets.create_tweet(text=body, attachment_url=clean_url, client=c))
        )

    def tweet(self, text: str) -> str:
        _, xtweets, _ = self._load_modules()
        c = self._get_client()
        return self._status(lambda: self._run(xtweets.create_tweet(text=text, client=c)))

    def close(self):
        """Tear down the event loop (best-effort)."""
        if self._loop is not None:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None
            self._client = None
