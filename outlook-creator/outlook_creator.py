#!/usr/bin/env python3
"""
Outlook account creator — hybrid Playwright + API approach.

Playwright: loads signup.live.com, intercepts risk/initialize for continuationToken,
            solves HumanCaptcha natively via PerimeterX WASM,
            handles risk/verify via same-origin XHR on login.microsoftonline.com.
API (curl_cffi): handles CheckAvailableSigninNames, CreateAccount.

Flow (from HAR analysis):
  1. Playwright loads signup.live.com → page JS calls risk/initialize automatically
     → intercept response for continuationToken + extract canary/uaid/px3
  2. API: CheckAvailableSigninNames → check availability + get new apiCanary
  3. Browser: risk/verify #1 via XHR on login.microsoftonline.com → gets HumanCaptcha challenge
  4. Playwright: loads hsprotect.net challenge → PerimeterX solves natively → extract new px3
  5. Browser: risk/verify #2 via XHR → sends new px3 + challengeSolution → gets final continuationToken
  6. API: CreateAccount → creates account

NOTE: risk/verify MUST be called from browser context (same-origin on login.microsoftonline.com).
      curl_cffi calls to risk/verify get 403 riskBlock due to TLS fingerprint mismatch.

Usage:
  python3 outlook_creator.py --count 1
  python3 outlook_creator.py --email custom@outlook.com --password "P@ssw0rd!"
  python3 outlook_creator.py --count 5 --proxy --country us
"""

import argparse
import json
import random
import string
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# curl_cffi for Chrome TLS impersonation
try:
    from curl_cffi import requests as cffi_requests
    _USE_CFFI = True
except ImportError:
    import requests as cffi_requests
    _USE_CFFI = False

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright required: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────

SIGNUP_URL = "https://signup.live.com/signup"
CHECK_API = "https://signup.live.com/API/CheckAvailableSigninNames"
RISK_VERIFY_API = "https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/api/v1.0/risk/verify"
CREATE_API = "https://signup.live.com/API/CreateAccount"

SITE_ID = "00000000487A244A"
HPGID = 200225
SCID = 100118
UIFLVR = 1001

ACCOUNTS_DIR = Path(__file__).parent / "accounts"
PROXIES_ENV = Path(__file__).resolve().parent / ".env"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_proxy_env() -> dict:
    env = {}
    if PROXIES_ENV.exists():
        for line in PROXIES_ENV.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def build_proxy_url(country: str = "") -> str:
    env = _load_proxy_env()
    login = env.get("PROXY_LOGIN", "")
    password = env.get("PROXY_PASSWORD", "")
    host = env.get("PROXY_HOST", "proxy.example.com")
    port = env.get("PROXY_PORT", "823")
    if not login or not password:
        raise RuntimeError("PROXY_LOGIN/PASSWORD not set in proxies.env")
    user = login
    if country:
        user = f"{login}__cr.{country.lower()}"
    session_id = f"outlook_{uuid.uuid4().hex[:8]}"
    user = f"{user}__session_{session_id}"
    return f"http://{user}:{password}@{host}:{port}"


def generate_password(length: int = 14) -> str:
    upper = random.choice(string.ascii_uppercase)
    lower = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special = random.choice("!@#$%^&*")
    rest = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=length - 4))
    pw = list(upper + lower + digit + special + rest)
    random.shuffle(pw)
    return "".join(pw)


def generate_name() -> tuple:
    first_names = [
        "James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph",
        "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Steven", "Paul",
        "Emily", "Emma", "Olivia", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia",
        "Harper", "Evelyn", "Abigail", "Ella", "Elizabeth", "Camila", "Luna", "Sofia",
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas",
        "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Harris",
    ]
    return random.choice(first_names), random.choice(last_names)


def generate_birthdate(min_age: int = 21, max_age: int = 45) -> str:
    today = datetime.now()
    age = random.randint(min_age, max_age)
    birth = today - timedelta(days=age * 365 + random.randint(0, 364))
    return birth.strftime("%d:%m:%Y")


def generate_dot_trick_email(base: str, domain: str = "outlook.com") -> str:
    if "@" in base:
        base, domain = base.split("@", 1)
    chars = list(base)
    positions = random.sample(range(1, len(chars)), min(3, len(chars) - 1))
    for pos in sorted(positions, reverse=True):
        chars.insert(pos, ".")
    return f"{''.join(chars)}@{domain}"


def generate_random_email(domain: str = "outlook.com") -> str:
    adjectives = ["swift", "bright", "cool", "dark", "fast", "wild", "calm", "bold",
                  "keen", "warm", "soft", "deep", "wise", "fair", "pure", "brave"]
    nouns = ["fox", "wolf", "bear", "hawk", "star", "moon", "wave", "fire",
             "wind", "rain", "rock", "tree", "lake", "hill", "bird", "fish"]
    return f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(100, 9999)}@{domain}"


# ── Playwright Browser Session ────────────────────────────────────────────────

