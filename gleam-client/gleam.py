"""
Gleam.io API Client
===================
Full-featured client for Gleam.io giveaway/contest platform.
Supports auth, contestant registration, task completion, and bulk entry automation.

API Base: https://gleam.io
Auth: Twitter OAuth → cert token
CSRF: X-CSRF-Token header (from cookie)
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests


COOKIES_PATH = Path.home() / ".hermes" / "credentials" / "gleam-cookies.json"
CEX_UIDS_PATH = Path.home() / ".hermes" / "credentials" / "gleam-cex-uids.json"
X_COOKIES_PATH = Path.home() / ".hermes" / "credentials" / "x-cookies.json"

BASE_URL = "https://gleam.io"
TURNSTILE_SITEKEY_DEFAULT = "0x4AAAAAAAAma6FCjIY5lVkD"  # fallback if HTML parse fails
TURNSTILE_URL = "https://gleam.io"
CAPTCHA_PROVIDER_ENV = Path.home() / ".hermes" / "credentials" / "captcha-provider.env"

# X.com (Twitter) web app public bearer token — same for all users
X_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Gleam's "goodStr" salt used to sign the fraud token in the `f` body field.
# Extracted from widget.gleamjs.io JS (intsToStr([53,101,96,105,124,88,86,59,...])).
GLEAM_GOOD_STR = "5e`i|XV;>w6DtqPZ'"


def _gleam_md5(s: str) -> str:
    """Replicate gleam's JS md5 output, which swaps 32-bit words pairwise:
    standard hex output `AAAA BBBB CCCC DDDD` becomes `BBBB AAAA DDDD CCCC`.
    """
    raw = hashlib.md5(s.encode()).hexdigest()
    return raw[8:16] + raw[0:8] + raw[24:32] + raw[16:24]

# Known entry method types
ENTRY_TYPES = {
    "twitter_follow": "Follow on Twitter",
    "twitter_retweet": "Retweet on Twitter",
    "twitter_tweet": "Tweet on Twitter",
    "twitter_like": "Like on Twitter",
    "youtube_subscribe": "Subscribe on YouTube",
    "youtube_watch": "Watch on YouTube",
    "instagram_follow": "Follow on Instagram",
    "telegram_join": "Join Telegram",
    "discord_join": "Join Discord",
    "visit_url": "Visit URL",
    "referral": "Refer a friend",
    "custom": "Custom action",
}


class GleamClient:
    """Gleam.io API client with session management and contest automation."""

    def __init__(self, cookies_path: str = str(COOKIES_PATH)):
        self.cookies_path = Path(cookies_path)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": "https://gleam.io",
            "Referer": "https://gleam.io/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        })
        self.csrf_token = None
        self.contestant_data = None
        self.cert = None
        self.cex_uids = {}
        # Cumulative interaction stats — grow across submissions in a session
        # to mimic a real user. Reset on new GleamClient instance.
        self._stats_m = 0   # mouse moves total
        self._stats_c = 0   # clicks total
        self._stats_k = 0   # keypresses total
        self._stats_i = 0   # interaction count
        # Cache Turnstile sitekey per campaign (sniffed from page HTML)
        self._sitekey_cache: dict[str, str] = {}
        self._load_cookies()
        self._load_cex_uids()

    def get_turnstile_sitekey(self, campaign_key: str) -> str:
        """Detect the Turnstile sitekey for a campaign by scraping its page.

        Falls back to TURNSTILE_SITEKEY_DEFAULT if no key is found. Cached per
        campaign so we only fetch once.
        """
        if campaign_key in self._sitekey_cache:
            return self._sitekey_cache[campaign_key]

        try:
            resp = self.session.get(
                f"{BASE_URL}/m/{campaign_key}",
                timeout=15,
                headers={"Accept": "text/html"},
                allow_redirects=True,
            )
            if resp.status_code == 200:
                # Cloudflare Turnstile sitekeys are 0x + base62; gleam embeds
                # them inline in the widget config block.
                import re
                m = re.search(r'0x4[A-Za-z0-9]{20,}', resp.text)
                if m:
                    sitekey = m.group(0)
                    self._sitekey_cache[campaign_key] = sitekey
                    return sitekey
        except Exception:
            pass

        self._sitekey_cache[campaign_key] = TURNSTILE_SITEKEY_DEFAULT
        return TURNSTILE_SITEKEY_DEFAULT

    def _build_stats(self, has_input: bool) -> dict:
        """Generate plausible interaction stats for a queue-entry submission.

        Each call simulates "what happened since last submission":
        - m/c/k grow as cumulative totals
        - ml/cl/kl are the deltas since the previous submission
        - i increments once per submission
        """
        import random
        delta_m = random.randint(40, 180)        # mouse moves between submissions
        delta_c = random.randint(1, 5)           # clicks (open entry, focus input, submit)
        delta_k = random.randint(2, 12) if has_input else 0
        self._stats_m += delta_m
        self._stats_c += delta_c
        self._stats_k += delta_k
        self._stats_i += 1
        return {
            "e": "nd",
            "m": self._stats_m,
            "c": self._stats_c,
            "k": self._stats_k,
            "ts": 0,
            "tm": 0,
            "ml": delta_m,
            "cl": delta_c,
            "kl": delta_k,
            "tsl": 0,
            "tml": 0,
            "i": self._stats_i - 1,
        }

    # ──────────────────────────────────────────────
    # Cookie / Auth management
    # ──────────────────────────────────────────────

    def _load_cookies(self):
        """Load gleam.io cookies from disk into the session cookie jar."""
        if not self.cookies_path.exists():
            return

        with open(self.cookies_path) as f:
            data = json.load(f)

        # Load gleam cookies into jar (domain-scoped) so Set-Cookie can update them
        for k, v in data.get("cookies", {}).items():
            self.session.cookies.set(k, v, domain="gleam.io")

        # Load CSRF token
        self.csrf_token = data.get("csrf_token")
        if self.csrf_token:
            self.session.headers["X-CSRF-Token"] = self.csrf_token

        # Load contestant data
        self.contestant_data = data.get("contestant")
        if self.contestant_data:
            self.cert = self.contestant_data.get("cert")

    def _save_cookies(self):
        """Save current gleam.io session state to disk.

        Includes `fpr` (fraud fingerprint) so the same value persists across
        runs — switching it between submissions is a strong fraud signal.
        """
        cookies = {
            c.name: c.value
            for c in self.session.cookies
            if c.domain and "gleam.io" in c.domain
        }

        data = {
            "cookies": cookies,
            "csrf_token": self.csrf_token,
            "contestant": self.contestant_data,
        }

        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookies_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_x_cookies(self) -> dict:
        """Load X.com (Twitter) cookies from ~/.hermes/credentials/x-cookies.json."""
        if not X_COOKIES_PATH.exists():
            raise FileNotFoundError(
                f"X cookies not found at {X_COOKIES_PATH}. "
                "Export X cookies from your browser first."
            )

        with open(X_COOKIES_PATH) as f:
            x_cookies = json.load(f)

        if "auth_token" not in x_cookies or "ct0" not in x_cookies:
            raise RuntimeError("X cookies missing required fields (auth_token, ct0)")

        return x_cookies

    def refresh_csrf(self) -> str:
        """Fetch a fresh CSRF token via GET /csrf and store it on the session.

        The endpoint returns 204 with no body but sets the XSRF-TOKEN cookie via
        Set-Cookie. That cookie value is what gleam expects as the X-CSRF-Token
        header on subsequent protected requests.
        """
        self.session.get(f"{BASE_URL}/csrf", timeout=15)
        csrf = self.session.cookies.get("XSRF-TOKEN", domain="gleam.io")
        if csrf:
            self.csrf_token = csrf
            self.session.headers["X-CSRF-Token"] = csrf
        return csrf or ""

    def _load_cex_uids(self):
        """Load CEX UIDs from disk."""
        if not CEX_UIDS_PATH.exists():
            return
        
        with open(CEX_UIDS_PATH) as f:
            self.cex_uids = json.load(f)

    def get_cex_uid(self, exchange: str) -> str:
        """
        Get CEX UID by exchange name.
        
        Args:
            exchange: Exchange name (kucoin, binance, okx, bybit, gateio, bitget, mexc)
        
        Returns:
            UID string or empty string
        """
        # Normalize exchange name
        exchange = exchange.lower().replace(".", "").replace(" ", "")
        
        # Aliases
        aliases = {
            "gate": "gateio",
            "gateio": "gateio",
            "okex": "okx",
        }
        exchange = aliases.get(exchange, exchange)
        
        return self.cex_uids.get(exchange, "")

    def is_authenticated(self) -> bool:
        """Check if current session is valid."""
        if not self.cert:
            return False
        
        # Try to get contestant data
        try:
            resp = self.session.patch(
                f"{BASE_URL}/contestant_backdoor_api/retrieve_value/twitter",
                timeout=15,
            )
            if resp.status_code == 201:
                data = resp.json()
                if data.get("contestant"):
                    self.contestant_data = data["contestant"]
                    self.cert = self.contestant_data.get("cert")
                    return True
        except Exception:
            pass
        
        return False

    def login_with_cookies(self, cookies: dict, csrf_token: str) -> bool:
        """
        Login using manually provided cookies and CSRF token.
        
        Args:
            cookies: dict of cookie name → value
            csrf_token: X-CSRF-Token value
        """
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self.session.headers["Cookie"] = cookie_str
        self.csrf_token = csrf_token
        self.session.headers["X-CSRF-Token"] = csrf_token
        
        # Try to get contestant data
        if self.is_authenticated():
            self._save_cookies()
            return True
        
        return False

    def _solve_turnstile(self, sitekey: str = None, timeout: int = 90) -> str:
        """Solve Gleam's Turnstile via CapSolver.

        Reads CAPTCHA_CAPSOLVER_API_KEY from `~/.hermes/credentials/captcha-provider.env`.

        Args:
            sitekey: Turnstile sitekey for the target campaign. If omitted,
                falls back to TURNSTILE_SITEKEY_DEFAULT. Use
                `get_turnstile_sitekey(campaign_key)` to auto-detect.
        """
        if sitekey is None:
            sitekey = TURNSTILE_SITEKEY_DEFAULT
        if not CAPTCHA_PROVIDER_ENV.exists():
            raise FileNotFoundError(f"Missing {CAPTCHA_PROVIDER_ENV}")

        api_key = None
        for line in CAPTCHA_PROVIDER_ENV.read_text().splitlines():
            if line.startswith("CAPTCHA_CAPSOLVER_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break
        if not api_key:
            raise RuntimeError("CAPTCHA_CAPSOLVER_API_KEY not set in captcha-provider.env")

        create = requests.post(
            "https://api.capsolver.com/createTask",
            json={
                "clientKey": api_key,
                "task": {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": TURNSTILE_URL,
                    "websiteKey": sitekey,
                },
            },
            timeout=30,
        ).json()
        task_id = create.get("taskId")
        if not task_id:
            raise RuntimeError(f"CapSolver createTask failed: {create}")

        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(2)
            result = requests.post(
                "https://api.capsolver.com/getTaskResult",
                json={"clientKey": api_key, "taskId": task_id},
                timeout=30,
            ).json()
            status = result.get("status")
            if status == "ready":
                token = result.get("solution", {}).get("token")
                if not token:
                    raise RuntimeError(f"CapSolver ready but no token: {result}")
                return token
            if status == "failed":
                raise RuntimeError(
                    f"CapSolver solve failed: {result.get('errorDescription', result)}"
                )
        raise RuntimeError(f"CapSolver solve timed out after {timeout}s")

    # ──────────────────────────────────────────────
    # Campaign / Contest
    # ──────────────────────────────────────────────

    def get_campaign(self, campaign_key: str) -> dict:
        """
        Get campaign details by key or full URL.
        Scrapes page HTML for embedded campaign data (no public JSON API).

        Args:
            campaign_key: e.g., "MPPty" or "https://gleam.io/MPPty/kucoin-x-genius-genius"

        Returns:
            Campaign data with entry methods, prizes, etc.
        """
        # Handle full URLs
        slug = ""
        if campaign_key.startswith("http"):
            campaign_key, slug = self.parse_campaign_url(campaign_key)

        # Cloudflare blocks fresh requests; warm up the session if we haven't yet
        if not self.session.cookies.get("__cf_bm", domain=".gleam.io"):
            self.refresh_csrf()

        # `/m/<key>` is gleam's canonical short URL that 301s to /<key>/<slug>.
        # Hitting it lets us resolve the slug automatically.
        url = f"{BASE_URL}/{campaign_key}/{slug}" if slug else f"{BASE_URL}/m/{campaign_key}"
        resp = self.session.get(
            url,
            timeout=15,
            headers={"Accept": "text/html"},
            allow_redirects=True,
        )

        if resp.status_code == 404:
            return {
                "key": campaign_key,
                "name": "Unknown Campaign",
                "entry_methods": [],
                "prizes": [],
                "state": "not_found",
                "error": f"Campaign {campaign_key} not found (404)",
            }

        resp.raise_for_status()

        campaign = self._parse_campaign_html(resp.text)
        campaign["key"] = campaign_key
        # Capture the resolved slug from the final URL (after /m/ redirect)
        try:
            parts = urlparse(resp.url).path.strip("/").split("/")
            if len(parts) >= 2:
                campaign["slug"] = parts[1]
        except Exception:
            pass
        return campaign

    def _parse_campaign_html(self, html: str) -> dict:
        """Parse campaign data from page HTML.

        Gleam embeds the full campaign payload as the first argument to
        ng-init='initCampaign({...})' on the .popup-blocks-container div. The
        JSON is HTML-entity-encoded (&quot;, &#39;, &amp;, etc.).
        """
        import re
        import html as html_mod

        campaign = {
            "name": "",
            "entry_methods": [],
            "prizes": [],
            "state": "unknown",
        }

        # Extract campaign name from title
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        if title_match:
            campaign["name"] = title_match.group(1).split(" - ")[0].strip()

        # Find the initCampaign(...) call and balance the parentheses to extract
        # the JSON arg even when it contains nested objects/arrays.
        marker = "initCampaign("
        start = html.find(marker)
        if start == -1:
            return campaign

        i = start + len(marker)
        depth = 0
        json_start = i
        # Scan with brace balancing — the value starts with `{`
        if i >= len(html) or html[i] != "{":
            return campaign

        while i < len(html):
            ch = html[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_end = i + 1
                    raw = html[json_start:json_end]
                    decoded = html_mod.unescape(raw)
                    try:
                        data = json.loads(decoded)
                    except json.JSONDecodeError:
                        return campaign
                    # Merge known fields
                    campaign["name"] = data.get("name") or campaign["name"]
                    campaign["entry_methods"] = data.get("entry_methods", [])
                    campaign["prizes"] = data.get("prizes", [])
                    campaign["state"] = data.get("state") or "active"
                    # Stash the full raw payload too in case callers need other fields
                    campaign["_raw"] = data
                    return campaign
            i += 1

        return campaign

    def parse_campaign_url(self, url: str) -> tuple[str, str]:
        """
        Parse Gleam URL to extract campaign key and slug.
        
        Args:
            url: e.g., "https://gleam.io/MPPty/kucoin-x-genius-genius"
        
        Returns:
            (campaign_key, slug)
        """
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            return parts[0], ""
        raise ValueError(f"Invalid Gleam URL: {url}")

    # ──────────────────────────────────────────────
    # Contestant Registration
    # ──────────────────────────────────────────────

    def defer_oauth(self, campaign_key: str, entry_method_id: str = "") -> dict:
        """
        Start Twitter OAuth flow.
        
        Args:
            campaign_key: e.g., "MPPty"
            entry_method_id: optional entry method ID
        
        Returns:
            OAuth redirect URL
        """
        body = {
            "optional_referrer_url": "",
            "optional_location_url": f"https://gleam.io/{campaign_key}",
            "backdoor_campaign_key": campaign_key,
        }
        if entry_method_id:
            body["optional_entry_method_id"] = entry_method_id
        
        resp = self.session.post(
            f"{BASE_URL}/contestant_backdoor_api/v5/defer_oauth/twitter",
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def permit_access(self, backdoor_signature: str) -> bool:
        """
        Complete OAuth with signature.

        Args:
            backdoor_signature: OAuth signature from Twitter callback
        """
        resp = self.session.post(
            f"{BASE_URL}/contestant_backdoor_api/v5/permit_access/twitter",
            json={"backdoor_signature": backdoor_signature},
            timeout=15,
        )
        return resp.status_code == 204

    def _x_oauth_approve(self, backdoor_authorize_url: str, x_cookies: dict) -> tuple[str, str]:
        """
        Approve the Twitter OAuth2 grant directly via X.com's XHR endpoint.
        Skips the browser by calling the same /i/api/2/oauth2/authorize endpoint
        that x.com's own JS uses under the hood.

        Args:
            backdoor_authorize_url: URL returned by defer_oauth (https://x.com/i/oauth2/authorize?...)
            x_cookies: dict of X.com cookies (must include auth_token and ct0)

        Returns:
            (auth_code, state) — both required for the gleam resume_oauth callback
        """
        ct0 = x_cookies["ct0"]
        parsed = urlparse(backdoor_authorize_url)
        query = parse_qs(parsed.query)
        state = query.get("state", [""])[0]

        # Swap /i/oauth2/authorize (HTML page) → /i/api/2/oauth2/authorize (XHR)
        api_url = "https://x.com/i/api/2/oauth2/authorize?" + parsed.query

        ua = self.session.headers.get("User-Agent", "")
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Authorization": f"Bearer {X_BEARER}",
            "Origin": "https://x.com",
            "Referer": backdoor_authorize_url,
            "User-Agent": ua,
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "en",
        }

        # Use a fresh requests session so gleam headers/cookies don't leak into x.com
        x_session = requests.Session()
        for k, v in x_cookies.items():
            x_session.cookies.set(k, v, domain=".x.com")

        # 1) GET — X.com returns the pre-issued auth_code along with the app info
        resp = x_session.get(api_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"X.com authorize GET failed ({resp.status_code}): {resp.text[:300]}"
            )
        auth_code = resp.json().get("auth_code")
        if not auth_code:
            raise RuntimeError(f"X.com authorize GET did not return auth_code: {resp.text[:300]}")

        # 2) POST approval=true&code=<auth_code> — this commits the OAuth grant
        post_headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
        resp = x_session.post(
            "https://x.com/i/api/2/oauth2/authorize",
            data={"approval": "true", "code": auth_code},
            headers=post_headers,
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"X.com authorize POST failed ({resp.status_code}): {resp.text[:300]}"
            )

        return auth_code, state

    def resume_oauth(self, state: str, code: str) -> bool:
        """
        Hand the X.com auth_code back to gleam so it can exchange it for tokens
        and mint the contestant cert in the current session.
        """
        resp = self.session.get(
            f"{BASE_URL}/contestant_backdoor/resume_oauth/twitter",
            params={"state": state, "code": code},
            timeout=30,
            allow_redirects=True,
        )
        return resp.status_code in (200, 302)

    def oauth_twitter(self, campaign_key: str, entry_method_id: str = "") -> dict:
        """
        Full Twitter OAuth flow without a browser.

        Requires X cookies at ~/.hermes/credentials/x-cookies.json (must include
        auth_token and ct0). After this returns successfully, self.cert is set
        and you can register/claim/complete tasks for the campaign.

        Args:
            campaign_key: e.g. "MPPty"
            entry_method_id: optional entry method id (used by gleam telemetry)

        Returns:
            Contestant data including cert.
        """
        # Pull X cookies up front so we fail fast if they're missing
        x_cookies = self._load_x_cookies()

        # Make sure we have a valid gleam session + CSRF
        self.refresh_csrf()

        # 1) Tell gleam we're starting an OAuth attempt
        defer = self.defer_oauth(campaign_key, entry_method_id)
        authorize_url = defer.get("backdoor_authorize_url")
        backdoor_signature = defer.get("backdoor_signature")
        task_seed = defer.get("backdoor_task_seed", {})
        if not authorize_url or not backdoor_signature:
            raise RuntimeError(f"defer_oauth returned unexpected payload: {defer}")

        # 2) Pre-approve the callback on gleam's side
        if not self.permit_access(backdoor_signature):
            raise RuntimeError("permit_access failed (expected 204)")

        # 3) Approve the OAuth grant on x.com — no browser needed
        auth_code, state = self._x_oauth_approve(authorize_url, x_cookies)

        # 4) Deliver the auth_code to gleam → mints the cert in the session
        if not self.resume_oauth(state, auth_code):
            raise RuntimeError("resume_oauth callback to gleam failed")

        # 5) Pull the contestant record using the task_seed from defer_oauth.
        # The X-CSRF-Token header must match the freshly-rotated XSRF-TOKEN cookie.
        new_csrf = self.session.cookies.get("XSRF-TOKEN", domain="gleam.io")
        if new_csrf:
            self.csrf_token = new_csrf
            self.session.headers["X-CSRF-Token"] = new_csrf

        data = self.retrieve_contestant(task_seed=task_seed)
        if not self.cert:
            raise RuntimeError(f"OAuth completed but no cert returned: {data}")

        self._save_cookies()
        return data

    def retrieve_contestant(
        self,
        task_seed: dict = None,
        max_attempts: int = 10,
        poll_interval: float = 0.5,
    ) -> dict:
        """
        Retrieve contestant data after OAuth.

        The endpoint may return 202 (Accepted) while gleam is still exchanging
        the auth_code with X.com server-side. Polls until it returns 201 with
        the contestant payload.

        Args:
            task_seed: backdoor_task_seed dict from defer_oauth response. Required
                for the v5 backdoor flow — supplies task_location + task_signature.
            max_attempts: how many times to poll before giving up
            poll_interval: seconds between polls

        Returns:
            Contestant data with cert, id, name, etc.
        """
        url = f"{BASE_URL}/contestant_backdoor_api/retrieve_value/twitter"
        headers = {"Content-Type": "application/json"}

        if task_seed:
            loc = task_seed.get("task_location")
            if loc:
                url = f"{BASE_URL}{loc}" if loc.startswith("/") else loc
            sig = task_seed.get("task_signature")
            if sig:
                headers["task-signature"] = sig

        last_resp = None
        for _ in range(max_attempts):
            resp = self.session.patch(url, headers=headers, data="null", timeout=15)
            last_resp = resp

            if resp.status_code == 201 and resp.text:
                data = resp.json()
                if data.get("contestant"):
                    self.contestant_data = data["contestant"]
                    self.cert = self.contestant_data.get("cert")
                return data

            if resp.status_code == 202:
                # Still processing the OAuth callback — poll again
                time.sleep(poll_interval)
                continue

            # Anything else is fatal
            resp.raise_for_status()
            break

        raise RuntimeError(
            f"retrieve_contestant exhausted {max_attempts} polls "
            f"(last status: {last_resp.status_code if last_resp else 'n/a'})"
        )

    def register_contestant(self, campaign_key: str, firstname: str, lastname: str, email: str) -> dict:
        """
        Register contestant for a campaign.
        
        Args:
            campaign_key: e.g., "MPPty"
            firstname: First name
            lastname: Last name
            email: Email address
        
        Returns:
            Registration response
        """
        body = {
            "campaign_key": campaign_key,
            "contestant": {
                "firstname": firstname,
                "lastname": lastname,
                "email": email,
                "name": f"{firstname} {lastname}",
                "competition_subscription": None,
            },
            "additional_details": False,
        }
        
        resp = self.session.patch(
            f"{BASE_URL}/queue-contestant/{campaign_key}",
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def claim_contestant(self) -> dict:
        """
        Claim contestant registration.
        
        Returns:
            Updated contestant data
        """
        resp = self.session.patch(
            f"{BASE_URL}/claim-contestant",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("contestant"):
            self.contestant_data = data["contestant"]
            self.cert = self.contestant_data.get("cert")
            self._save_cookies()
        
        return data

    # ──────────────────────────────────────────────
    # Task Completion
    # ──────────────────────────────────────────────

    def compute_task_hash(self, campaign_key: str, entry_method_id: str, entry_type: str) -> str:
        """
        Compute the `h` field for queue-entry submissions.

        Gleam's JS formula (from widget.gleamjs.io):
            md5(["-"+contestant.id, em.id, em.entry_type, campaign.key].join("-"))

        The JS md5 library outputs words in swapped order (see _gleam_md5).
        """
        if not self.contestant_data or not self.contestant_data.get("id"):
            raise RuntimeError("compute_task_hash needs an authenticated contestant (no id)")
        cid = self.contestant_data["id"]
        raw = f"-{cid}-{entry_method_id}-{entry_type}-{campaign_key}"
        return _gleam_md5(raw)

    def _generate_fraud_token(self) -> str:
        """Generate or return the persistent `f` field — `<fraud>.<signed_hash>`.

        Real browsers persist this value in the `fpr` cookie via FingerprintJS
        (cdn.fraudjs.io). Regenerating per request is a strong bot signal and
        invalidates entries via "Invalidated by fraud filter". We instead
        generate once and persist in the jar so subsequent submissions reuse
        the same fingerprint.
        """
        existing = self.session.cookies.get("fpr", domain="gleam.io")
        if existing and "." in existing:
            return existing

        import secrets
        fraud = secrets.token_hex(16)
        token = f"{fraud}.{_gleam_md5(GLEAM_GOOD_STR + fraud)}"
        self.session.cookies.set("fpr", token, domain="gleam.io")
        # Persist immediately so the next process inherits the same fingerprint.
        # Switching fpr across runs is one of gleam's strongest fraud signals.
        try:
            self._save_cookies()
        except Exception:
            pass
        return token

    def complete_task(
        self,
        campaign_key: str,
        entry_method_id: str,
        entry_type: str,
        details=None,
        turnstile_token: str = None,
    ) -> dict:
        """
        Complete a task/entry method.

        Args:
            campaign_key: e.g., "MPPty"
            entry_method_id: e.g., "8324590"
            entry_type: e.g., "twitter_follow" / "custom_action" / "visit_url"
            details: Task-specific details. For twitter_follow this is `{}`;
                for custom_action / visit_url this is the user's answer string.
            turnstile_token: Turnstile captcha token (auto-solved if missing)

        Returns:
            {"status_code", "data", "success", "task_location"}
        """
        if details is None:
            details = {} if entry_type.startswith("twitter_") else ""

        # Try once with the passed-in token (often None — gleam usually accepts
        # null). If gleam returns `error_challenge_failed`, solve Turnstile via
        # CapSolver and retry once with the real token.
        h = self.compute_task_hash(campaign_key, entry_method_id, entry_type)

        det_for_dbg = details if isinstance(details, str) else None
        body = {
            "details": details,
            "h": h,
            "use_hcaptcha": False,
            "use_turnstile": True,
            "challenge_response": turnstile_token,
            "dbg": {
                "eds": {entry_method_id: det_for_dbg},
                "afd": {},
                "efd": {entry_method_id: det_for_dbg} if det_for_dbg is not None else {},
                "car": True,
            },
            "dbge": {
                "eed": "7",
                "hedr": f"2#{entry_method_id}:{det_for_dbg if det_for_dbg is not None else ''}",
                "csefr": "rnull",
                "ae": "re",
                "re": "sed" if det_for_dbg is not None else "scs",
            },
            "stats": self._build_stats(has_input=det_for_dbg is not None),
            "f": self._generate_fraud_token(),
        }

        # Refresh CSRF in case it rotated
        new_csrf = self.session.cookies.get("XSRF-TOKEN", domain="gleam.io")
        if new_csrf and new_csrf != self.csrf_token:
            self.csrf_token = new_csrf
            self.session.headers["X-CSRF-Token"] = new_csrf

        resp = self.session.patch(
            f"{BASE_URL}/queue-entry/{campaign_key}/{entry_method_id}",
            json=body,
            timeout=30,
        )

        task_location = resp.headers.get("task-location")
        data = self._poll_task_location(task_location)

        # If gleam demands a captcha challenge, solve via CapSolver and retry
        # once. Only happens for campaigns/contestants where gleam's Twitter
        # verification cache says "needs captcha" (typically after a failed
        # earlier attempt).
        if (
            isinstance(data, dict)
            and data.get("error_challenge_failed")
            and turnstile_token is None
        ):
            try:
                sitekey = self.get_turnstile_sitekey(campaign_key)
                turnstile_token = self._solve_turnstile(sitekey=sitekey)
            except Exception as e:
                data = {"error_challenge_failed": True, "captcha_error": str(e)}
            else:
                body["challenge_response"] = turnstile_token
                # Refresh stats (simulate captcha-solve interaction time)
                body["stats"] = self._build_stats(has_input=det_for_dbg is not None)
                resp = self.session.patch(
                    f"{BASE_URL}/queue-entry/{campaign_key}/{entry_method_id}",
                    json=body,
                    timeout=30,
                )
                task_location = resp.headers.get("task-location")
                data = self._poll_task_location(task_location)

        worth = data.get("worth", 0) if isinstance(data, dict) else 0
        success = resp.status_code in (200, 202)
        if task_location:
            success = success and worth > 0

        return {
            "status_code": resp.status_code,
            "task_location": task_location,
            "data": data,
            "success": success,
        }

    def _poll_task_location(self, task_location: str) -> dict:
        """Follow a `task-location` header to fetch the access-entry result."""
        if not task_location:
            return {}
        time.sleep(0.6)
        result = self.session.get(f"{BASE_URL}{task_location}", timeout=15)
        if not result.text:
            return {}
        try:
            parsed = result.json()
        except json.JSONDecodeError:
            parsed = result.text[:200]
        return parsed if isinstance(parsed, dict) else {"raw": parsed}

    def complete_task_twitter_follow(
        self,
        campaign_key: str,
        entry_method_id: str,
        twitter_username: str = "",
        turnstile_token: str = None,
    ) -> dict:
        """Complete a Twitter follow task. Gleam verifies via the OAuth-linked
        Twitter account, so `twitter_username` is informational only."""
        return self.complete_task(
            campaign_key, entry_method_id, "twitter_follow", details={}, turnstile_token=turnstile_token,
        )

    def complete_task_twitter_retweet(
        self,
        campaign_key: str,
        entry_method_id: str,
        tweet_url: str = "",
        turnstile_token: str = None,
    ) -> dict:
        """Complete a Twitter retweet task."""
        return self.complete_task(
            campaign_key, entry_method_id, "twitter_retweet", details={}, turnstile_token=turnstile_token,
        )

    def complete_task_twitter_tweet(
        self,
        campaign_key: str,
        entry_method_id: str,
        tweet_text: str = "",
        turnstile_token: str = None,
    ) -> dict:
        """Complete a Twitter tweet task."""
        return self.complete_task(
            campaign_key, entry_method_id, "twitter_tweet", details={}, turnstile_token=turnstile_token,
        )

    def complete_task_visit_url(
        self,
        campaign_key: str,
        entry_method_id: str,
        url: str = "",
        turnstile_token: str = None,
    ) -> dict:
        """Complete a visit URL task."""
        return self.complete_task(
            campaign_key, entry_method_id, "visit_url", details=url, turnstile_token=turnstile_token,
        )

    def complete_task_custom(
        self,
        campaign_key: str,
        entry_method_id: str,
        value: str = "",
        turnstile_token: str = None,
    ) -> dict:
        """Complete a custom_action task. `value` is the user's free-form answer."""
        return self.complete_task(
            campaign_key, entry_method_id, "custom_action", details=value, turnstile_token=turnstile_token,
        )

    # ──────────────────────────────────────────────
    # Bulk Operations
    # ──────────────────────────────────────────────

    def enter_contest(self, campaign_key: str, firstname: str, lastname: str, email: str) -> dict:
        """
        Full contest entry flow: register + claim.
        
        Args:
            campaign_key: e.g., "MPPty"
            firstname: First name
            lastname: Last name
            email: Email address
        
        Returns:
            Registration result
        """
        # Register
        reg_result = self.register_contestant(campaign_key, firstname, lastname, email)
        
        # Claim
        claim_result = self.claim_contestant()
        
        return {
            "registered": bool(reg_result),
            "claimed": bool(claim_result),
            "contestant": self.contestant_data,
        }

    def complete_entry_method(
        self,
        campaign_key: str,
        em: dict,
        value_override: str = None,
        turnstile_token: str = None,
    ) -> dict:
        """
        Decide how to complete one entry method based on its type & metadata,
        then submit it. Shared by `clear_campaign` and the `task` CLI command.

        Resolution order:
          1. value_override (explicit user input) wins for any type
          2. CEX UID tasks → auto-fill from gleam-cex-uids.json
          3. twitter_* → details = {} (gleam verifies via OAuth)
          4. visit_url → use the URL stored on the entry method
          5. fallthrough custom_action with no value → returns a "needs --value" error
        """
        em_id = str(em.get("id", ""))
        em_type = em.get("entry_type", "custom_action")
        em_title = self._entry_method_title(em)
        em_description = em.get("config4") or em.get("config3") or ""

        if value_override is not None:
            return self.complete_task(
                campaign_key, em_id, em_type, details=value_override, turnstile_token=turnstile_token,
            )

        # CEX UID detection
        cex_exchange = self._detect_cex_task(em_title, em_description)
        if cex_exchange:
            uid = self.get_cex_uid(cex_exchange)
            if not uid:
                return {"success": False, "error": f"No UID stored for {cex_exchange}", "data": {}}
            return self.complete_task(
                campaign_key, em_id, em_type, details=uid, turnstile_token=turnstile_token,
            )

        # Twitter actions — empty details, gleam server validates against OAuth
        if em_type.startswith("twitter_"):
            return self.complete_task(
                campaign_key, em_id, em_type, details={}, turnstile_token=turnstile_token,
            )

        # Visit URL — config1 holds the URL to visit
        if em_type == "visit_url":
            url = em.get("config1") or ""
            return self.complete_task(
                campaign_key, em_id, em_type, details=url, turnstile_token=turnstile_token,
            )

        # Custom action with no auto-fillable value
        return {
            "success": False,
            "error": "manual task — pass --value with the answer",
            "data": {},
        }

    def clear_campaign(
        self,
        campaign_key: str,
        firstname: str = "Waguri",
        lastname: str = "Agent",
        email: str = "waguriagent@gmail.com",
        dry_run: bool = False,
    ) -> list:
        """
        Attempt to complete all tasks in a campaign.
        
        Args:
            campaign_key: e.g., "MPPty"
            firstname: First name for registration
            lastname: Last name for registration
            email: Email for registration
            dry_run: If True, only show what would be done
        
        Returns:
            List of results per task
        """
        # Get campaign details
        try:
            campaign = self.get_campaign(campaign_key)
        except Exception as e:
            return [{"error": f"Failed to get campaign: {e}"}]
        
        entry_methods = campaign.get("entry_methods", [])
        results = []
        
        import random
        for idx, em in enumerate(entry_methods):
            em_id = str(em.get("id", ""))
            em_type = em.get("entry_type", "custom")
            em_title = self._entry_method_title(em)
            em_description = em.get("config4") or em.get("config3") or ""

            result = {
                "entry_method_id": em_id,
                "type": em_type,
                "title": em_title,
                "description": em_description,
            }

            if dry_run:
                result["action"] = "dry_run"
                result["auto_completable"] = em_type in [
                    "visit_url", "custom", "twitter_follow", "twitter_retweet",
                    "twitter_tweet", "twitter_like",
                ]
                results.append(result)
                continue

            # Random delay between submissions to look human (skip before first)
            if idx > 0:
                time.sleep(random.uniform(4, 11))

            try:
                task_result = self.complete_entry_method(campaign_key, em)
                result.update(task_result)
            except Exception as e:
                result["success"] = False
                result["error"] = str(e)

            results.append(result)

        return results

    def _extract_twitter_username(self, entry_method: dict) -> str:
        """Extract Twitter username from entry method settings.

        Gleam stores entry-type-specific values in flat numeric config fields
        (config1..config9). For twitter_follow, config1 is the target username.
        """
        username = (
            entry_method.get("config1") or
            entry_method.get("twitter_username") or
            entry_method.get("username") or
            entry_method.get("screen_name") or
            ""
        )

        if not username:
            url = entry_method.get("url", "")
            if "twitter.com/" in url or "x.com/" in url:
                parts = url.split("/")
                for i, part in enumerate(parts):
                    if part in ("twitter.com", "x.com") and i + 1 < len(parts):
                        username = parts[i + 1]
                        break

        return username.lstrip("@")

    def _extract_tweet_url(self, entry_method: dict) -> str:
        """Extract tweet URL from entry method settings.

        For twitter_retweet / twitter_like, config1 holds the tweet URL.
        """
        return (
            entry_method.get("config1") or
            entry_method.get("tweet_url") or
            entry_method.get("url") or
            entry_method.get("status_url") or
            ""
        )

    def _entry_method_title(self, em: dict) -> str:
        """Build a human-readable label for an entry method."""
        em_type = em.get("entry_type", "custom")
        c1 = em.get("config1") or ""
        c3 = em.get("config3") or ""
        c4 = em.get("config4") or ""

        if em_type == "twitter_follow":
            return f"Follow @{c1.lstrip('@')}"
        if em_type == "twitter_retweet":
            return f"Retweet {c1}"
        if em_type == "twitter_tweet":
            return "Tweet"
        if em_type == "twitter_like":
            return f"Like {c1}"
        if em_type == "visit_url":
            return f"Visit {c1}"
        if em_type == "custom_action":
            # config1 is the question; config4 is the longer description
            return (c1 or c4 or "Custom action")[:80]
        return em_type.replace("_", " ").title()

    def _detect_cex_task(self, title: str, description: str) -> str:
        """
        Detect if a task requires a CEX UID.
        
        Args:
            title: Task title
            description: Task description
        
        Returns:
            Exchange name if CEX task, empty string otherwise
        """
        text = f"{title} {description}".lower()
        
        cex_keywords = {
            "kucoin": ["kucoin", "ku coin"],
            "binance": ["binance"],
            "okx": ["okx", "okex"],
            "bybit": ["bybit"],
            "gateio": ["gate.io", "gateio", "gate io"],
            "bitget": ["bitget"],
            "mexc": ["mexc"],
        }
        
        for exchange, keywords in cex_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    # Check if it's a UID task (not just a follow task)
                    if any(x in text for x in ["uid", "user id", "account id", "register", "sign up"]):
                        return exchange
        
        return ""

    # ──────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────

    def get_entry_methods(self, campaign_key: str) -> list:
        """Get all entry methods for a campaign."""
        campaign = self.get_campaign(campaign_key)
        return campaign.get("entry_methods", [])

    def get_prizes(self, campaign_key: str) -> list:
        """Get prizes for a campaign."""
        campaign = self.get_campaign(campaign_key)
        return campaign.get("prizes", [])

    def get_contestant_status(self) -> dict:
        """Get current contestant status."""
        return {
            "authenticated": bool(self.cert),
            "contestant": self.contestant_data,
            "cert": self.cert,
        }
