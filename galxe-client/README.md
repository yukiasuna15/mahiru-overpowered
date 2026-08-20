# Galxe Client

Python client for automating Galxe: SIWE (sign-in-with-Ethereum) auth, a rich
read API (campaigns, spaces, raffles, savings, …), quest completion, captcha
generation, and on-chain reward claims.

## Files

- **`galxe.py`** — the library: all GraphQL API calls, SIWE `login`, WASM captcha,
  quest completion, and on-chain claim logic. Import it directly for scripting.
- **`galxe-cli.py`** — the CLI wrapping `galxe.py`.

Everything is **synchronous**.

## ⚠️ Captcha: Galxe no longer uses GeeTest

Galxe dropped GeeTest v4. The captcha payload is now built client-side by an
in-house **Rust→WASM** module shipped in the Galxe frontend
(`app.galxe.com/_next/static/media/wasm_lib_bg.*.wasm`). The old GraphQL field
names are kept, but the values are computed by Galxe's own code:

```
lotNumber     = sha256(apiName)        # e.g. sha256("PrepareParticipate")
passToken     = sha256(genTime)
genTime       = unix seconds
captchaOutput = wasm.generate_data(...).geetest_encrypted   # the real proof
```

**CapSolver / 2Captcha / GeeTest solvers no longer work** — they return a real
GeeTest token, which Galxe rejects with `"lotNumber is invalid"`. We instead run
Galxe's own JS in a **headless browser (Playwright, sync API)** and call the
builder directly. The token is **not IP-bound**, so the browser needs no proxy.
See `solve_geetest_captcha()` / `_WasmCaptcha` in `galxe.py`.

## Requirements

- Python 3.11+
- `curl_cffi`, `eth_account`, `web3`, `playwright`
- Chromium for Playwright: `python -m playwright install chromium`
- `twikit` + `telethon` — for the integrated Twitter/Telegram automation (see below)

## Credentials

| File | Contents |
|------|----------|
| `~/wallet/.env` | `WALLET_EVM_STANDALONE_PRIVATE_KEY=0x...` (for `login` + on-chain claims) |
| `~/.hermes/credentials/galxe-credentials.json` | JWT token + address, auto-saved by `login` |

> CapSolver / `captcha-provider.env` is **no longer needed** (removed).

## CLI usage

```bash
python galxe-cli.py login                      # SIWE sign-in → save JWT
python galxe-cli.py info                       # account info
python galxe-cli.py explore --limit 10         # list active campaigns
python galxe-cli.py campaign <id>              # campaign detail
python galxe-cli.py space --alias <alias>      # space info
python galxe-cli.py quest-status <id>          # creds eligibility + claim section
python galxe-cli.py complete <id>              # complete a quest's auto-tasks
python galxe-cli.py claim <id>                 # claim/enter on-chain (auto-detects points / NFT / ZK_RAFFLE)
python galxe-cli.py complete-and-claim <id>    # complete then claim
# also: space-campaigns, follow, participations, raffle, notifications,
#       airdrops, savings, quest-creds
```

### Integrated social automation (Twitter / Telegram)

`complete` performs the real social actions automatically — it imports the helper
tools directly (no subprocess) and does the action before syncing the credential:

- **Twitter follow/like/RT** → `/home/ubuntu/scripts/x-client` (twikit; creds:
  `~/.hermes/credentials/x-cookies.json`, `x-credentials.env`). `_complete_credential`
  parses the cred's `intent/...?screen_name=`/`tweet_id=` link and calls
  `x-client`'s `follow`/`like`/`retweet`. Galxe genuinely verifies follow/RT.
- **Telegram joins** → `/home/ubuntu/scripts/telegram-userbot` (telethon; session:
  `~/.hermes/credentials/telegram-userbot.session`). Parses the `t.me/<channel>`
  link and calls `groups.join_group`.
- **Discord membership** → join manually (no automation).

Requires the helper dirs + their creds present, and the **same** X/Telegram account
linked to the Galxe account. (`galxe.py` runs them via `asyncio.run`; `twikit` and
`telethon` must be installed in the runtime venv.)

## Library usage

```python
import galxe
galxe.login()                                  # SIWE → saves token
print(galxe.user_info()["username"])
galxe.list_campaigns(first=10, statuses=["Active"])
galxe.complete_and_claim("GCMiCtYmzU")         # complete tasks + on-chain claim
```

### How claiming works

`claim_quest` auto-detects the reward type and routes accordingly:

- **Loyalty points (Gravity)** — captcha → `prepareParticipate` →
  `increasePoint(lpContract, verifyID, account, points*1e18, claimFee, signature)`
  with `msg.value = claimFee` → confirm. Galxe charges a **claim fee**
  (`CHARGE_CLAIM_FEE_VERSION`, ~14.88 G per claim, paid in native G — "Gasless"
  only means the space sponsors gas, not the fee).
- **NFT/OAT** — captcha → `prepareParticipate` → SpaceStation `claim`/`claimCapped`
  → `participate` confirm.
- **ZK_RAFFLE** (`type: "Token"` or `"LuckBasedToken"`) — *entered* (not claimed),
  see `enter_zk_raffle`: captcha → `prepareParticipate` (reward chain) → **on-chain
  tx on Gravity** to the raffle contract (`eth_call`-checked first) → `Participate`
  on `GRAVITY_ALPHA`. Costs ~0.1 G gas; **no BNB** (the reward chain, e.g. BSC/MATIC,
  is separate). `Token` uses `tokenRewardCampaignTxResp.verifyID`; `LuckBasedToken`
  uses `luckBasedTokenCampaignTxResp.dummyId` — same on-chain fn. The reward only
  arrives if you win, drawn later (winner-claim not yet implemented).