class BrowserSession:
    """CloakBrowser via Playwright CDP for PerimeterX captcha + token extraction.

    Connects to CloakBrowser Manager (Docker) instead of launching its own Chromium.
    Benefits: real fingerprint, extensions (Rabby/Phantom), anti-detection patches,
    residential proxy configured at profile level.
    """

    CLOAKBROWSER_MANAGER = "http://127.0.0.1:<CLOAKBROWSER_PORT>"
    CLOAKBROWSER_PROFILE_ID = "<CLOAKBROWSER_PROFILE_ID>"

    def __init__(self, proxy_url: str = ""):
        self.proxy_url = proxy_url
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._initial_px3 = ""

    @property
    def _cdp_url(self) -> str:
        return f"{self.CLOAKBROWSER_MANAGER}/api/profiles/{self.CLOAKBROWSER_PROFILE_ID}/cdp"

    @property
    def _api_url(self) -> str:
        return f"{self.CLOAKBROWSER_MANAGER}/api/profiles/{self.CLOAKBROWSER_PROFILE_ID}"

    def _configure_proxy(self):
        """Set proxy on CloakBrowser profile if it differs from current. Restarts if changed."""
        if not self.proxy_url:
            return
        import httpx
        with httpx.Client() as http:
            resp = http.get(self._api_url, timeout=10)
            current = resp.json().get("proxy", "")
            # Compare without session ID (session ID changes per run)
            if current and self._proxy_base(current) == self._proxy_base(self.proxy_url):
                return  # Same proxy, no restart needed

            print("[cloakbrowser] updating proxy on profile...")
            http.put(self._api_url, json={"proxy": self.proxy_url}, timeout=15)
            http.post(f"{self._api_url}/stop", timeout=15)
            time.sleep(2)
            http.post(f"{self._api_url}/launch", timeout=30)
            for _ in range(10):
                time.sleep(1)
                try:
                    r = http.get(f"{self._api_url}/status", timeout=5)
                    if r.json().get("status") == "running":
                        break
                except Exception:
                    pass
            time.sleep(2)
            # Reset connection state — need to reconnect
            self._page = None
            self._context = None
            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None
            print("[cloakbrowser] proxy configured, profile restarted")

    @staticmethod
    def _proxy_base(url: str) -> str:
        """Strip session ID from proxy URL for comparison."""
        import re
        return re.sub(r'__session_\w+', '', url)

    def _ensure_page(self):
        if self._page is not None and not self._page.is_closed():
            return
        if self._pw is None:
            self._pw = sync_playwright().start()

        # Configure proxy on CloakBrowser profile if provided
        self._configure_proxy()

        # Ensure profile is running
        import httpx
        with httpx.Client() as http:
            resp = http.get(self._api_url, timeout=10)
            profile = resp.json()
            if profile.get("status") != "running":
                print("[cloakbrowser] launching profile...")
                http.post(f"{self._api_url}/launch", timeout=10)
                for _ in range(10):
                    time.sleep(1)
                    try:
                        r = http.get(f"{self._api_url}/status", timeout=5)
                        if r.json().get("status") == "running":
                            break
                    except Exception:
                        pass
                time.sleep(2)

        # Connect Playwright to CloakBrowser via CDP
        print("[cloakbrowser] connecting via CDP...")
        self._browser = self._pw.chromium.connect_over_cdp(self._cdp_url, timeout=30000)
        contexts = self._browser.contexts
        self._context = contexts[0] if contexts else self._browser.new_context()
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        print(f"[cloakbrowser] connected ({len(self._context.pages)} pages)")

    def extract_session_tokens(self) -> dict:
        """
        Load signup.live.com and extract session tokens.
        Intercepts risk/initialize response for continuationToken.
        """
        self._ensure_page()
        print("[browser] loading signup.live.com...")

        # Intercept risk/initialize response to capture continuationToken + cookies
        captured = {}
        risk_init_cookies = {}

        def _on_response(resp):
            if "risk/initialize" in resp.url:
                try:
                    data = resp.json()
                    captured["risk_init"] = data
                except Exception:
                    pass
                # Capture set-cookie headers from risk/initialize (fpc, esctx on login.microsoftonline.com)
                try:
                    arr = resp.headers_array()
                    for h in arr:
                        if h.get("name", "").lower() == "set-cookie":
                            name_val = h.get("value", "").split(";")[0].strip()
                            if "=" in name_val:
                                n, v = name_val.split("=", 1)
                                risk_init_cookies[n.strip()] = v.strip()
                except Exception:
                    pass

        self._page.on("response", _on_response)

        self._page.goto(SIGNUP_URL, wait_until="domcontentloaded", timeout=45000)

        # Poll actively for BOTH risk/initialize (continuationToken) AND the
        # PerimeterX _px3 cookie before proceeding. These fire independently and
        # at different speeds: continuationToken lands ~1.5s, but _px3 is set by the
        # PX sensor on .hsprotect.net a few seconds later (~5s). Breaking on
        # continuationToken alone (the old behaviour) extracted cookies too early
        # and gave "px3 MISSING". Wait for both, with a hard cap.
        ct_wait_total = 30  # seconds
        ct_poll = 0.5
        waited = 0.0
        ct_ok = False
        px_ok = False
        while waited < ct_wait_total:
            self._page.wait_for_timeout(int(ct_poll * 1000))
            waited += ct_poll
            if not ct_ok and captured.get("risk_init", {}).get("continuationToken"):
                ct_ok = True
                print(f"[browser] risk/initialize captured after {waited:.1f}s")
            if not px_ok:
                # _px3 lives on .hsprotect.net — context.cookies() returns all domains
                for c in self._page.context.cookies():
                    if c["name"] == "_px3" and len(c["value"]) > 100:
                        px_ok = True
                        print(f"[browser] _px3 cookie set after {waited:.1f}s")
                        break
            if ct_ok and px_ok:
                break

        if not ct_ok:
            # Fallback: risk/initialize never fired passively. Trigger it manually
            # via same-origin XHR using ServerData fields, mirroring the page JS call.
            print(f"[browser] risk/initialize not captured in {ct_wait_total}s, triggering manually...")
            try:
                manual_ct = self._trigger_risk_initialize()
                if manual_ct:
                    captured["risk_init"] = {"continuationToken": manual_ct}
                    print("[browser] manual risk/initialize OK")
            except Exception as e:
                print(f"[browser] manual risk/initialize failed: {e}")

        if not px_ok:
            print(f"[browser] WARNING: _px3 not set after {ct_wait_total}s — PX sensor may be slow/blocked")

        # Remove listener
        try:
            self._page.remove_listener("response", _on_response)
        except Exception:
            pass

        # Extract from ServerData
        sd = self._page.evaluate("""() => {
            if (typeof ServerData === 'undefined') return {};
            return {
                apiCanary: ServerData.apiCanary || '',
                sUnauthSessionID: ServerData.sUnauthSessionID || '',
                sClientId: ServerData.sClientId || '',
                sCobrandId: ServerData.sCobrandId || '',
                hpgid: ServerData.hpgid || '',
                iUiFlavor: ServerData.iUiFlavor || '',
                iScenarioId: ServerData.iScenarioId || '',
                sHumanAppId: ServerData.sHumanAppId || '',
                urlHumanIframe: ServerData.urlHumanIframe || '',
                arrDomainList: ServerData.arrDomainList || [],
            };
        }""")

        # Extract uaid from cookies
        cookies = {c["name"]: c["value"] for c in self._page.context.cookies()}
        uaid = cookies.get("uaid", sd.get("sUnauthSessionID", ""))

        # Extract continuationToken from intercepted risk/initialize
        continuation_token = ""
        risk_init = captured.get("risk_init", {})
        if risk_init:
            continuation_token = risk_init.get("continuationToken", "")

        # Extract PerimeterX tokens
        px3 = cookies.get("_px3", cookies.get("px3", ""))
        pxde = cookies.get("_pxde", cookies.get("pxde", ""))
        pxvid = cookies.get("_pxvid", cookies.get("pxvid", ""))

        self._initial_px3 = px3

        # Extract all cookies as dict for API session
        all_cookies = {c["name"]: c["value"] for c in self._page.context.cookies()}
        # Merge risk/initialize cookies (fpc, esctx from login.microsoftonline.com)
        all_cookies.update(risk_init_cookies)

        tokens = {
            "canary": sd.get("apiCanary", ""),
            "continuationToken": continuation_token,
            "uaid": uaid,
            "px3": px3,
            "pxde": pxde,
            "pxvid": pxvid,
            "cookies": all_cookies,
            "clientId": sd.get("sClientId", ""),
            "cobrandId": sd.get("sCobrandId", ""),
            "domainList": sd.get("arrDomainList", []),
            "humanAppId": sd.get("sHumanAppId", ""),
            "humanIframeUrl": sd.get("urlHumanIframe", ""),
        }

        print(f"[browser] canary: {'OK' if tokens['canary'] else 'MISSING'} ({len(tokens['canary'])} chars)")
        print(f"[browser] continuationToken: {'OK' if tokens['continuationToken'] else 'MISSING'} ({len(tokens['continuationToken'])} chars)")
        print(f"[browser] uaid: {tokens['uaid'] or 'MISSING'}")
        print(f"[browser] px3: {'OK' if px3 else 'MISSING'} ({len(px3)} chars)")
        print(f"[browser] pxde: {'OK' if pxde else 'MISSING'} ({len(pxde)} chars)")
        print(f"[browser] pxvid: {pxvid or 'MISSING'}")
        print(f"[browser] humanAppId: {tokens['humanAppId']}")

        return tokens

    def _trigger_risk_initialize(self) -> str:
        """
        Manually fire risk/initialize via same-origin XHR (fallback when the page
        JS didn't call it within the polling window — typically on slow proxies).

        Returns the continuationToken string, or "" on failure.

        risk/initialize is a same-origin POST to login.microsoftonline.com under the
        MSA consumer tenant. The page JS calls it on load; we replicate it using
        ServerData fields read from the live signup page.
        """
        self._ensure_page()
        # Must run from the signup.live.com page where ServerData lives.
        if "signup.live.com" not in (self._page.url or ""):
            self._page.goto(SIGNUP_URL, wait_until="domcontentloaded", timeout=45000)
            self._page.wait_for_timeout(2000)

        result = self._page.evaluate("""() => {
            return new Promise((resolve) => {
                let sd = (typeof ServerData !== 'undefined') ? ServerData : {};
                let canary = sd.apiCanary || '';
                let uaid = sd.sUnauthSessionID || '';
                let clientId = sd.sClientId || '';
                // risk/initialize payload mirrors the page JS: it carries the
                // unauthenticated session + client context for MSA risk engine.
                let body = JSON.stringify({
                    clientId: clientId,
                    correlationId: uaid,
                    sessionId: uaid,
                    riskProvider: 'Human',
                });
                const xhr = new XMLHttpRequest();
                xhr.open('POST', 'https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/api/v1.0/risk/initialize', true);
                xhr.withCredentials = true;
                xhr.setRequestHeader('Accept', 'application/json');
                xhr.setRequestHeader('Content-Type', 'application/json; charset=utf-8');
                if (canary) xhr.setRequestHeader('canary', canary);
                if (uaid) { xhr.setRequestHeader('client-request-id', uaid); xhr.setRequestHeader('correlationId', uaid); }
                xhr.onload = function() {
                    try { resolve({status: xhr.status, data: JSON.parse(xhr.responseText)}); }
                    catch(e) { resolve({status: xhr.status, text: xhr.responseText.substring(0, 300)}); }
                };
                xhr.onerror = function() { resolve({error: 'network error'}); };
                xhr.send(body);
            });
        }""")

        if result.get("error"):
            print(f"[browser] risk/initialize XHR error: {result['error']}")
            return ""
        status = result.get("status", 0)
        data = result.get("data", {})
        if status != 200:
            print(f"[browser] risk/initialize HTTP {status}: {json.dumps(data)[:200]}")
            return ""
        return data.get("continuationToken", "")

    def risk_verify_step1(self, tokens: dict, email: str, first_name: str,
                          last_name: str, birthdate: str, country: str,
                          max_retries: int = 3) -> dict:
        """risk/verify #1 via browser XHR (same-origin on login.microsoftonline.com)."""
        print("[browser] risk/verify #1 via XHR...")
        self._ensure_page()

        px3 = tokens.get("px3", "")
        pxde = tokens.get("pxde", "")
        pxvid = tokens.get("pxvid", "")

        payload = {
            "continuationToken": tokens.get("continuationToken", ""),
            "riskProviderMetadata": [{
                "riskProvider": "Human",
                "px3": px3,
                "pxde": pxde,
                "pxvid": pxvid,
            }],
            "msaRiskVerifySignature": {
                "memberName": email,
                "siteId": SITE_ID,
                "uiFlavor": "Web",
                "appId": SITE_ID,
                "birthdate": birthdate,
                "firstName": first_name,
                "lastName": last_name,
                "countryCode": country,
                "verificationCode": "",
                "deviceDetails": {"isRdm": False},
                "action": "SignUp",
            },
        }

        for attempt in range(max_retries):
            # Navigate to login.microsoftonline.com for same-origin XHR
            # (cross-origin XHR from signup.live.com fails — CORS blocked)
            current = self._page.url or ""
            if "login.microsoftonline.com" not in current:
                self._page.goto(
                    "https://login.microsoftonline.com/common/login",
                    wait_until="domcontentloaded", timeout=30000,
                )
                self._page.wait_for_timeout(1000)

            result = self._page.evaluate("""(args) => {
                return new Promise((resolve) => {
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', '/9188040d-6c67-4c5b-b112-36a304b66dad/api/v1.0/risk/verify', true);
                    xhr.setRequestHeader('Accept', 'application/json');
                    xhr.setRequestHeader('Content-Type', 'application/json; charset=utf-8');
                    xhr.setRequestHeader('canary', args.canary);
                    xhr.setRequestHeader('client-request-id', args.uaid);
                    xhr.setRequestHeader('correlationId', args.uaid);
                    xhr.setRequestHeader('hpgact', '0');
                    xhr.setRequestHeader('hpgid', '200225');
                    xhr.onload = function() {
                        try { resolve({status: xhr.status, data: JSON.parse(xhr.responseText)}); }
                        catch(e) { resolve({status: xhr.status, text: xhr.responseText.substring(0, 500)}); }
                    };
                    xhr.onerror = function() { resolve({error: 'XHR failed — CORS or network'}); };
                    xhr.send(args.body);
                });
            }""", {
                "body": json.dumps(payload),
                "canary": tokens.get("canary", ""),
                "uaid": tokens.get("uaid", ""),
            })

            if result.get("error"):
                return {"error": result["error"]}

            status = result.get("status", 0)
            data = result.get("data", {})

            # 403 riskBlock = IP flagged, retry after delay
            if status == 403:
                err_code = data.get("error", {}).get("innerError", {}).get("code", "")
                if err_code == "riskBlock" and attempt < max_retries - 1:
                    delay = 15 * (attempt + 1)
                    print(f"[browser] riskBlock (attempt {attempt+1}/{max_retries}), waiting {delay}s...")
                    time.sleep(delay)
                    # Refresh page for new session
                    self._page.goto(
                        "https://login.microsoftonline.com/common/login",
                        wait_until="domcontentloaded", timeout=30000,
                    )
                    self._page.wait_for_timeout(2000)
                    continue

            if status != 200:
                return {"error": f"risk/verify #1 HTTP {status}: {json.dumps(data)[:200]}"}

            new_ct = data.get("continuationToken", "")
            if new_ct:
                tokens["continuationToken"] = new_ct

            challenge = data.get("challengeDetails", {})
            rv = {"continuationToken": tokens["continuationToken"]}
            if challenge:
                rv["challengeType"] = challenge.get("challengeType", "")
                meta = challenge.get("challengeMetadata", {})
                rv["challengeUrl"] = meta.get("challengeUrl", "")
                print(f"[browser] challenge: {rv['challengeType']}")
            else:
                rv["challengeType"] = ""
                print("[browser] no challenge")
            return rv

        return {"error": f"risk/verify #1 failed after {max_retries} attempts (riskBlock)"}

    def risk_verify_step2(self, tokens: dict, challenge_type: str,
                          captcha_tokens: dict, max_retries: int = 3) -> dict:
        """risk/verify #2 via browser XHR (same-origin on login.microsoftonline.com)."""
        print("[browser] risk/verify #2 via XHR...")
        self._ensure_page()

        px3 = captcha_tokens.get("px3", "")
        pxde = captcha_tokens.get("pxde", "")
        pxvid = captcha_tokens.get("pxvid", "")

        payload = {
            "continuationToken": tokens.get("continuationToken", ""),
            "challengeSolution": {
                "challengeType": challenge_type,
                "px3": px3,
                "pxde": pxde,
                "pxvid": pxvid,
            },
            "riskProviderMetadata": [{
                "riskProvider": "Human",
                "px3": px3,
                "pxde": pxde,
                "pxvid": pxvid,
            }],
        }

        for attempt in range(max_retries):
            # Navigate to login.microsoftonline.com for same-origin XHR
            current = self._page.url or ""
            if "login.microsoftonline.com" not in current:
                self._page.goto(
                    "https://login.microsoftonline.com/common/login",
                    wait_until="domcontentloaded", timeout=30000,
                )
                self._page.wait_for_timeout(1000)

            # NOTE: No cookie injection. PX cookies live on .hsprotect.net only.

            result = self._page.evaluate("""(args) => {
                return new Promise((resolve) => {
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', '/9188040d-6c67-4c5b-b112-36a304b66dad/api/v1.0/risk/verify', true);
                    xhr.setRequestHeader('Accept', 'application/json');
                    xhr.setRequestHeader('Content-Type', 'application/json; charset=utf-8');
                    xhr.setRequestHeader('canary', args.canary);
                    xhr.setRequestHeader('client-request-id', args.uaid);
                    xhr.setRequestHeader('correlationId', args.uaid);
                    xhr.setRequestHeader('hpgact', '0');
                    xhr.setRequestHeader('hpgid', '200225');
                    xhr.onload = function() {
                        try { resolve({status: xhr.status, data: JSON.parse(xhr.responseText)}); }
                        catch(e) { resolve({status: xhr.status, text: xhr.responseText.substring(0, 500)}); }
                    };
                    xhr.onerror = function() { resolve({error: 'network error'}); };
                    xhr.send(args.body);
                });
            }""", {
                "body": json.dumps(payload),
                "canary": tokens.get("canary", ""),
                "uaid": tokens.get("uaid", ""),
            })

            if result.get("error"):
                return {"error": result["error"]}

            status = result.get("status", 0)
            data = result.get("data", {})

            if status == 403:
                err_code = data.get("error", {}).get("innerError", {}).get("code", "")
                if err_code == "riskBlock" and attempt < max_retries - 1:
                    delay = 15 * (attempt + 1)
                    print(f"[browser] riskBlock (attempt {attempt+1}/{max_retries}), waiting {delay}s...")
                    time.sleep(delay)
                    self._page.goto(
                        "https://login.microsoftonline.com/common/login",
                        wait_until="domcontentloaded", timeout=30000,
                    )
                    self._page.wait_for_timeout(2000)
                    continue

            if status != 200:
                return {"error": f"risk/verify #2 HTTP {status}: {json.dumps(data)[:200]}"}

            new_ct = data.get("continuationToken", "")
            if new_ct:
                tokens["continuationToken"] = new_ct
            state = data.get("state", "")
            print(f"[browser] verify #2 full: {json.dumps(data, separators=(',', ':'))[:400]}")
            print(f"[browser] state: {state}")
            result = {"state": state, "continuationToken": tokens["continuationToken"]}
            # Return challenge details if another round needed
            challenge = data.get("challengeDetails", {})
            if challenge:
                challenge_meta = challenge.get("challengeMetadata", {})
                result["challengeType"] = challenge.get("challengeType", "")
                result["challengeUrl"] = challenge_meta.get("challengeUrl", "")
            return result

        return {"error": f"risk/verify #2 failed after {max_retries} attempts (riskBlock)"}

    def solve_human_captcha(self, challenge_url: str) -> dict:
        """Load HumanCaptcha challenge as an IFRAME on the current page.

        The real browser flow loads the PX challenge inside an iframe within the
        Microsoft signup page, NOT as a separate page navigation. Navigating away
        from login.microsoftonline.com breaks session context and triggers
        Microsoft's risk engine (riskChallengeRequired loop).

        This approach:
        1. Stays on login.microsoftonline.com (preserves session context)
        2. Injects challenge_url as an iframe (PX WASM runs natively in the iframe)
        3. Polls .hsprotect.net cookies for _px3 change (PX sensor sets cookies)
        4. Removes the iframe after solve
        """
        print(f"[browser] loading HumanCaptcha challenge (iframe on signup.live.com)...")
        self._ensure_page()

        # Navigate back to signup.live.com — this page has PX sensor JS loaded,
        # which provides the full PX context for the captcha challenge iframe.
        # login.microsoftonline.com (where XHR was sent) doesn't have PX sensor.
        current = self._page.url or ""
        if "signup.live.com" not in current and "login.live.com" not in current:
            self._page.goto(SIGNUP_URL, wait_until="domcontentloaded", timeout=45000)
            self._page.wait_for_timeout(2000)

        # Capture initial _px3 from hsprotect.net domain
        initial_px3 = ""
        try:
            for c in self._page.context.cookies():
                if c["name"] == "_px3":
                    initial_px3 = c["value"]
                    break
        except Exception:
            pass

        # Inject the challenge as an iframe on the current page
        self._page.evaluate(f"""() => {{
            // Remove any existing PX challenge iframe
            const existing = document.getElementById('px-challenge-frame');
            if (existing) existing.remove();
            const iframe = document.createElement('iframe');
            iframe.id = 'px-challenge-frame';
            iframe.src = '{challenge_url}';
            iframe.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:99999;border:none;';
            document.body.appendChild(iframe);
        }}""")
        self._page.wait_for_timeout(2000)

        # Poll for _px3 cookie change on .hsprotect.net
        print("[browser] waiting for PerimeterX solve (up to 90s)...")
        start = time.time()
        new_px3 = ""
        while time.time() - start < 90:
            self._page.wait_for_timeout(3000)
            try:
                for c in self._page.context.cookies():
                    if c["name"] == "_px3" and c["value"] != initial_px3:
                        new_px3 = c["value"]
                        break
            except Exception:
                pass
            if new_px3:
                break
        elapsed = time.time() - start
        print(f"[browser] PerimeterX solve: {elapsed:.1f}s, px3: {'OK' if new_px3 else 'TIMEOUT'}")

        # Remove the challenge iframe
        try:
            self._page.evaluate("""() => {
                const iframe = document.getElementById('px-challenge-frame');
                if (iframe) iframe.remove();
            }""")
        except Exception:
            pass

        # Extract all PX cookies
        result = {"px3": "", "pxde": "", "pxvid": ""}
        try:
            for c in self._page.context.cookies():
                cname = c["name"]
                if cname == "_px3":
                    result["px3"] = c["value"]
                elif cname == "_pxde":
                    result["pxde"] = c["value"]
                elif cname == "_pxvid":
                    result["pxvid"] = c["value"]
        except Exception:
            pass

        if new_px3:
            result["px3"] = new_px3
            print(f"[browser] new px3: OK ({len(new_px3)} chars, first50: {new_px3[:50]})")
            if initial_px3:
                print(f"[browser] initial px3: ({len(initial_px3)} chars, first50: {initial_px3[:50]})")
        else:
            print("[browser] WARNING: no new px3 after 90s")

        return result

    def close(self):
        try:
            # Disconnect Playwright only — do NOT close CloakBrowser profile
            if self._browser is not None:
                self._browser.close()  # disconnect, not stop
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._pw = None
        self._context = None
        self._page = None


