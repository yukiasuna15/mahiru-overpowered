"""
Zealy API Client
================
Full-featured client for Zealy quest platform API.
Supports auth, quest discovery, task verification, and claim automation.

API Endpoints:
  v1 (api-v1.zealy.io): questboard, quest detail, claim, user profile
  v2 (api-v2.zealy.io/api): communities, users, sprints, recommended quests

Auth: OTP email + Turnstile captcha → JWT cookies (30-day expiry)
"""

import json
import time
import re
import subprocess
from os import getenv
from pathlib import Path
from typing import Optional

import requests


COOKIES_PATH = Path.home() / ".hermes" / "credentials" / "zealy-cookies.json"
USER_ID = "f1c369be-1f77-40ab-8c2e-17f811651db4"

V1_BASE = "https://api-v1.zealy.io"
V2_BASE = "https://api-v2.zealy.io/api"

TURNSTILE_SITEKEY = "0x4AAAAAAA9xxWmJYaOq_CNN"
TURNSTILE_URL = "https://zealy.io/login"

# All supported task types from API schema
TASK_TYPES = [
    "partnershipQuest", "partnership", "onChain", "api", "nft", "token",
    "text", "discord", "url", "telegram", "quiz", "invites",
    "visitLink", "file", "date", "number", "poll", "opinion",
    "twitterFollow", "twitterSpace", "tweetReact", "tweetQuote",
    "tweet", "twitterBlue", "tiktok", "proveYourHumanity",
]

# Task types that can be auto-verified without external action
AUTO_VERIFY_TYPES = {"visitLink", "text", "url", "number", "date", "poll"}

# Task types requiring Twitter action
TWITTER_TYPES = {"twitterFollow", "tweetReact", "tweetQuote", "tweet", "twitterBlue", "twitterSpace"}

# Task types requiring on-chain verification (wallet proof)
ONCHAIN_TYPES = {"onChain", "nft", "token"}

# Twitter task types we can fully automate via the X client bridge (x_bridge.py).
# twitterBlue / twitterSpace can't be automated and are intentionally excluded.
TWITTER_AUTOMATABLE = {"twitterFollow", "tweetReact", "tweetQuote", "tweet"}

# Seconds to wait after performing Twitter actions before submitting the claim,
# so the actions are reflected in Twitter's API by the time Zealy verifies them.
TWITTER_ACTION_DELAY = float(getenv("ZEALY_TWITTER_DELAY", "4"))

# Small gap between individual Twitter actions, to stay gentle on rate limits.
TWITTER_ACTION_GAP = float(getenv("ZEALY_X_ACTION_GAP", "1.5"))