- **Parent campaigns** (`type: "Parent"`) hold no tasks themselves — claim each
  **child** campaign individually.
- **Member creds** (`JOIN_TELEGRAM`, `DISCORD_MEMBER`): linking the account to
  Galxe is *not* enough — you must actually be a member of the specific
  channel/server; then completion happens via `sync_credential` +
  `verify_credentials`. `CAMPAIGN_REFERRAL` can't be automated.

## Auto-completable task types

`complete` fully handles: **space-follow, visit-link, watch-YouTube, multiple-choice
quiz** (brute-forced), **Twitter follow/like/RT/quote** (via x-client), and **Telegram
join** (via telegram-userbot). **Discord membership** must be joined manually (then
`complete` syncs it).

Not automatable: **`TWITTER_USER`** ("X Account Requirement" — a passive gate on
account age/followers/etc.; eligible only if the account already qualifies),
**surveys**, and **referrals** (CAMPAIGN_REFERRAL). Note: `TWITTER_QUOTE` *posts a
public quote-tweet* — implemented, but it's real content on your account.

## Changelog — 2026-05-29

- **Captcha rewrite (root cause).** Galxe migrated GeeTest v4 → in-house WASM;
  the old GeeTest `captcha_id` (`244bcb8b…`) is retired (HTTP 410 Gone). Replaced
  all paid solvers with a Playwright WASM generator (`_WasmCaptcha`). Verified for
  `PrepareParticipate`, `AddTypedCredentialItems`, `SyncCredentialValue`.
- **On-chain claim fixes.** Loyalty claim uses `increasePoint(...)` with
  `points*1e18` and the fee as `msg.value` (the old `claim(...)` reverted;
  verified via `eth_call`). `mintCount` = NFT count (0 for points, else the input
  default of 1 → "Invalid main reward gas config"). `allow` is read from
  `loyaltyPointsTxResp.allow` (top-level is always false for points).
  `participate*` now send `tx`/`nonce`/`verifyIDs`. web3 7.x: `w3.eth.gas_price`
  is a property.
- **Consolidated to 2 files.** Folded the former `galxe_auto.py` (SIWE login +
  quest-completion automation) into `galxe.py` (sync) and exposed it via
  `galxe-cli.py` (`login`, `complete`, `complete-and-claim`). Deleted
  `galxe_auto.py`. The rich read API of `galxe.py` is preserved.
- **Telegram/Discord member sync.** `sync_credential` no longer sends a nested
  `telegram`/`discord` object (Galxe returns HTTP 422); membership is verified
  via `verify_credentials` after a plain `{address, credId}` sync.
- **ZK_RAFFLE entry** (`enter_zk_raffle`). Token raffles (`distributionType:
  ZK_RAFFLE`) are *entered* (not claimed) by an **on-chain tx on Gravity**:
  `prepareParticipate` (reward chain, e.g. BSC/MATIC) → on-chain call to the raffle
  contract (= `prepareParticipate.spaceStation`) on Gravity —
  `participate(uint256 numberID, address account, uint256 verifyID, bytes
  signature)`, selector `0xc8cbf5e3` — → `Participate` mutation on `GRAVITY_ALPHA`
  with the tx hash. **No BNB needed**: the user signs the Gravity tx and pays
  ~0.1 G gas (the reward chain is separate). `claim`/`claim_quest` auto-route
  `Token` **and** `LuckBasedToken` campaigns here (the latter uses
  `luckBasedTokenCampaignTxResp.dummyId` in place of `verifyID`; same on-chain fn).
  Pre-flight `eth_call` to avoid wasting gas on reverts. **Verified live end-to-end**
  (SonicSVM `GCYX1tZxtn` USDC/MATIC, and MagVerseAI `GCCCwtZBEK` LuckBasedToken).
- **Twitter actions via x-client** (`/home/ubuntu/scripts/x-client`, twikit):
  run the x-client to perform follow/like/RT, then `complete` syncs+verifies them
  (Galxe genuinely verifies follow/RT).
- **Space-follow fix.** `_follow_space_and_sync` now fetches the space `id` itself
  (`quest_claim_section`'s `space` lacks `id`, so SPACE_FOLLOWER creds silently
  weren't being followed).
- **Integrated social automation.** `complete` now performs the real Twitter
  (follow/like/RT) and Telegram (join) actions itself by importing the x-client
  (twikit) and telegram-userbot (telethon) modules directly — no more manual
  pre-step / subprocess. The async actions run in a **dedicated thread** (`_run_coro`)
  because Playwright's sync-API captcha keeps an event loop running in the main
  thread, which breaks `asyncio.run()`. (x-client's `users`/`tweets` do
  `from auth import …`, so its dir goes on `sys.path`; telegram-userbot is loaded by
  file path. `telethon` installed into the venv.) Verified end-to-end on KiiChain
  `GCSvxtZ2YC`: `complete` did follow+like+RT from zero, then entered the raffle.
- **Quote-tweets + delayed re-verify.** `TWITTER_QUOTE` now posts a real quote
  (`create_tweet(text, attachment_url)`). And since Galxe's Twitter verification
  lags ~1 min (a quote/RT can read `eligible=0` if checked immediately), `complete`
  now **re-verifies the still-pending social creds** (up to 3× with 25 s waits) —
  `TWITTER_USER` is excluded so it doesn't waste the wait. `TWITTER_USER` itself no
  longer errors (it's a passive gate — skipped, not sent to `add_cred_items`).

## Not yet supported

- **Token-reward winner claim** (`TokenRaffleWon` after winning a raffle) —
  separate on-chain flow from entry; not implemented.

## API Endpoints

- GraphQL: `https://graphigo.prd.galaxy.eco/query`
- Gravity RPC: `https://rpc.gravity.xyz`