# ── API Client ────────────────────────────────────────────────────────────────

class OutlookAPI:
    """Outlook signup API client using curl_cffi for Chrome TLS fingerprinting."""

    def __init__(self, tokens: dict):
        self.uaid = tokens.get("uaid", str(uuid.uuid4()).replace("-", ""))
        self.canary = tokens.get("canary", "")
        self.continuation_token = tokens.get("continuationToken", "")

        if _USE_CFFI:
            self.session = cffi_requests.Session(impersonate="chrome131")
        else:
            self.session = cffi_requests.Session()

        # Import browser cookies into API session (required for Microsoft APIs)
        browser_cookies = tokens.get("cookies", {})
        for name, value in browser_cookies.items():
            self.session.cookies.set(name, value, domain=".live.com")
            self.session.cookies.set(name, value, domain=".login.microsoftonline.com")
        if self.uaid:
            self.session.cookies.set("uaid", self.uaid, domain="signup.live.com")

        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Referer": SIGNUP_URL,
            "User-Agent": UA,
            "canary": self.canary,
            "client-request-id": self.uaid,
            "correlationId": self.uaid,
            "hpgact": "0",
            "hpgid": str(HPGID),
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

        self.name_change_count = 0
        self.available_count = 0
        self.unavailable_count = 0

    def _update_canary(self, data: dict):
        new = data.get("apiCanary", "")
        if new:
            self.canary = new
            self.headers["canary"] = new

    def check_email(self, email: str) -> dict:
        print(f"[api] checking availability: {email}")
        payload = {
            "includeSuggestions": True,
            "signInName": email,
            "uiflvr": UIFLVR,
            "scid": SCID,
            "uaid": self.uaid,
            "hpgid": HPGID,
        }
        resp = self.session.post(CHECK_API, json=payload, headers=self.headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self._update_canary(data)
        self.name_change_count += 1
        available = data.get("isAvailable", False)
        if available:
            self.available_count += 1
        else:
            self.unavailable_count += 1
        return {
            "isAvailable": available,
            "suggestions": data.get("suggestions", []),
            "type": data.get("type", ""),
        }

    def risk_verify_step1(self, email, first_name, last_name, birthdate, country,
                          px3, pxde, pxvid) -> dict:
        print("[api] risk/verify #1...")
        payload = {
            "continuationToken": self.continuation_token,
            "riskProviderMetadata": [{
                "riskProvider": "Human",
                "px3": px3,
                "pxde": pxde,
                "pxvid": pxvid,
            }],
            "msaRiskVerifySignature": {
                "memberName": email,
                "siteId": SITE_ID,
                "uiFlavor": "Web",
                "appId": SITE_ID,
                "birthdate": birthdate,
                "firstName": first_name,
                "lastName": last_name,
                "countryCode": country,
                "verificationCode": "",
                "deviceDetails": {"isRdm": False},
                "action": "SignUp",
            },
        }
        resp = self.session.post(RISK_VERIFY_API, json=payload, headers=self.headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self._update_canary(data)
        new_ct = data.get("continuationToken", "")
        if new_ct:
            self.continuation_token = new_ct
        result = {"continuationToken": self.continuation_token}
        challenge = data.get("challengeDetails", {})
        if challenge:
            result["challengeType"] = challenge.get("challengeType", "")
            meta = challenge.get("challengeMetadata", {})
            result["challengeUrl"] = meta.get("challengeUrl", "")
            print(f"[api] challenge: {result['challengeType']}")
        else:
            result["challengeType"] = ""
            print("[api] no challenge")
        return result

    def risk_verify_step2(self, challenge_type, px3, pxde, pxvid) -> dict:
        print("[api] risk/verify #2...")
        payload = {
            "continuationToken": self.continuation_token,
            "challengeSolution": {
                "challengeType": challenge_type,
                "px3": px3,
                "pxde": pxde,
                "pxvid": pxvid,
            },
            "riskProviderMetadata": [{
                "riskProvider": "Human",
                "px3": px3,
                "pxde": pxde,
                "pxvid": pxvid,
            }],
        }
        resp = self.session.post(RISK_VERIFY_API, json=payload, headers=self.headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self._update_canary(data)
        new_ct = data.get("continuationToken", "")
        if new_ct:
            self.continuation_token = new_ct
        state = data.get("state", "")
        print(f"[api] state: {state}")
        return {"state": state, "continuationToken": self.continuation_token}

    def create_account(self, email, password, first_name, last_name, birthdate, country) -> dict:
        print(f"[api] creating account: {email}")
        uaid = self.uaid
        sru = (
            "https%3a%2f%2flogin.live.com%2foauth20_authorize.srf%3flc%3d1033"
            "%26client_id%3d9199bf20-a13f-4107-85dc-02114787ef48"
            "%26cobrandid%3dab0455a0-8d03-46b9-b18b-df2f57b9e44c"
            "%26mkt%3dEN-US"
            f"%26uaid%3d{uaid}"
            "%26opignore%3d1"
        )
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{random.randint(100, 999)}Z"
        payload = {
            "BirthDate": birthdate,
            "CheckAvailStateMap": [f"{email}:false"],
            "Country": country,
            "EvictionWarningShown": [],
            "FirstName": first_name,
            "IsRDM": False,
            "IsOptOutEmailDefault": False,
            "IsOptOutEmailShown": 1,
            "IsOptOutEmail": False,
            "IsUserConsentedToChinaPIPL": False,
            "LastName": last_name,
            "LW": 1,
            "MemberName": email,
            "RequestTimeStamp": now,
            "ReturnUrl": "",
            "SignupReturnUrl": sru,
            "SuggestedAccountType": "OUTLOOK",
            "SiteId": "",
            "VerificationCodeSlt": "",
            "PrivateAccessToken": "",
            "WReply": "",
            "MemberNameChangeCount": self.name_change_count,
            "MemberNameAvailableCount": self.available_count,
            "MemberNameUnavailableCount": self.unavailable_count,
            "Password": password,
            "ContinuationToken": self.continuation_token,
            "uiflvr": UIFLVR,
            "scid": SCID,
            "uaid": uaid,
            "hpgid": HPGID,
        }
        resp = self.session.post(CREATE_API, json=payload, headers=self.headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "signinName": data.get("signinName", email),
            "slt": data.get("slt", ""),
            "encPuid": data.get("encPuid", ""),
            "redirectUrl": data.get("redirectUrl", ""),
            "error": data.get("error", {}),
        }


# ── Orchestrator ──────────────────────────────────────────────────────────────

def _create_temp_profile(proxy_url: str = "") -> str:
    """Create a fresh CloakBrowser profile for isolated session."""
    import httpx
    payload = {
        "name": f"OutlookTemp-{uuid.uuid4().hex[:8]}",
        "launch_args": [],
        "humanize": True,
        "headless": False,
    }
    if proxy_url:
        payload["proxy"] = proxy_url
    with httpx.Client() as http:
        resp = http.post(
            f"{BrowserSession.CLOAKBROWSER_MANAGER}/api/profiles",
            json=payload, timeout=15,
        )
        resp.raise_for_status()
        pid = resp.json()["id"]
        http.post(
            f"{BrowserSession.CLOAKBROWSER_MANAGER}/api/profiles/{pid}/launch",
            timeout=30,
        )
        # Wait for profile to be running
        for _ in range(15):
            time.sleep(1)
            try:
                r = http.get(
                    f"{BrowserSession.CLOAKBROWSER_MANAGER}/api/profiles/{pid}/status",
                    timeout=5,
                )
                if r.json().get("status") == "running":
                    break
            except Exception:
                pass
        time.sleep(2)
        return pid


def _delete_temp_profile(profile_id: str):
    """Stop and delete a temporary CloakBrowser profile."""
    import httpx
    try:
        with httpx.Client() as http:
            http.post(
                f"{BrowserSession.CLOAKBROWSER_MANAGER}/api/profiles/{profile_id}/stop",
                timeout=10,
            )
            http.delete(
                f"{BrowserSession.CLOAKBROWSER_MANAGER}/api/profiles/{profile_id}",
                timeout=10,
            )
    except Exception:
        pass


def create_account(email="", password="", first_name="", last_name="",
                   birthdate="", country="US", proxy_url="", base_email="") -> dict:
    if not first_name or not last_name:
        first_name, last_name = generate_name()
    if not password:
        password = generate_password()
    if not birthdate:
        birthdate = generate_birthdate()
    if not email:
        email = generate_dot_trick_email(base_email) if base_email else generate_random_email()

    print(f"\n{'='*60}")
    print(f"Creating: {email}")
    print(f"Name: {first_name} {last_name} | Country: {country}")
    print(f"{'='*60}")

    browser = None
    temp_profile_id = None
    try:
        # Create fresh CloakBrowser profile per attempt (clean pxvid/uaid)
        temp_profile_id = _create_temp_profile(proxy_url)
        print(f"[cloakbrowser] temp profile: {temp_profile_id}")

        class TempBrowser(BrowserSession):
            CLOAKBROWSER_PROFILE_ID = temp_profile_id

        # Phase 1: Browser — extract session tokens
        print("\n[Phase 1] Browser — extracting session tokens...")
        browser = TempBrowser()
        tokens = browser.extract_session_tokens()

        if not tokens.get("canary"):
            return {"error": "Failed to extract canary", "email": email}
        if not tokens.get("continuationToken"):
            return {"error": "Failed to extract continuationToken (risk/initialize not intercepted)", "email": email}

        # Phase 2: API — check email (retry up to 10 times if taken with no suggestions)
        print("\n[Phase 2] API — checking email...")
        api = OutlookAPI(tokens)
        max_retries = 10
        for attempt in range(max_retries):
            check = api.check_email(email)
            if check["isAvailable"]:
                break
            suggestions = check.get("suggestions", [])
            if suggestions:
                email = suggestions[0]
                print(f"[info] using suggestion: {email}")
                api.check_email(email)
                break
            # No suggestions — generate new email and retry
            if attempt < max_retries - 1:
                old = email
                email = generate_dot_trick_email(base_email) if base_email else generate_random_email()
                print(f"[info] {old} taken, retrying with: {email}")
            else:
                return {"error": f"Email not available after {max_retries} attempts", "email": email}

        # Phase 3: Browser — risk/verify #1 (same-origin XHR on login.microsoftonline.com)
        print("\n[Phase 3] Browser — risk/verify #1...")
        rv1 = browser.risk_verify_step1(
            tokens=tokens, email=email, first_name=first_name,
            last_name=last_name, birthdate=birthdate, country=country,
        )
        if rv1.get("error"):
            return {"error": rv1["error"], "email": email}

        # Phase 3+4+5: risk/verify → captcha solve loop
        captcha_tokens = {
            "px3": tokens.get("px3", ""),
            "pxde": tokens.get("pxde", ""),
            "pxvid": tokens.get("pxvid", ""),
        }

        if rv1.get("challengeType") == "HumanCaptcha" and rv1.get("challengeUrl"):
            # Captcha solve loop — may need multiple rounds
            max_captcha_rounds = 5
            current_challenge_url = rv1["challengeUrl"]

            for captcha_round in range(max_captcha_rounds):
                print(f"\n[Phase 4.{captcha_round+1}] Browser — solving HumanCaptcha...")
                captcha_tokens = browser.solve_human_captcha(current_challenge_url)
                if not captcha_tokens.get("px3"):
                    return {"error": "HumanCaptcha solve failed — no px3", "email": email}

                print(f"\n[Phase 5.{captcha_round+1}] Browser — risk/verify...")
                rv2 = browser.risk_verify_step2(
                    tokens=tokens, challenge_type="HumanCaptcha",
                    captcha_tokens=captcha_tokens,
                )
                if rv2.get("error"):
                    return {"error": rv2["error"], "email": email}

                if rv2.get("state") == "continue":
                    print("[Phase 5] risk/verify passed!")
                    break

                # Another challenge? Loop again
                if rv2.get("challengeUrl"):
                    current_challenge_url = rv2["challengeUrl"]
                    print(f"[Phase 5] Another challenge, solving again...")
                    continue

                # Unknown state
                return {"error": f"risk/verify state: {rv2.get('state')}", "email": email}
            else:
                return {"error": f"Captcha not solved after {max_captcha_rounds} rounds", "email": email}
        else:
            print("\n[Phase 4] Skipped — no challenge")

        # Phase 6: API — CreateAccount (continuationToken updated by browser risk/verify)
        print("\n[Phase 6] API — creating account...")
        api.continuation_token = tokens.get("continuationToken", api.continuation_token)
        result = api.create_account(
            email=email, password=password, first_name=first_name,
            last_name=last_name, birthdate=birthdate, country=country,
        )
        if result.get("error"):
            return {"error": result["error"], "email": email}

        account = {
            "email": result.get("signinName", email),
            "password": password,
            "firstName": first_name,
            "lastName": last_name,
            "birthdate": birthdate,
            "country": country,
            "slt": result.get("slt", ""),
            "encPuid": result.get("encPuid", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"\n[SUCCESS] {account['email']}")
        return account

    except Exception as e:
        return {"error": str(e), "email": email}
    finally:
        if browser:
            browser.close()
        if temp_profile_id:
            _delete_temp_profile(temp_profile_id)


def save_account(account: dict):
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = account.get("email", "unknown").split("@")[0]
    filename = ACCOUNTS_DIR / f"{name}_{ts}.json"
    with open(filename, "w") as f:
        json.dump(account, f, indent=2)
    print(f"[saved] {filename}")
    master = ACCOUNTS_DIR / "all_accounts.json"
    existing = []
    if master.exists():
        try:
            existing = json.loads(master.read_text())
        except Exception:
            existing = []
    existing.append(account)
    master.write_text(json.dumps(existing, indent=2))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Outlook account creator (Playwright + API)")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--email", type=str)
    parser.add_argument("--base-email", type=str)
    parser.add_argument("--password", type=str)
    parser.add_argument("--country", type=str, default="US")
    parser.add_argument("--proxy", action="store_true")
    parser.add_argument("--proxy-country", type=str)
    parser.add_argument("--delay", type=int, default=10)
    args = parser.parse_args()

    proxy_url = ""
    if args.proxy:
        pc = args.proxy_country or args.country
        proxy_url = build_proxy_url(pc)
        print(f"[proxy] {pc}: {proxy_url[:50]}...")

    results = []
    for i in range(args.count):
        if i > 0:
            d = args.delay + random.randint(0, 5)
            print(f"\n[delay] {d}s...")
            time.sleep(d)
            if args.proxy:
                proxy_url = build_proxy_url(args.proxy_country or args.country)

        account = create_account(
            email=args.email if args.count == 1 else "",
            password=args.password,
            country=args.country,
            proxy_url=proxy_url,
            base_email=args.base_email,
        )

        if "error" not in account:
            save_account(account)
        else:
            print(f"\n[FAILED] {account.get('email', '?')}: {account['error']}")
        results.append(account)

    success = sum(1 for r in results if "error" not in r)
    print(f"\n{'='*60}")
    print(f"Results: {success}/{args.count} created")
    print(f"{'='*60}")
    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