class ZealyClient:
    """Zealy API client with session management and quest automation."""

    def __init__(self, cookies_path: str = str(COOKIES_PATH), email: str = "waguriagent@gmail.com"):
        self.email = email
        self.cookies_path = Path(cookies_path)
        self._x = None  # lazily-created X/Twitter bridge (see .x property)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Origin": "https://zealy.io",
            "Referer": "https://zealy.io/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        })
        self._load_cookies()

    # ──────────────────────────────────────────────
    # Cookie / Auth management
    # ──────────────────────────────────────────────

    def _load_cookies(self):
        """Load cookies from disk and set as Cookie header."""
        if not self.cookies_path.exists():
            raise FileNotFoundError(f"Cookies not found: {self.cookies_path}")
        with open(self.cookies_path) as f:
            cookies = json.load(f)
        # Set as Cookie header for all requests (more reliable than .cookies.set)
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self.session.headers["Cookie"] = cookie_str
        # Verify auth
        self.user_id = self._get_user_id()

    def _save_cookies(self):
        """Save current session cookies to disk."""
        cookies = {c.name: c.value for c in self.session.cookies}
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookies_path, "w") as f:
            json.dump(cookies, f, indent=2)

    def _get_user_id(self) -> str:
        """Get user ID from cookies or API."""
        resp = self.session.get(f"{V2_BASE}/users/{USER_ID}", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("id", USER_ID)
        return USER_ID

    def is_authenticated(self) -> bool:
        """Check if current session is valid."""
        resp = self.session.get(f"{V2_BASE}/users/{USER_ID}", timeout=15)
        return resp.status_code == 200 and resp.json().get("isMe", False)

    @property
    def x(self):
        """
        Lazily-created X/Twitter bridge (twikit). Used to perform the real
        Twitter actions that Twitter-gated quests require before claiming.
        Returns an XBridge instance, or None if the bridge can't be imported.
        """
        if self._x is None:
            try:
                from x_bridge import XBridge
                self._x = XBridge()
            except Exception:
                self._x = False  # sentinel: import failed, don't retry
        return self._x or None

    def login(self, turnstile_token: Optional[str] = None) -> bool:
        """
        Login via OTP email flow.
        1. Solve Turnstile captcha
        2. Send OTP to email
        3. Read OTP from Gmail (himalaya CLI)
        4. Verify OTP
        """
        # Step 1: Turnstile token
        if not turnstile_token:
            turnstile_token = self._solve_turnstile()

        # Step 2: Send OTP
        resp = self.session.post(
            f"{V2_BASE}/authentication/otp/send",
            json={"email": self.email, "turnstileToken": turnstile_token},
            headers={"Content-Type": "application/json", "Origin": "https://zealy.io", "Referer": "https://zealy.io/"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OTP send failed: {resp.status_code} {resp.text[:200]}")

        # Step 3: Read OTP
        time.sleep(5)
        otp = self._read_otp_from_gmail()
        if not otp:
            raise RuntimeError("Could not read OTP from Gmail")

        # Step 4: Verify
        resp = self.session.post(
            f"{V2_BASE}/authentication/otp/verify",
            json={"email": self.email, "otp": otp},
            headers={"Content-Type": "application/json", "Origin": "https://zealy.io", "Referer": "https://zealy.io/"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OTP verify failed: {resp.status_code} {resp.text[:200]}")

        self._save_cookies()
        self.user_id = self._get_user_id()
        return True

    def _solve_turnstile(self) -> str:
        """Solve Turnstile via Mahiru Solver."""
        key_path = Path.home() / ".hermes" / "credentials" / "turnstile-solver.env"
        api_key = key_path.read_text().split("API_KEY=")[1].strip()

        resp = requests.post(
            "https://turnstile.mahiru.my.id/cloudflare",
            json={"siteKey": TURNSTILE_SITEKEY, "domain": TURNSTILE_URL, "mode": "turnstile"},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=120,
        )
        data = resp.json()
        if "token" not in data:
            raise RuntimeError(f"Turnstile solve failed: {data}")
        return data["token"]

    def _read_otp_from_gmail(self) -> Optional[str]:
        """Read latest Zealy OTP from Gmail via himalaya CLI."""
        try:
            result = subprocess.run(
                ["himalaya", "envelope", "list", "--page-size", "3"],
                capture_output=True, text=True, timeout=15,
            )
            for line in result.stdout.split("\n"):
                if "Zealy login code" in line:
                    match = re.search(r"code is (\w{6})", line)
                    if match:
                        return match.group(1)
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────
    # User profile
    # ──────────────────────────────────────────────

    def get_me(self) -> dict:
        """Get current user profile."""
        resp = self.session.get(f"{V2_BASE}/users/{self.user_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def update_profile(self, **kwargs) -> dict:
        """
        Update user profile fields.
        Supported: name, country, city, twitterUsername, discordHandle, etc.
        """
        resp = self.session.patch(
            f"{V1_BASE}/users/me",
            data=kwargs,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_user_communities(self) -> list:
        """Get communities the user has joined."""
        resp = self.session.get(f"{V2_BASE}/users/{self.user_id}/communities", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("communities", data) if isinstance(data, dict) else data

    # ──────────────────────────────────────────────
    # Communities
    # ──────────────────────────────────────────────

    def list_communities(self, category: str = "featured", limit: int = 20, search: str = "") -> list:
        """
        List communities.
        category: 'featured', 'all', 'upcoming'
        """
        params = {"category": category, "limit": limit}
        if search:
            params["search"] = search
        resp = self.session.get(f"{V2_BASE}/communities", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("communities", data) if isinstance(data, dict) else data

    def get_community(self, slug: str) -> dict:
        """Get community details by slug (subdomain)."""
        resp = self.session.get(f"{V2_BASE}/communities/{slug}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def join_community(self, slug: str) -> bool:
        """Join a community (if open entry)."""
        # Community join happens automatically when you claim a quest
        return True

    def get_community_user(self, slug: str) -> dict:
        """Get user's membership info in a community."""
        resp = self.session.get(
            f"{V2_BASE}/communities/{slug}/users/{self.user_id}", timeout=15
        )
        resp.raise_for_status()
        return resp.json()

    # ──────────────────────────────────────────────
    # Quests
    # ──────────────────────────────────────────────

    def get_questboard(self, community_slug: str) -> list:
        """
        Get full questboard for a community.
        Returns list of categories, each containing quests with tasks and rewards.
        """
        resp = self.session.get(
            f"{V1_BASE}/communities/{community_slug}/questboard/v2",
            headers={"Origin": "https://zealy.io", "Referer": "https://zealy.io/"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_quest(self, community_slug: str, quest_id: str) -> dict:
        """
        Get full quest detail including tasks, rewards, conditions.
        Also returns claimed/completed/inReview status.
        """
        resp = self.session.get(
            f"{V1_BASE}/communities/{community_slug}/quests/v2/{quest_id}",
            headers={"Origin": "https://zealy.io", "Referer": "https://zealy.io/"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_recommended_quests(self, limit: int = 10) -> list:
        """Get recommended quests across all communities."""
        resp = self.session.get(f"{V2_BASE}/quests/recommended", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data) if isinstance(data, dict) else data

    def list_quests(self, community_slug: str) -> list:
        """
        Flat list of all quests in a community (convenience wrapper).
        Flattens questboard categories into a single list.
        """
        board = self.get_questboard(community_slug)
        quests = []
        for category in board:
            cat_title = category.get("title", "")
            for q in category.get("quests", []):
                q["_category"] = cat_title
                quests.append(q)
        return quests

    def get_undone_quests(self, community_slug: str) -> list:
        """Get quests that are not yet claimed."""
        quests = self.list_quests(community_slug)
        return [q for q in quests if not q.get("claimed", False)]

    # ──────────────────────────────────────────────
    # Task verification & Claim
    # ──────────────────────────────────────────────

    def execute_twitter_task(self, task: dict) -> dict:
        """
        Perform the real Twitter actions a single task requires, via the X
        bridge. Returns {action_label: status} where status is one of
        'ok' | 'already' | 'error: ...'. The key '_' carries a task-level
        message (e.g. when X is unavailable or the type can't be automated).
        """
        ttype = task.get("type")
        settings = task.get("settings", {}) or {}
        metadata = task.get("metadata", {}) or {}

        x = self.x
        if x is None or not x.available():
            return {"_": "error: X client unavailable (twikit not importable)"}

        results: dict = {}

        if ttype == "twitterFollow":
            uid = str(metadata.get("id") or "")
            username = settings.get("username", "?")
            if not uid:
                results[f"follow:@{username}"] = "error: no target user id in metadata"
            else:
                results[f"follow:@{username}"] = x.follow(uid)

        elif ttype == "tweetReact":
            tweet_id = str(metadata.get("tweetId") or "")
            tweet_url = settings.get("tweetUrl", "")
            creator = metadata.get("creator", {}) or {}
            actions = settings.get("actions", [])
            if not tweet_id and not tweet_url:
                return {"_": "error: tweetReact task has no tweetId/tweetUrl"}
            for i, action in enumerate(actions):
                if i:
                    time.sleep(TWITTER_ACTION_GAP)
                if action == "like":
                    results["like"] = x.like(tweet_id)
                elif action == "retweet":
                    results["retweet"] = x.retweet(tweet_id)
                elif action == "reply":
                    results["reply"] = x.reply(tweet_id)
                elif action == "quote":
                    results["quote"] = x.quote(tweet_url)
                elif action == "bookmark":
                    results["bookmark"] = x.bookmark(tweet_id)
                elif action == "follow":
                    cid = str(creator.get("id") or "")
                    results["follow"] = x.follow(cid) if cid else "error: no creator id"
                else:
                    results[action] = f"error: unknown action '{action}'"

        elif ttype == "tweetQuote":
            results["quote"] = x.quote(settings.get("tweetUrl", ""))

        elif ttype == "tweet":
            text = settings.get("defaultValue") or settings.get("text") or settings.get("title") or "gm 🚀"
            results["tweet"] = x.tweet(text)

        else:
            results["_"] = f"unsupported: {ttype} cannot be automated"

        return results

    def claim_quest(self, community_slug: str, quest_id: str, task_values: list) -> dict:
        """
        Claim a quest by submitting task values.
        
        task_values: list of {"type": "taskType", "taskId": "...", ...extra fields}
        
        Returns claim result with per-task validation status.
        Response codes:
          202 = accepted (polling for async verification)
          400 = validation result (check taskValidations)
          403 = forbidden
        """
        resp = self.session.post(
            f"{V1_BASE}/communities/{community_slug}/quests/v2/{quest_id}/claim",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://zealy.io",
                "Referer": f"https://zealy.io/cw/{community_slug}/_/questboard",
                "X-Zealy-Subdomain": community_slug,
            },
            json={"taskValues": task_values},
            timeout=30,
        )
        # 202 = async (poll), 400 = validation result, 200 = success
        return {
            "status_code": resp.status_code,
            "data": resp.json() if resp.text else {},
            "success": resp.status_code in (200, 202),
        }

    def build_task_values(self, quest_detail: dict, extra_values: Optional[dict] = None) -> list:
        """
        Build taskValues array from quest detail.
        Auto-fills type and taskId from quest data.
        
        extra_values: dict mapping taskId -> extra fields (e.g. {"taskId": {"value": "some_value"}})
        """
        extra_values = extra_values or {}
        task_values = []
        for task in quest_detail.get("tasks", []):
            tv = {
                "type": task["type"],
                "taskId": task["id"],
            }
            # Merge extra values for this task
            if task["id"] in extra_values:
                tv.update(extra_values[task["id"]])
            task_values.append(tv)
        return task_values

    def auto_claim_quest(self, community_slug: str, quest_id: str, do_twitter: bool = True) -> dict:
        """
        Auto-claim a quest: fetch detail, perform any required Twitter actions
        (via the X bridge), build task values, then submit the claim.

        Handles auto-verifyable, Twitter (twitterFollow / tweetReact / tweetQuote
        / tweet), and on-chain task types. Set do_twitter=False to submit the
        claim without performing Twitter actions first.
        """
        detail = self.get_quest(community_slug, quest_id)

        if detail.get("claimed"):
            return {"success": True, "message": "Already claimed", "skipped": True}

        if detail.get("locked"):
            return {"success": False, "message": "Quest is locked", "skipped": True}

        # Check if all tasks are handleable
        tasks = detail.get("tasks", [])
        task_types = {t["type"] for t in tasks}
        handleable = AUTO_VERIFY_TYPES | TWITTER_TYPES | ONCHAIN_TYPES

        if not task_types.issubset(handleable):
            unsupported = task_types - handleable
            return {
                "success": False,
                "message": f"Unsupported task types: {unsupported}",
                "skipped": True,
            }

        # 1. Perform the real Twitter actions for any Twitter-gated tasks.
        twitter_actions = {}
        if do_twitter:
            for task in tasks:
                if task["type"] in TWITTER_TYPES:
                    twitter_actions[task["id"]] = self.execute_twitter_task(task)
            # Give Twitter's API a moment to reflect the actions before claiming.
            if twitter_actions:
                time.sleep(TWITTER_ACTION_DELAY)

        # 2. Build task values based on types.
        wallet = getenv("WALLET_ADDRESS", "")

        task_values = []
        for task in tasks:
            tv = {"type": task["type"], "taskId": task["id"]}
            # On-chain tasks may need wallet address
            if task["type"] in ONCHAIN_TYPES:
                tv["value"] = wallet
            task_values.append(tv)

        # 3. Submit the claim and attach the Twitter action results.
        result = self.claim_quest(community_slug, quest_id, task_values)
        if twitter_actions:
            result["twitter_actions"] = twitter_actions
        return result

    # ──────────────────────────────────────────────
    # Bulk operations
    # ──────────────────────────────────────────────

    def clear_community(self, community_slug: str, dry_run: bool = False, do_twitter: bool = True) -> list:
        """
        Attempt to claim all undone quests in a community.
        Performs Twitter actions for Twitter-gated quests unless do_twitter=False.
        Returns list of results per quest.
        """
        quests = self.get_undone_quests(community_slug)
        results = []

        for q in quests:
            quest_id = q.get("id", "")
            quest_name = q.get("name", q.get("title", "Unknown"))
            tasks = q.get("tasks", [])
            task_types = [t.get("type", "?") for t in tasks]

            result = {
                "quest_id": quest_id,
                "name": quest_name,
                "task_types": task_types,
                "category": q.get("_category", ""),
            }

            if dry_run:
                result["action"] = "dry_run"
                result["auto_claimable"] = all(
                    t in AUTO_VERIFY_TYPES | TWITTER_TYPES | ONCHAIN_TYPES for t in task_types
                )
                results.append(result)
                continue

            try:
                claim_result = self.auto_claim_quest(community_slug, quest_id, do_twitter=do_twitter)
                result.update(claim_result)
            except Exception as e:
                result["success"] = False
                result["error"] = str(e)

            results.append(result)

        return results

    # ──────────────────────────────────────────────
    # Sprints & Leaderboard
    # ──────────────────────────────────────────────

    def get_sprints(self) -> list:
        """Get active sprints/competitions."""
        resp = self.session.get(f"{V2_BASE}/sprints", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data) if isinstance(data, dict) else data

    def get_leaderboard(self, community_slug: str, sprint_id: Optional[str] = None) -> dict:
        """Get community leaderboard."""
        url = f"{V2_BASE}/communities/{community_slug}/leaderboard/sprint"
        if sprint_id:
            url += f"?sprintId={sprint_id}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ──────────────────────────────────────────────
    # Referral
    # ──────────────────────────────────────────────

    def get_referral_link(self, community_slug: str) -> str:
        """Get user's referral link for a community."""
        resp = self.session.get(
            f"{V1_BASE}/communities/{community_slug}/users/me/referral-link",
            headers={"Origin": "https://zealy.io", "Referer": "https://zealy.io/"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # ──────────────────────────────────────────────
    # Subscription
    # ──────────────────────────────────────────────

    def get_subscription_status(self, community_slug: str) -> dict:
        """Get community subscription status."""
        resp = self.session.get(
            f"{V2_BASE}/communities/{community_slug}/subscription/status", timeout=15
        )
        resp.raise_for_status()
        return resp.json()

    # ──────────────────────────────────────────────
    # Twitter task helpers
    # ──────────────────────────────────────────────

    def extract_tweet_tasks(self, quest_detail: dict) -> list:
        """
        Extract tweet IDs and required actions from tweetReact/tweetQuote tasks.
        Returns list of {"taskId", "tweetId", "tweetUrl", "actions"}.
        """
        tweets = []
        for task in quest_detail.get("tasks", []):
            if task["type"] in ("tweetReact", "tweetQuote", "tweet"):
                settings = task.get("settings", {})
                metadata = task.get("metadata", {})
                tweets.append({
                    "taskId": task["id"],
                    "type": task["type"],
                    "tweetId": metadata.get("tweetId", ""),
                    "tweetUrl": settings.get("tweetUrl", ""),
                    "actions": settings.get("actions", []),
                    "creator": metadata.get("creator", {}),
                })
        return tweets

    def extract_follow_tasks(self, quest_detail: dict) -> list:
        """
        Extract Twitter follow targets from twitterFollow tasks.
        Returns list of {"taskId", "username", "userId"}.
        """
        follows = []
        for task in quest_detail.get("tasks", []):
            if task["type"] == "twitterFollow":
                settings = task.get("settings", {})
                metadata = task.get("metadata", {})
                follows.append({
                    "taskId": task["id"],
                    "username": settings.get("username", ""),
                    "userId": metadata.get("id", ""),
                })
        return follows

    # ──────────────────────────────────────────────
    # On-chain task helpers
    # ──────────────────────────────────────────────

    def extract_onchain_tasks(self, quest_detail: dict) -> list:
        """
        Extract on-chain task details from quest.
        Returns list of {taskId, type, chain, contractAddress, tokenType, minBalance, ...}
        """
        tasks = []
        for task in quest_detail.get("tasks", []):
            if task["type"] in ONCHAIN_TYPES:
                settings = task.get("settings", {})
                metadata = task.get("metadata", {})
                tasks.append({
                    "taskId": task["id"],
                    "type": task["type"],
                    "taskType": task["type"],  # onChain, nft, token
                    "chain": settings.get("chain", metadata.get("chain", "")),
                    "contractAddress": settings.get("contractAddress", metadata.get("contractAddress", "")),
                    "tokenType": settings.get("tokenType", ""),  # ERC-20, ERC-721, ERC-1155
                    "minBalance": settings.get("minBalance", metadata.get("minBalance", "")),
                    "tokenId": settings.get("tokenId", metadata.get("tokenId", "")),
                    "rawSettings": settings,
                    "rawMetadata": metadata,
                })
        return tasks

    def build_onchain_task_values(self, quest_detail: dict, wallet_address: str = "") -> list:
        """
        Build taskValues for on-chain tasks.
        On-chain verification typically needs the wallet address as proof.
        """
        task_values = []
        for task in quest_detail.get("tasks", []):
            tv = {"type": task["type"], "taskId": task["id"]}
            # Some on-chain tasks need wallet address in value field
            if wallet_address:
                tv["value"] = wallet_address
            task_values.append(tv)
        return task_values
