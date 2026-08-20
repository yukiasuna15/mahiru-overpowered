# gleam-client

Headless Python client for [Gleam.io](https://gleam.io) giveaways. Handles the
Twitter OAuth flow, contestant registration, and task completion entirely over
HTTP — no browser, no Selenium, no Camoufox.

## Features

- **No-browser Twitter OAuth** — completes the `/i/api/2/oauth2/authorize`
  XHR flow directly using your X.com session cookies.
- **Full task completion** — replicates the `h` hash and `f` fraud token that
  Gleam's `/queue-entry` endpoint expects.
- **Auto-detection** — twitter_follow uses OAuth verification, CEX UID
  prompts auto-fill from a JSON file, visit_url reads the URL from the entry
  method, and manual tasks fall back to a `--value` flag.
- **Lazy Turnstile solving** — submits with `challenge_response: null` first;
  if gleam returns `error_challenge_failed`, transparently solves via
  CapSolver (~5 s) and retries once.
- **Per-campaign sitekey auto-detection** — scrapes the campaign page for the
  embedded Turnstile `0x4...` sitekey and caches it, so gleam can rotate keys
  without breaking the solver.
- **Fraud-filter mitigation** — persists `fpr` cookie across runs, sends
  growing interaction stats, and paces task submissions so entries are
  marked **Valid** in the campaign panel (verified end-to-end).
- **Session persistence** — gleam cookies, contestant cert, and `fpr` are all
  cached under `~/.hermes/credentials/gleam-cookies.json`.

## Prerequisites

| File                                         | Purpose                                           | Required for                                              |
| -------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------- |
| `~/.hermes/credentials/x-cookies.json`       | X.com session cookies (`auth_token`, `ct0`, etc.)         | `oauth` command                                           |
| `~/.hermes/credentials/gleam-cookies.json`   | Cached gleam session + contestant cert                    | auto-created after `oauth`                                |
| `~/.hermes/credentials/gleam-cex-uids.json`  | UIDs per exchange for CEX prompts                         | optional, only for CEX UID tasks                          |
| `~/.hermes/credentials/captcha-provider.env` | `CAPTCHA_CAPSOLVER_API_KEY=...` for Turnstile solving     | only when gleam demands a captcha challenge (auto-retry)  |

### Exporting X cookies

Open `https://x.com` while logged in → DevTools → Application → Cookies → copy
all cookies for `.x.com` into a JSON dict:

```json
{
  "auth_token": "...",
  "ct0": "...",
  "guest_id": "...",
  "twid": "...",
  "_twitter_sess": "..."
}
```

`auth_token` and `ct0` are mandatory; the rest are helpful for anti-bot
fingerprinting but not strictly required.

### CEX UIDs file

```json
{
  "kucoin": "123456789",
  "binance": "987654321",
  "okx": "111222333",
  "bybit": "444555666",
  "gateio": "777888999",
  "bitget": "000111222",
  "mexc": "333444555"
}
```

## CLI usage

The CLI lives in `gleam-cli.py` and uses the virtualenv at
`/home/galkurta/.hermes/hermes-agent/venv/bin/python3`.

### Authenticate (one-time per session)

```bash
./gleam-cli.py oauth MPPty
```

This runs the full OAuth flow:

1. `GET /csrf` → fresh CSRF token
2. `POST /defer_oauth/twitter` → backdoor authorize URL + task seed
3. `POST /permit_access/twitter`
4. `GET/POST x.com/i/api/2/oauth2/authorize` → auth code (uses X cookies)
5. `GET /contestant_backdoor/resume_oauth/twitter?code=...` → mints cert
6. `PATCH /retrieve_value/twitter` (polled) → contestant payload

Cert + cookies are persisted, so subsequent runs use the cache.

### Inspect campaign

```bash
./gleam-cli.py campaign MPPty            # name + state + entry methods
./gleam-cli.py entries MPPty             # entry methods with worth
./gleam-cli.py me                        # show signed-in contestant
```

### Complete tasks

```bash
# Clear every task in a campaign (auto-resolves what each task needs)
./gleam-cli.py clear MPPty
./gleam-cli.py clear MPPty --dry-run     # preview only

# Complete one task — auto-detects type and value
./gleam-cli.py task MPPty 8324590        # twitter_follow → uses OAuth
./gleam-cli.py task MPPty 8324593        # "Submit your KuCoin UID" → autofills

# Manual answer needed (custom_action with no auto-fillable hint)
./gleam-cli.py task MPPty 8324592 --value "https://twitter.com/me/status/123..."
```

### When `--value` is required

| Task type                                                                   | `--value` needed?                           |
| --------------------------------------------------------------------------- | ------------------------------------------- |
| `twitter_follow` / `twitter_retweet` / `twitter_like` / `twitter_tweet`     | No — Gleam verifies via OAuth               |
| `visit_url`                                                                 | No — URL stored on the entry method         |
| `custom_action` matching CEX UID keywords (`kucoin`, `binance`, `okx`, ...) | No — auto-filled from `gleam-cex-uids.json` |
| Other `custom_action` (free-form answers, tweet URLs to verify)             | **Yes**                                     |

## Library usage

```python
from gleam import GleamClient

client = GleamClient()

# Twitter OAuth (only needed once until session expires)
if not client.cert:
    client.oauth_twitter("MPPty", entry_method_id="8324590")

# Inspect campaign
campaign = client.get_campaign("MPPty")
for em in campaign["entry_methods"]:
    print(em["id"], em["entry_type"], em["config1"])

# Complete one task with auto-detection
em = next(m for m in campaign["entry_methods"] if m["id"] == "8324590")
result = client.complete_entry_method("MPPty", em)
# → {"status_code": 202, "task_location": "/access-entry/...",
#    "data": {"id": ..., "worth": 1, ...}, "success": True}

# Complete a manual custom_action
client.complete_entry_method(
    "MPPty",
    em_custom,
    value_override="https://twitter.com/me/status/123...",
)

# Or call lower-level helpers directly
client.complete_task_twitter_follow("MPPty", "8324590")
client.complete_task_custom("MPPty", "8324593", value="123456789")

# Solve Turnstile manually with the right per-campaign sitekey
sitekey = client.get_turnstile_sitekey("MPPty")    # auto-detect + cache
token = client._solve_turnstile(sitekey=sitekey)   # via CapSolver
client.complete_task_twitter_follow("MPPty", "8324590", turnstile_token=token)
```

## How the protocol works

### OAuth (`oauth_twitter`)

Gleam's flow looks browser-only because of the OAuth2 PKCE redirect, but the
"approve" button on `x.com/i/oauth2/authorize` is really two XHR calls:

```
GET  https://x.com/i/api/2/oauth2/authorize?client_id=...&code_challenge=...
     Headers: Bearer <public web token>, x-csrf-token: <ct0>, Cookie: auth_token=...; ct0=...
     → {"auth_code": "..."}

POST https://x.com/i/api/2/oauth2/authorize
     Body: approval=true&code=<auth_code>
     → 200
```

The redirect-page anti-bot only fires on the HTML page (`/i/oauth2/authorize`),
not on the API endpoint (`/i/api/2/oauth2/authorize`). With valid X cookies,
this is a regular authenticated request.

### Task hash (`h`)

From `widget.gleamjs.io`:

```js
md5([-contestant.id, em.id, em.entry_type, campaign.key].join("-"));
```

Gleam's JS MD5 lib outputs 32-bit words pairwise-swapped — the standard hex
`AAAA BBBB CCCC DDDD` becomes `BBBB AAAA DDDD CCCC`. `_gleam_md5()` replicates
this.

### Fraud token (`f`)

`f = "<random 32-hex>.<gleam_md5(goodStr + random)>"` where
`goodStr = "5e\`i|XV;>w6DtqPZ'"`(decoded from`intsToStr([53,101,96,...])`
in the widget JS).

### Submission lifecycle

```
PATCH /queue-entry/<campaign_key>/<em_id>
  Body: {details, h, f, dbg, dbge, stats, use_turnstile, challenge_response}
  → 202 Accepted
  Response header: task-location: /access-entry/<uuid>

GET /access-entry/<uuid>
  → 201 {"id": ..., "worth": 1, ...}    # worth > 0 = credited
```

### Fraud filter & Turnstile

Gleam injects an external bot detector from `cdn.fraudjs.io` (FingerprintJS
based) and stores its output in the `fpr` cookie. Server-side, gleam scores
each submission and tags suspicious ones **Invalidated by fraud filter**
asynchronously — the API still returns `worth: 1` but the entry doesn't
count toward the campaign.

The client defeats this by:

1. **Persisting `fpr`** in the cookie jar and on disk. Real browsers keep one
   fingerprint per device; rotating it per request is the strongest bot
   signal. We generate once in `_generate_fraud_token` and reuse.
2. **Growing `stats`** — `m`/`c`/`k` are session-cumulative mouse/click/key
   counts. `ml`/`cl`/`kl` are the deltas since the previous submission and
   `i` is the submission index. `_build_stats()` produces realistic values.
3. **Random 4–11 s pause** between submissions in `clear_campaign`.
4. **Lazy Turnstile**: first attempt sends `challenge_response: null`. On
   `error_challenge_failed`, the client calls CapSolver with the campaign's
   auto-detected sitekey (`get_turnstile_sitekey`) and resubmits.

## File layout

```
gleam-client/
├── gleam.py            # GleamClient — library
├── gleam-cli.py        # CLI wrapper
└── README.md
```

## Notes

- `clear_campaign` only re-runs uncompleted tasks server-side; already-credited
  tasks return `worth: 0` but won't double-credit you.
- The X bearer token (`AAAA…CpTnA`) is X.com's public web bearer — same value
  for every user. It's not an API key you need to obtain.
- Gleam rotates the `XSRF-TOKEN` cookie on most responses; `complete_task`
  re-syncs the `X-CSRF-Token` header from the jar before each submission.
- The Cloudflare bot challenge fires on cold sessions. The client warms up by
  calling `/csrf` first, which sets `__cf_bm` and allows subsequent requests.
- **Gleam caches Twitter verification per (contestant, entry_method).** A
  failed first attempt (e.g., submitting before following on Twitter) flips
  that entry into "needs captcha" mode for that contestant. After completing
  the Twitter action, just resubmit; the auto-retry will solve and credit you.
- **If entries are still marked Invalid after the fixes**, the contestant may
  already be tagged in gleam's history. Try a fresh X.com account — `fpr` is
  per-contestant and a clean session usually clears the slate.
- **Force-skip the solver** by passing `turnstile_token=""` (or any non-`None`
  value) to `complete_task`. Useful when you know null will be accepted and
  want to avoid CapSolver cost.
