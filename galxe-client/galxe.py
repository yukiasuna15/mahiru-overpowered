#!/usr/bin/env python3
"""Galxe GraphQL API client. Auto-loads JWT from ~/.hermes/credentials/galxe-credentials.json."""

import json
import os
import time
import uuid
from pathlib import Path

# Use curl_cffi for proper TLS fingerprinting (Chrome impersonation)
# Galxe rejects requests without Chrome TLS pattern
try:
    from curl_cffi import requests as cffi_requests
    _USE_CFFI = True
except ImportError:
    import requests as cffi_requests
    _USE_CFFI = False

CREDENTIALS_FILE = os.path.expanduser("~/.hermes/credentials/galxe-credentials.json")
GALXE_API = "https://graphigo.prd.galaxy.eco/query"
SAVINGS_API = "https://savings-graphigo.prd.latch.io/query"

CAMPAIGN_TYPES = [
    "Airdrop", "Bounty", "DiscordRole", "Drop", "ExternalLink", "Forge",
    "LuckBasedToken", "Mintlist", "MysteryBox", "MysteryBoxWR", "Oat",
    "OptIn", "OptInEmail", "Parent", "Points", "PointsMysteryBox",
    "PowahDrop", "Token"
]


def _load_token() -> str:
    with open(CREDENTIALS_FILE) as f:
        return json.load(f).get("access_token", "")


def _headers(token: str) -> dict:
    return {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "authorization": token,
        "origin": "https://app.galxe.com",
        "referer": "https://app.galxe.com/",
        "request-id": str(uuid.uuid4()),
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }


def gql(query: str, variables: dict = None, token: str = None, api: str = GALXE_API) -> dict:
    token = token or _load_token()
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    kwargs = {"headers": _headers(token), "json": payload, "timeout": 30}
    if _USE_CFFI:
        kwargs["impersonate"] = "chrome131"
    r = cffi_requests.post(api, **kwargs)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL errors: {json.dumps(data['errors'], ensure_ascii=False)}")
    return data.get("data", {})


# ============================================================
# USER INFO
# ============================================================

Q_GALXE_ID_EXIST = 'query($s:String!){galxeIdExist(schema:$s)}'

Q_BASIC_USER_INFO = """query($a:String!){addressInfo(address:$a){
  id username avatar address
  spacesFollowing{totalCount}
  userLevel{level{name logo minExp maxExp value}exp gold ggRecall}
  userXPLevel{level levelName validXP minRequiredXP maxRequiredXP logo}
  ggInviteCode ggInviter{id username}
  isBot hasEmail
  solanaAddress hasTwitter hasGithub hasDiscord hasTelegram
  displayEmail displayTwitter displayGithub displayDiscord displayTelegram
  twitterUserName discordUserName
  email
}}"""


def galxe_id_exist(address: str, token: str = None) -> bool:
    schema = address if address.startswith("EVM:") else f"EVM:{address}"
    return gql(Q_GALXE_ID_EXIST, {"s": schema}, token).get("galxeIdExist", False)


def user_info(token: str = None) -> dict:
    """Get comprehensive user info (username, level, XP, linked accounts, etc.)."""
    addr = _get_address(token)
    return gql(Q_BASIC_USER_INFO, {"a": addr}, token).get("addressInfo", {})


# ============================================================
# CAMPAIGNS
# ============================================================

Q_CAMPAIGN_LIST = """query($ci:ListCampaignInput!){
  campaigns(input:$ci){totalCount pageInfo{endCursor hasNextPage}
  list{id numberID name status type startTime endTime description thumbnail cap gasType
    chain rewardInfo{premint{price chain}discordRole{guildName roleName}}
    space{id alias name thumbnail}
    participants{participantsCount bountyWinnersCount}
    tokenReward{tokenAddress tokenSymbol tokenDecimal userTokenAmount}
    rewardName
  }}
}"""

Q_CAMPAIGN_DETAIL = """query($id:String!,$addr:String!){
  campaign(id:$id){
    id numberID name status type description thumbnail startTime endTime cap gasType chain
    formula rewardName isPrivate loyaltyPoints
    advancedSybilPrevention
    rewardInfo{
      premint{price chain}
      discordRole{guildName roleName}
      luckBasedToken{totalAmount userAvailableMaxAmount tokenAddress tokenDecimal tokenSymbol}
    }
    space{id alias name thumbnail}
    participants{participantsCount bountyWinnersCount}
    tokenReward{tokenAddress tokenSymbol tokenDecimal userTokenAmount}
    tokenRewardContract{id chain address}
    allowAddresses{list}
    childrenQuests{id name status type numberID}
    credential{id type name description}
    quests{id name type credential{id type}rewardType}
  }
}"""

Q_BROWSE_SPACE_CAMPAIGNS = """query($id:Int,$alias:String,$addr:String!,$ci:ListCampaignInput!){
  space(id:$id,alias:$alias){
    id name alias
    campaigns(input:$ci){pageInfo{endCursor hasNextPage}
    list{id type status name description thumbnail startTime cap gasType chain
      rewardName formula isPrivate loyaltyPoints advancedSybilPrevention
      boost(address:$addr){golden}
      whitelistInfo(address:$addr){usedCount}
      space{id alias name thumbnail}
      participants{participantsCount bountyWinnersCount}
      rewardInfo{premint{price chain}discordRole{guildName roleName}
        luckBasedToken{totalAmount userAvailableMaxAmount tokenAddress tokenDecimal tokenSymbol}
      }
      tokenReward{tokenAddress tokenSymbol tokenDecimal userTokenAmount}
    }}
  }
}"""

Q_RECOMMEND_CAMPAIGNS = """query($input:ListCampaignInput!,$addr:String){
  campaigns(input:$input){totalCount pageInfo{endCursor hasNextPage}
  list{id numberID name status type startTime endTime thumbnail cap chain
    rewardName distributionType
    space{id alias name thumbnail isVerified}
  }}
}"""

Q_CAMPAIGN_PROMO_SLOTS = """query($input:CampaignPromotionSlotsInput!){
  campaignPromotionSlots(input:$input){
    campaign{id thumbnail rewardName type name numberID cap status}
  }
}"""


def list_campaigns(address: str = None, first: int = 20, after: str = "-1",
                    types: list = None, statuses: list = None, token: str = None) -> dict:
    address = address or _get_address(token)
    ci = {"first": first, "after": after}
    if types:
        ci["types"] = types
    if statuses:
        ci["statuses"] = statuses
    return gql(Q_CAMPAIGN_LIST, {"ci": ci}, token).get("campaigns", {})


def get_campaign(campaign_id: str, token: str = None) -> dict:
    addr = _get_address(token)
    return gql(Q_CAMPAIGN_DETAIL, {"id": campaign_id, "addr": addr}, token).get("campaign", {})


def browse_space_campaigns(alias: str = None, space_id: int = None,
                            first: int = 20, after: str = "-1",
                            token: str = None) -> dict:
    """List campaigns for a specific space/project."""
    addr = _get_address(token)
    ci = {
        "first": first, "after": after,
        "excludeChildren": True, "forAdmin": False,
        "listTrendingWithoutFilter": True, "listType": "Trending",
        "types": CAMPAIGN_TYPES,
    }
    vars = {"addr": addr, "ci": ci}
    if alias:
        vars["alias"] = alias
    if space_id:
        vars["id"] = space_id
    return gql(Q_BROWSE_SPACE_CAMPAIGNS, vars, token).get("space", {})


def recommend_campaigns(user_id: str = None, campaign_id: str = None,
                         first: int = 12, after: str = "-1",
                         token: str = None) -> dict:
    """Get recommended campaigns based on user/campaign."""
    ci = {"first": first, "after": after}
    if user_id:
        ci["recommendByUser"] = user_id
    if campaign_id:
        ci["recommendByCampaignId"] = campaign_id
    return gql(Q_RECOMMEND_CAMPAIGNS, {"input": ci}, token).get("campaigns", {})


# ============================================================
# SPACE / PROJECT
# ============================================================

Q_SPACE_INFO = """query($id:Int,$alias:String){
  space(id:$id,alias:$alias){
    id name alias followersCount
  }
}"""

Q_SPACE_IS_ADMIN = """query($id:Int,$alias:String,$addr:String!){
  space(id:$id,alias:$alias){isAdmin(address:$addr)}
}"""

Q_FOLLOW_SPACE = 'mutation($ids:[Int!]){followSpace(spaceIds:$ids)}'


def get_space(alias: str = None, space_id: int = None, token: str = None) -> dict:
    vars = {}
    if alias:
        vars["alias"] = alias
    if space_id:
        vars["id"] = space_id
    return gql(Q_SPACE_INFO, vars, token).get("space", {})


def follow_space(space_ids: list, token: str = None) -> int:
    """Follow one or more spaces. Returns count of followed."""
    return gql(Q_FOLLOW_SPACE, {"ids": space_ids}, token).get("followSpace", 0)


def space_is_admin(alias: str = None, space_id: int = None, token: str = None) -> bool:
    addr = _get_address(token)
    vars = {"addr": addr}
    if alias:
        vars["alias"] = alias
    if space_id:
        vars["id"] = space_id
    return gql(Q_SPACE_IS_ADMIN, vars, token).get("space", {}).get("isAdmin", False)


# ============================================================
# PARTICIPATION & CLAIM
# ============================================================

Q_RECENT_PARTICIPATION = """query($addr:String!,$pi:ListParticipationInput!){
  addressInfo(address:$addr){
    recentParticipation(input:$pi){list{
      id chain tx createdAt nftId status
      nftCore{contractAddress}
      campaign{id name space{id alias}}
    }}
  }
}"""


def recent_participation(address: str = None, first: int = 30, token: str = None) -> list:
    address = address or _get_address(token)
    addr = address if address.startswith("EVM:") else f"EVM:{address}"
    pi = {"first": first, "onlyGasless": False, "onlyVerified": False}
    data = gql(Q_RECENT_PARTICIPATION, {"addr": addr, "pi": pi}, token)
    return data.get("addressInfo", {}).get("recentParticipation", {}).get("list", [])


# ============================================================
# NOTIFICATIONS
# ============================================================

Q_NOTIFICATIONS = """query($addr:String!,$input:GetUserNotificationsRequest!){
  addressInfo(address:$addr){
    userNotifications(input:$input){notifications{
      id category title description url image status createdAt
    }total}
  }
}"""


def notifications(limit: int = 30, token: str = None) -> dict:
    addr = _get_address(token)
    return gql(Q_NOTIFICATIONS, {"addr": addr, "input": {"limit": limit}}, token).get(
        "addressInfo", {}).get("userNotifications", {})


# ============================================================
# GG RAFFLE
# ============================================================

Q_GG_RAFFLE_INFO = """query{
  getLatestGGRaffleQuestInfo{questInfo{
    roundId raffleQuestId isActive chain tokenId tokenType
    raffleContract rewardContract totalAmount totalProbability
    rate grandCount smallCount luckyGrand
    startAt endAt buyEndAt claimEndAt participateCount
    tokenDetail{tokenSymbol tokenDecimal id chain tokenAddress tokenLogo}
    rateFire
  }}
}"""

Q_GG_RAFFLE_HISTORY = """query($req:ListUserGGRaffleResultsHistoryRequest!){
  listUserGGRaffleResultsHistory(request:$req){resultsInfo{
    id hashId questId ticketId ticketNum address
    claimAmount claimStatus tx rewardType createAt updateAt
    GGRaffleQuestInfo{tokenDetail{tokenSymbol tokenDecimal id chain tokenAddress tokenLogo}claimEndAt}
  }}
}"""


def gg_raffle_info(token: str = None) -> dict:
    return gql(Q_GG_RAFFLE_INFO, {}, token).get("getLatestGGRaffleQuestInfo", {}).get("questInfo", {})


def gg_raffle_history(offset: int = 0, limit: int = 10, rtype: str = "ToClaim", token: str = None) -> list:
    req = {"offset": offset, "limit": limit, "type": rtype}
    return gql(Q_GG_RAFFLE_HISTORY, {"req": req}, token).get(
        "listUserGGRaffleResultsHistory", {}).get("resultsInfo", []) or []


# ============================================================
# EARN DROPS & AIRDROPS
# ============================================================

Q_EARNDROP_LIST = """query($id:Int){
  space(id:$id){earndrops{
    id space{id name thumbnail isVerified}
    alias name
    tokenInfo{symbol icon decimals}
    stages{earndropId}
    statData{totalParticipants totalClaimedAmount totalAmount}
  }}
}"""

Q_CHECK_AIRDROP = """query($input:Int64!){
  airdropCampaigns(input:{first:50,after:"-1",spaceId:$input}){
    list{id name status}
  }
}"""


def space_earndrops(space_id: int, token: str = None) -> list:
    return gql(Q_EARNDROP_LIST, {"id": space_id}, token).get("space", {}).get("earndrops", [])


def check_airdrop(space_id: int, token: str = None) -> list:
    return gql(Q_CHECK_AIRDROP, {"input": space_id}, token).get(
        "airdropCampaigns", {}).get("list", []) or []


# ============================================================
# STAR BOARDS & WATCH LIST
# ============================================================

Q_STAR_BOARDS = """query($input:StarboardsInput!){
  starboards(input:$input){name id tags participants isPrivate
    reward{name}space{id name alias thumbnail isVerified}
  }
}"""

Q_RECOMMEND_WATCHLIST = "query{recommendWatchList{watchList{id name}}}"


def star_boards(space_id: int, token: str = None) -> list:
    return gql(Q_STAR_BOARDS, {"input": {"spaceId": str(space_id), "isDefaultStarboard": False}}, token).get(
        "starboards", [])


# ============================================================
# USER SUBSCRIPTION & SETTINGS
# ============================================================

Q_PLUS_SUBSCRIPTION = """query{
  userPlusSubscription{active currentPlanType currentPaymentCycle expiresAt beginsAt}
}"""

Q_PLUS_TRIAL = "query($id:String){userPlusTrialCards(queryGalxeId:$id){planType}}"

Q_SETTINGS = "query{settings{basicSettings}}"

Q_SMART_RANK = "query{smartRankUserInfo{abGroup userTag}}"

Q_IS_LSD_HOLDER = "query{isLsdTokenHolder}"

Q_GLOBAL_BANNER = "query{webObjects(input:{categories:ANNOUNCEMENT,first:10,after:\"-1\"}){description}}"

Q_WHITELIST_SITES = "query{whitelistSites{name url}}"


def plus_subscription(token: str = None) -> dict:
    return gql(Q_PLUS_SUBSCRIPTION, {}, token).get("userPlusSubscription", {})


def smart_rank_info(token: str = None) -> dict:
    return gql(Q_SMART_RANK, {}, token).get("smartRankUserInfo", {})


def global_banner(token: str = None) -> list:
    return gql(Q_GLOBAL_BANNER, {}, token).get("webObjects", [])


def whitelist_sites(token: str = None) -> list:
    return gql(Q_WHITELIST_SITES, {}, token).get("whitelistSites", [])


# ============================================================
# SAVINGS API (LSD/DeFi)
# ============================================================

Q_SAVINGS_BALANCE = """query($addr:String!){
  GetBalance(address:$addr){token{chainId addr symbol icon decimal}
    availableAmount pendingAmount totalAmount
  }
}"""

Q_SAVINGS_EXCHANGE_RATE = """query($tokens:[TokenInput!]!){
  GetExchangeRate(tokens:$tokens){token{chainId addr}exchangeRate}
}"""

Q_SAVINGS_PROFIT = """query($addr:String!){
  totalProfit:GetLSDTotalProfit(address:$addr){totalProfit}
  yesterdayProfit:GetLSDYesterdayProfit(address:$addr){yesterdayProfit}
}"""

Q_SAVINGS_STAKED = """query($addr:String!){
  GetIsStaked(address:$addr)
  GetDepositPendingBalance(address:$addr){balance}
}"""

Q_SAVINGS_VAULT = """query($lsd:String!){
  apy:GetAPYs(lsdToken:$lsd)
  apyPast7Days:GetAPYs(lsdToken:$lsd,days:7)
}"""


def savings_balance(address: str = None, token: str = None) -> list:
    address = address or _get_address(token).replace("EVM:", "").lower()
    return gql(Q_SAVINGS_BALANCE, {"addr": address}, token, SAVINGS_API).get("GetBalance", [])


def savings_profit(address: str = None, token: str = None) -> dict:
    address = address or _get_address(token).replace("EVM:", "").lower()
    return gql(Q_SAVINGS_PROFIT, {"addr": address}, token, SAVINGS_API)


# ============================================================

# ============================================================
# CREDENTIAL & VERIFICATION
# ============================================================

Q_QUEST_CRED_LIST = """query($id:ID!,$addr:String!){
  campaign(id:$id){id endTime space{alias id name thumbnail}
    recurringType latestRecurringTime
    taskConfig(address:$addr){
      participateCondition{conditions{...EE}conditionalFormula eligible verifyBeforeTasks}
      rewardConfigs{id conditions{...EE}conditionalFormula description
        rewards{...ER}eligible
        rewardAttrVals{attrName attrTitle attrVal}
      }
      referralConfig{id conditions{...EE}conditionalFormula description
        rewards{...ER}eligible
        rewardAttrVals{attrName attrTitle attrVal}
      }
    }
    referralCode(address:$addr)
  }
}
fragment ER on ExprReward{arithmetics{...EE}arithmeticFormula rewardType rewardCount rewardVal}
fragment EE on ExprEntity{cred{
  id name credType credSource dimensionConfig referenceLink description
  lastUpdate lastSync chain
  curatorSpace{id name thumbnail}
  eligible(address:$addr)
  metadata{twitter{isAuthentic}worldcoin{dimensions{values{value}}}
    starboard{dimensions{id title description}}
    discord{discordAma{LinkIsInvalid}discordMember{LinkIsInvalid}discordMessage{LinkIsInvalid}}
    prediction{options{option isCorrect chosenCount}deadlineForVoting deadlineForReveal rule}
  }
  commonInfo{participateEndTime modificationInfo}
}attrs{attrName operatorSymbol targetValue}attrFormula eligible eligibleAddress}"""

M_SYNC_CRED = """mutation($input:SyncCredentialValueInput!){
  syncCredentialValue(input:$input){value{
    address spaceUsers{follow points participations}
    campaignReferral{count}galxePassport{eligible lastSelfieTimestamp}
    spacePoint{points}spaceParticipation{participations}
    gitcoinPassport{score lastScoreTimestamp}walletBalance{balance}
    multiDimension{value}allow survey{answers}quiz{allow correct}
    prediction{isCorrect}spaceFollower{follow}timeWindowCount{count}
  }message}
}"""

M_ADD_CRED_ITEMS = """mutation($input:MutateTypedCredItemInput!){
  typedCredentialItems(input:$input){id}
}"""

Q_QUEST_CLAIM_SECTION = """query($id:ID!,$addr:String!,$withAddr:Boolean!,$isParent:Boolean=false){
  campaign(id:$id){
    id numberID type chain status distributionType startTime endTime claimEndTime
    cap recurringType loyaltyPoints rewardName rewardType gasType
    boost(address:$addr){golden boost boostedGold reason}
    numNFTMinted
    participants @skip(if:$isParent){participantsCount}
    userParticipants(address:$addr,first:1) @include(if:$withAddr){list{status}}
    name description userAgreement
    airdrop{rewardType rewardAmount
      rewardInfo{custom{name icon}token{address decimals symbol icon}}
      claimDetail(address:$addr){amount}
    }
    space{isFollowing @include(if:$withAddr)isVerified}
    inWatchList advancedSybilPrevention
    whitelistInfo(address:$addr){address maxCount usedCount
      claimedLoyaltyPoints currentPeriodClaimedLoyaltyPoints currentPeriodMaxLoyaltyPoints xrplLinks
    }
    taskConfig(address:$addr){
      rewardConfigs{id conditions{...EE}conditionalFormula description
        rewards{...ER}eligible
        rewardAttrVals{attrName attrTitle attrVal}
      }
      requiredInfo{
        socialInfos{email discordUserID twitterUserID telegramUserID githubUserID googleUserID worldcoinID}
        addressInfos{address evmAddressSecondary solanaAddress aptosAddress seiAddress injectiveAddress flowAddress starknetAddress suiAddress bitcoinAddress stacksAddress azeroAddress archwayAddress xrplAddress bitcoinSignetAddress tonAddress algorandAddress kadenaAddress}
      }
    }
    nftCore{id contractAddress chain transferable createdAt}
    tokenReward{userTokenAmount tokenAddress depositedTokenAmount tokenRewardContract tokenDecimal tokenLogo tokenSymbol raffleContractAddress}
    spaceStation{address}
  }
}
fragment ER on ExprReward{arithmetics{...EE}arithmeticFormula rewardType rewardCount rewardVal}
fragment EE on ExprEntity{cred{
  id name credType credSource dimensionConfig referenceLink description
  lastUpdate lastSync chain
  curatorSpace{id name thumbnail}
  eligible(address:$addr)
  commonInfo{participateEndTime modificationInfo}
}attrs{attrName operatorSymbol targetValue}attrFormula eligible eligibleAddress}"""

M_PREPARE_PARTICIPATE = """mutation($input:PrepareParticipateInput!){
  prepareParticipate(input:$input){
    allow disallowReason signature nonce
    spaceStationInfo{address chain version}
    mintFuncInfo{funcName nftCoreAddress verifyIDs powahs cap claimFeeAmount}
    loyaltyPointsTxResp{TotalClaimedPoints VerifyIDs
      loyaltyPointDistributionStation signature disallowReason nonce
      allow loyaltyPointContract Points reqQueueing claimFeeAmount
    }
    tokenRewardCampaignTxResp{signatureExpiredAt verifyID encodeAddress weight claimFeeAmount}
    airdropRewardCampaignTxResp{airdropID verifyID index account amount proof customReward}
    luckBasedTokenCampaignTxResp{cid dummyId expiredAt claimTo index claimAmount proof claimFeeAmount signature encodeAddress weight}
    spaceStationProxyResp{target callData}
    spaceStation
  }
}"""

M_REGISTER_SS_PAYMENT = """mutation($input:RegisterSSPaymentTaskInput!){
  registerSSPaymentTask(input:$input){taskId success failureReason}
}"""

Q_PAYMENT_TASK_INFO = "query($id:Int64!){paymentTaskInfo(taskID:$id){status}}"

Q_PARTICIPATION_INFO = """query($ids:[ID!]!,$lp:Boolean){
  participations(id:$ids,isLoyaltyPoint:$lp){id tx status chain}
}"""

Q_ESTIMATE_COST = """query($input:EstimateQuestCostDetailInput!){
  estimateQuestCostDetail(input:$input){
    totalCost{amount usd chain}
    totalCostAfterDeductingCredits{amount usd chain}
    totalClaimFee{amount usd chain}
    totalServiceFee{amount usd chain}
    transactionFee{claimFee{amount usd chain}gasFee{amount usd chain}serviceFee{amount usd chain}chain mintType}
  }
}"""

M_PARTICIPATE = """mutation($input:ParticipateInput!){
  participate(input:$input){participated failReason}
}"""

M_PARTICIPATE_POINT = """mutation($input:ParticipatePointInput!){
  participatePoint(input:$input){participated failReason}
}"""


def participate(campaign_id: str, chain: str, nonce, tx_hash: str,
                verify_id, token: str = None) -> dict:
    """Confirm an NFT/Drop claim AFTER the on-chain tx (see execute_onchain_claim)."""
    addr = _get_address(token)
    inp = {"address": addr, "campaignID": campaign_id, "chain": chain,
           "nonce": nonce, "signature": "", "tx": tx_hash, "verifyIDs": [verify_id]}
    res = gql(M_PARTICIPATE, {"input": inp}, token).get("participate", {})
    if not res.get("participated"):
        raise RuntimeError(f"Participate failed: {res}")
    return res


def participate_point(campaign_id: str, nonce, tx_hash: str, verify_ids: list,
                       chain: str = "GRAVITY_ALPHA", token: str = None) -> dict:
    """Confirm a loyalty-points claim AFTER the on-chain tx (see execute_onchain_claim)."""
    addr = _get_address(token)
    inp = {"address": addr, "campaignID": campaign_id, "chain": chain,
           "nonce": nonce, "signature": "", "tx": tx_hash, "verifyIDs": verify_ids}
    res = gql(M_PARTICIPATE_POINT, {"input": inp}, token).get("participatePoint", {})
    if not res.get("participated"):
        raise RuntimeError(f"ParticipatePoint failed: {res.get('failReason', res)}")
    return res


# ============================================================
# ON-CHAIN CLAIM  (Gravity loyalty points / NFT space station)
# ============================================================

WALLET_ENV = os.path.expanduser("~/wallet/.env")

_CHAIN_RPCS = {
    "Ethereum": "https://eth.llamarpc.com",
    "Polygon": "https://polygon-rpc.com",
    "BSC": "https://bsc-dataseed1.binance.org",
    "Arbitrum": "https://arb1.arbitrum.io/rpc",
    "Optimism": "https://mainnet.optimism.io",
    "Base": "https://mainnet.base.org",
    "Avalanche": "https://api.avax.network/ext/bc/C/rpc",
    "GRAVITY_ALPHA": "https://rpc.gravity.xyz",
    "Gravity": "https://rpc.gravity.xyz",
}

# SpaceStation ABI (NFT claim) — minimal.
SPACE_STATION_ABI = [
    {"inputs": [
        {"name": "cid", "type": "uint256"}, {"name": "signature", "type": "bytes"},
        {"name": "nftCoreAddress", "type": "address"}, {"name": "verifyID", "type": "uint256"},
        {"name": "powah", "type": "uint256"}],
     "name": "claim", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [
        {"name": "cid", "type": "uint256"}, {"name": "signature", "type": "bytes"},
        {"name": "nftCoreAddress", "type": "address"}, {"name": "verifyID", "type": "uint256"},
        {"name": "powah", "type": "uint256"}, {"name": "cap", "type": "uint256"}],
     "name": "claimCapped", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]

# LoyaltyPoints distribution-station ABI — increasePoint(lpContract, verifyID,
# account, amount, claimFee, signature); amount = points*1e18, fee paid as value.
LOYALTY_POINTS_ABI = [
    {"inputs": [
        {"name": "loyaltyPointContract", "type": "address"}, {"name": "verifyID", "type": "uint256"},
        {"name": "account", "type": "address"}, {"name": "amount", "type": "uint256"},
        {"name": "claimFeeAmount", "type": "uint256"}, {"name": "signature", "type": "bytes"}],
     "name": "increasePoint", "outputs": [], "stateMutability": "payable", "type": "function"},
]


def _load_private_key() -> str:
    if not os.path.exists(WALLET_ENV):
        raise RuntimeError(f"Wallet env not found: {WALLET_ENV}")
    with open(WALLET_ENV) as f:
        for line in f:
            line = line.strip()
            if line.startswith("WALLET_EVM_STANDALONE_PRIVATE_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("WALLET_EVM_STANDALONE_PRIVATE_KEY not found in wallet/.env")


def execute_onchain_claim(claim_data: dict, chain: str = "GRAVITY_ALPHA",
                          number_id: int = 0) -> str:
    """Execute the on-chain claim tx for a prepareParticipate result; return tx hash.

    Loyalty points -> increasePoint(lpContract, verifyID, account, points*1e18,
    claimFee, signature) with value=claimFee. NFT -> SpaceStation claim/claimCapped
    (pass number_id = campaign numberID).
    """
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware

    rpc_url = _CHAIN_RPCS.get(chain)
    if not rpc_url:
        raise RuntimeError(f"No RPC configured for chain: {chain}")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if chain in ("Polygon", "BSC", "Avalanche", "Base", "GRAVITY_ALPHA", "Gravity"):
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    pk = _load_private_key()
    account = w3.eth.account.from_key(pk)
    nonce = w3.eth.get_transaction_count(account.address)

    lp_resp = claim_data.get("loyaltyPointsTxResp") or {}
    mint_func = claim_data.get("mintFuncInfo") or {}
    ss_info = claim_data.get("spaceStationInfo") or {}

    if lp_resp and lp_resp.get("loyaltyPointContract") and lp_resp.get("allow"):
        station = w3.to_checksum_address(lp_resp["loyaltyPointDistributionStation"])
        contract = w3.eth.contract(address=station, abi=LOYALTY_POINTS_ABI)
        fee = int(lp_resp.get("claimFeeAmount", 0) or 0)
        amount = sum(int(p) for p in lp_resp.get("Points", []) if p) * 10**18
        tx = contract.functions.increasePoint(
            w3.to_checksum_address(lp_resp["loyaltyPointContract"]),
            int(lp_resp["VerifyIDs"][0]), account.address, amount, fee,
            bytes.fromhex(lp_resp["signature"].replace("0x", "")),
        ).build_transaction({"from": account.address, "nonce": nonce, "value": fee,
                             "gas": 500000, "gasPrice": w3.eth.gas_price})
    elif mint_func and mint_func.get("nftCoreAddress"):
        ss_addr = w3.to_checksum_address(ss_info.get("address", ""))
        contract = w3.eth.contract(address=ss_addr, abi=SPACE_STATION_ABI)
        sig = bytes.fromhex(claim_data.get("signature", "").replace("0x", ""))
        nft_addr = w3.to_checksum_address(mint_func["nftCoreAddress"])
        verify_id = int(mint_func["verifyIDs"][0])
        powah = int(mint_func["powahs"][0])
        cap = mint_func.get("cap")
        txd = {"from": account.address, "nonce": nonce, "gas": 500000, "gasPrice": w3.eth.gas_price}
        if cap:
            tx = contract.functions.claimCapped(int(number_id), sig, nft_addr, verify_id, powah, int(cap)).build_transaction(txd)
        else:
            tx = contract.functions.claim(int(number_id), sig, nft_addr, verify_id, powah).build_transaction(txd)
    else:
        raise RuntimeError("No valid claim data (no loyaltyPoints or NFT in prepareParticipate)")

    signed = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[Galxe] On-chain TX sent: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    print(f"[Galxe] Confirmed block {receipt['blockNumber']} status={receipt['status']}")
    if receipt["status"] != 1:
        raise RuntimeError(f"On-chain tx reverted: {tx_hash.hex()}")
    return tx_hash.hex()


def full_quest_status(campaign_id: str, token: str = None) -> dict:
    """Get full quest status: credentials eligibility + claim section + user participation.

    Returns dict with:
        - campaign_id, name, type, status, chain
        - space: {alias, id, name, isFollowing}
        - participate_condition: {eligible, formula, conditions: [{name, id, source, eligible}]}
        - reward_configs: [{id, eligible, description, conditions: [...]}]
        - user_participation: {status} or None
        - loyalty_points: int
        - already_claimed: bool
    """
    addr = _get_address(token).replace("EVM:", "").lower()

    cred_data = quest_cred_list(campaign_id, token)
    claim_data = quest_claim_section(campaign_id, token)

    result = {
        "campaign_id": campaign_id,
        "name": claim_data.get("name", ""),
        "type": claim_data.get("type", ""),
        "status": claim_data.get("status", ""),
        "chain": claim_data.get("chain", ""),
        "loyalty_points": claim_data.get("loyaltyPoints", 0),
        "number_id": claim_data.get("numberID", 0),
        "whitelist": claim_data.get("whitelistInfo", {}) or {},
        "space": claim_data.get("space", {}),
        "already_claimed": False,
        "user_participation": None,
        "participate_condition": None,
        "reward_configs": [],
    }

    up = claim_data.get("userParticipants", {})
    if up and up.get("list"):
        result["user_participation"] = up["list"][0]
        if up["list"][0].get("status") == "Success":
            result["already_claimed"] = True

    tc = cred_data.get("taskConfig", {})
    pc = tc.get("participateCondition")
    if pc:
        conds = []
        for c in pc.get("conditions", []):
            cred = c.get("cred", {})
            conds.append({
                "name": cred.get("name", ""),
                "id": cred.get("id", ""),
                "source": cred.get("credSource", ""),
                "type": cred.get("credType", ""),
                "eligible": cred.get("eligible", 0),
            })
        result["participate_condition"] = {
            "eligible": pc.get("eligible", False),
            "formula": pc.get("conditionalFormula", ""),
            "conditions": conds,
        }

    for rc in tc.get("rewardConfigs", []):
        conds = []
        for c in rc.get("conditions", []):
            cred = c.get("cred", {})
            conds.append({
                "name": cred.get("name", ""),
                "id": cred.get("id", ""),
                "source": cred.get("credSource", ""),
                "type": cred.get("credType", ""),
                "eligible": cred.get("eligible", 0),
                "reference_link": cred.get("referenceLink", ""),
            })
        result["reward_configs"].append({
            "id": rc.get("id", ""),
            "eligible": rc.get("eligible", False),
            "description": rc.get("description", ""),
            "formula": rc.get("conditionalFormula", ""),
            "conditions": conds,
        })

    return result


M_SAVE_PERMIT = """mutation($input:SavePermitTokenInput!){
  savePermitToken(input:$input){success}
}"""

Q_SS_PRECHECK = """query($id:ID!,$mc:Int!,$chain:Chain){
  campaign(id:$id){
    id
    ssPaymentPreCheck(mintCount:$mc){checkRes permitTokens{tokenAddr minimumTokenAmount spenderAddr}}
    ssPaymentPreCheckClaimPoints(chain:$chain){checkRes permitTokens{tokenAddr minimumTokenAmount spenderAddr}}
  }
}"""

Q_MYSTERY_BOXES = """query($addr:String!){
  mysteryBoxes{id name logo available
    participateFee{id chain tokenAmount tokenDetail{id chain tokenDecimal tokenLogo tokenSymbol tokenAddress}}
    discountParticipateFee{id chain tokenAmount tokenDetail{id chain tokenDecimal tokenLogo tokenSymbol tokenAddress}}
    rewardConfig{rewardCount rewardType rewardCap rewardDesc rewardIndex tokenDetail{id chain tokenDecimal tokenLogo tokenSymbol tokenAddress}}
    credentialGroups(address:$addr){id name credentials{id name}}
  }
}"""

Q_USER_TOKENS = """query($req:ListUserTokensRequest!){
  listUserTokens(request:$req){totalCount list{
    id chain tokenAmount tokenDetail{id chain tokenDecimal tokenLogo tokenSymbol tokenAddress}
  }}
}"""


def quest_cred_list(campaign_id: str, token: str = None) -> dict:
    addr = _get_address(token).replace("EVM:", "").lower()
    return gql(Q_QUEST_CRED_LIST, {"id": campaign_id, "addr": addr}, token).get("campaign", {})


def sync_credential(cred_id: str, campaign_id: str = None, captcha: dict = None,
                     cred_source: str = None, token: str = None) -> dict:
    """Sync a credential value. For Twitter creds, campaign_id and captcha are required.

    Args:
        cred_id: The credential ID to sync.
        campaign_id: Campaign ID (required for Twitter creds).
        captcha: Geetest captcha dict with lotNumber, captchaOutput, passToken, genTime.
        cred_source: Credential source type hint (TWITTER, DISCORD, TELEGRAM, etc.).
                     If omitted, syncs without source-specific nested object.
    """
    addr = _get_address(token)
    sync_opts = {"credId": cred_id, "address": addr}
    if cred_source and cred_source.upper() == "TWITTER" and campaign_id:
        cap_data = captcha or {}
        sync_opts["twitter"] = {
            "campaignID": campaign_id,
            "captcha": {
                "lotNumber": cap_data.get("lotNumber", ""),
                "captchaOutput": cap_data.get("captchaOutput", ""),
                "passToken": cap_data.get("passToken", ""),
                "genTime": cap_data.get("genTime", ""),
                "encryptedData": cap_data.get("encryptedData", ""),
            }
        }
    # DISCORD / TELEGRAM member creds: membership is verified server-side via
    # verify_credentials — sync with just {address, credId}. (A nested
    # telegram/discord object makes Galxe return HTTP 422.)
    return gql(M_SYNC_CRED, {"input": {"syncOptions": sync_opts}}, token).get("syncCredentialValue", {})


def add_cred_items(cred_id: str, campaign_id: str, items: list,
                    captcha: dict, token: str = None) -> dict:
    inp = {"credId": cred_id, "campaignId": campaign_id, "operation": "APPEND", "items": items, "captcha": captcha}
    return gql(M_ADD_CRED_ITEMS, {"input": inp}, token).get("typedCredentialItems", {})


def quest_claim_section(campaign_id: str, token: str = None) -> dict:
    addr = _get_address(token).replace("EVM:", "").lower()
    return gql(Q_QUEST_CLAIM_SECTION, {"id": campaign_id, "addr": addr, "withAddr": True, "isParent": False}, token).get("campaign", {})


def prepare_participate(campaign_id: str, chain: str = "GRAVITY_ALPHA",
                         signature: str = "", mint_count: int = 0,
                         claim_version: str = "CHARGE_CLAIM_FEE_VERSION",
                         point_mint_amount: int = 1,
                         captcha: dict = None, token: str = None) -> dict:
    addr = _get_address(token)
    inp = {"signature": signature, "campaignID": campaign_id, "address": addr,
           "mintCount": mint_count, "chain": chain, "claimVersion": claim_version,
           "pointMintAmount": point_mint_amount}
    if captcha:
        inp["captcha"] = captcha
    return gql(M_PREPARE_PARTICIPATE, {"input": inp}, token).get("prepareParticipate", {})


def register_ss_payment(campaign_id: int, chain: str, claim_type: str,
                         powahs: list, verify_ids: list,
                         points_task: dict = None, token: str = None) -> dict:
    task_detail = {"questTask": {"campaignId": campaign_id, "chain": chain,
                                  "claimType": claim_type, "powahs": powahs, "verifyIds": verify_ids}}
    if points_task:
        task_detail["questTask"]["pointsTask"] = points_task
    return gql(M_REGISTER_SS_PAYMENT, {"input": {"taskDetail": task_detail}}, token).get("registerSSPaymentTask", {})


def payment_task_status(task_id: int, token: str = None) -> str:
    return gql(Q_PAYMENT_TASK_INFO, {"id": task_id}, token).get("paymentTaskInfo", {}).get("status", "Unknown")


def participation_info(ids: list, is_loyalty_point: bool = True, token: str = None) -> list:
    return gql(Q_PARTICIPATION_INFO, {"ids": ids, "lp": is_loyalty_point}, token).get("participations", [])


def estimate_cost(quest_id: int, chain: str = "GRAVITY_ALPHA",
                   mint_count: int = 1, mint_type: str = "Points", token: str = None) -> dict:
    inp = {"questId": quest_id, "mints": [{"chain": chain, "mintCount": mint_count, "mintType": mint_type}]}
    return gql(Q_ESTIMATE_COST, {"input": inp}, token).get("estimateQuestCostDetail", {})


def save_permit_token(token_addr: str, spender: str, value: str,
                       permit: dict, nonce: int = 0, token: str = None) -> bool:
    inp = {"permit": permit, "spender": spender, "token": token_addr, "value": value, "nonce": nonce}
    return gql(M_SAVE_PERMIT, {"input": inp}, token).get("savePermitToken", {}).get("success", False)


def ss_precheck(campaign_id: str, mint_count: int = 25,
                 chain: str = "GRAVITY_ALPHA", token: str = None) -> dict:
    return gql(Q_SS_PRECHECK, {"id": campaign_id, "mc": mint_count, "chain": chain}, token).get("campaign", {})


def mystery_boxes(token: str = None) -> list:
    addr = _get_address(token)
    return gql(Q_MYSTERY_BOXES, {"addr": addr}, token).get("mysteryBoxes", [])


def user_tokens(limit: int = 10, token: str = None) -> list:
    return gql(Q_USER_TOKENS, {"req": {"afterId": 0, "limit": limit}}, token).get("listUserTokens", {}).get("list", [])

# HELPERS
# ============================================================

def _get_address(token: str = None) -> str:
    """Get EVM:prefixed address from credentials file."""
    with open(CREDENTIALS_FILE) as f:
        creds = json.load(f)
    addr = creds.get("address", "")
    return addr if addr.startswith("EVM:") else f"EVM:{addr}"


# ============================================================
# GALXE CAPTCHA (browser-generated WASM token)
# ============================================================
#
# Galxe no longer uses GeeTest v4. The captcha payload is built client-side by
# an in-house Rust->WASM module shipped in the Galxe frontend
# (app.galxe.com/_next/static/media/wasm_lib_bg.*.wasm). CapSolver / AntiCaptcha
# / GeeTest solvers no longer work — they return a real GeeTest token, which
# Galxe rejects with "lotNumber is invalid".
#
# We run Galxe's own JS in a headless browser (Playwright, sync API) and call
# the captcha builder directly. It returns:
#     lotNumber     = sha256(apiName)        # e.g. sha256("PrepareParticipate")
#     passToken     = sha256(genTime)
#     genTime       = unix seconds
#     captchaOutput = wasm.generate_data(...).geetest_encrypted   # the real proof
# The token is NOT IP-bound, so the browser needs no proxy.
#
# Requires: pip install playwright && python -m playwright install chromium

import atexit

_CAPTCHA_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# JS that locates Galxe's captcha builder via webpack and invokes it.
_CAPTCHA_JS = r"""
async (apiName) => {
  if (!window.__galxeReq) {
    const fid = "cap" + Math.random();
    await new Promise(res =>
      window.webpackChunk_N_E.push([[fid], {}, r => { window.__galxeReq = r; res(); }]));
  }
  const req = window.__galxeReq;
  let modId = null;
  for (let n = 0; n < 30 && !modId; n++) {
    modId = Object.keys(req.m).find(k => {
      try { return req.m[k].toString().includes("geetest_encrypted"); } catch (e) { return false; }
    });
    if (!modId) await new Promise(r => setTimeout(r, 500));
  }
  if (!modId) return { error: "captcha builder module not found (Galxe frontend changed?)" };
  const mod = req(modId);
  const H = mod.H || Object.values(mod).find(v => typeof v === "function");
  if (!H) return { error: "captcha builder export not found" };
  try {
    return { ok: true, captcha: await H({ apiName: apiName, shouldEncrypt: true }) };
  } catch (e) {
    return { error: "captcha builder threw: " + String(e) };
  }
}
"""


class _WasmCaptcha:
    """Persistent headless browser (sync Playwright) generating Galxe's WASM token."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._page = None

    def _ensure_page(self):
        if self._page is not None and not self._page.is_closed():
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Playwright is required for Galxe's WASM captcha. Install with:\n"
                "  pip install playwright && python -m playwright install chromium"
            ) from e
        if self._pw is None:
            self._pw = sync_playwright().start()
        if self._browser is None:
            self._browser = self._pw.chromium.launch(
                headless=True,
                args=["--lang=en-US,en", "--disable-blink-features=AutomationControlled"],
            )
        ctx = self._browser.new_context(user_agent=_CAPTCHA_UA)
        self._page = ctx.new_page()
        print("[Galxe] Loading Galxe frontend (WASM captcha)...")
        self._page.goto("https://app.galxe.com/quest", wait_until="domcontentloaded", timeout=45000)
        self._page.wait_for_timeout(3000)

    def solve(self, action: str) -> dict:
        last_err = None
        for _ in range(2):
            try:
                self._ensure_page()
                res = self._page.evaluate(_CAPTCHA_JS, action)
                if res.get("ok"):
                    cap = res["captcha"]
                    print(f"[Galxe] Generated WASM captcha (action={action})")
                    return {
                        "lotNumber": cap["lotNumber"],
                        "captchaOutput": cap["captchaOutput"],
                        "passToken": cap["passToken"],
                        "genTime": cap["genTime"],
                    }
                last_err = res.get("error", "unknown")
            except Exception as e:
                last_err = str(e)
            self._page = None  # reset and retry once
        raise RuntimeError(f"WASM captcha generation failed: {last_err}")

    def close(self):
        try:
            if self._browser is not None:
                self._browser.close()
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._browser = self._pw = self._page = None


_captcha = _WasmCaptcha()
atexit.register(_captcha.close)


def close_captcha_browser():
    """Shut down the captcha browser singleton (also runs automatically at exit)."""
    _captcha.close()


def solve_geetest_captcha(captcha_id: str = None, risk_type: str = "ai",
                          proxy: str = None, action: str = "PrepareParticipate",
                          method: str = "auto") -> dict:
    """Generate Galxe's WASM captcha token via a headless browser.

    `action` is the Galxe API/operation name — lotNumber = sha256(action), so it
    MUST match the mutation it gates (e.g. "PrepareParticipate",
    "AddTypedCredentialItems", "SyncCredentialValue").

    captcha_id / risk_type / proxy / method are accepted for backward
    compatibility but ignored: CapSolver/AntiCaptcha are obsolete (Galxe dropped
    GeeTest). See the module section header above.
    """
    return _captcha.solve(action)


# ============================================================
# SIWE LOGIN + QUEST AUTOMATION  (ported sync from former galxe_auto.py)
# ============================================================

import random as _rnd
import time as _time
from datetime import datetime, timedelta, timezone

CRED_TWITTER, CRED_EMAIL, CRED_EVM_ADDRESS = "TWITTER", "EMAIL", "EVM_ADDRESS"
CRED_GALXE_ID, CRED_DISCORD, CRED_TELEGRAM = "GALXE_ID", "DISCORD", "TELEGRAM"
SRC_VISIT_LINK, SRC_QUIZ, SRC_SURVEY = "VISIT_LINK", "QUIZ", "SURVEY"
SRC_SPACE_USERS, SRC_SPACE_FOLLOWER = "SPACE_USERS", "SPACE_FOLLOWER"
SRC_WATCH_YOUTUBE, SRC_CAMPAIGN_REFERRAL = "WATCH_YOUTUBE", "CAMPAIGN_REFERRAL"
SRC_JOIN_TELEGRAM = "JOIN_TELEGRAM"
SRC_TWITTER_FOLLOW, SRC_TWITTER_LIKE = "TWITTER_FOLLOW", "TWITTER_LIKE"
SRC_TWITTER_RT, SRC_TWITTER_TWEET = "TWITTER_RETWEET", "TWITTER_TWEET"

M_SIGN_IN = "mutation SignIn($input: Auth) {\n  signin(input: $input)\n}\n"

Q_READ_QUIZ = """query readQuiz($id: ID!) {
  credential(id: $id) { credQuiz { quizzes { title type items { value } } } }
}"""

M_VERIFY_CREDS = """mutation VerifyCredentials($input: VerifyCredentialsInput!) {
  verifyCredentials(input: $input)
}"""

M_SYNC_QUIZ = """mutation SyncCredentialValue($input: SyncCredentialValueInput!) {
  syncCredentialValue(input: $input) {
    value { allow quiz { allow correct } } message
  }
}"""

M_SYNC_EVAL = """mutation syncEvaluateCredentialValue($input: SyncEvaluateCredentialValueInput!) {
  syncEvaluateCredentialValue(input: $input) {
    result value { allow } message
  }
}"""


def _rand_string(n: int = 96) -> str:
    import secrets
    alp = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(secrets.choice(alp) for _ in range(n))


def login(save: bool = True) -> str:
    """SIWE sign-in using the wallet key (~/wallet/.env); saves JWT to the creds file."""
    from eth_account import Account
    from eth_account.messages import encode_defunct

    pk = _load_private_key()
    raw_addr = Account.from_key(pk).address
    now = datetime.now(timezone.utc)
    iss = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{_rnd.randint(100, 999)}Z"
    exp = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.") + f"{_rnd.randint(100, 999)}Z"
    msg = (
        f"app.galxe.com wants you to sign in with your Ethereum account:\n{raw_addr}\n\n"
        f"Sign in with Ethereum to the app.\n\nURI: https://app.galxe.com\nVersion: 1\n"
        f"Chain ID: 1\nNonce: {_rand_string(96)}\nIssued At: {iss}\nExpiration Time: {exp}"
    )
    sig = Account.sign_message(encode_defunct(text=msg), pk).signature.hex()
    if not sig.startswith("0x"):
        sig = "0x" + sig
    data = gql(M_SIGN_IN, {"input": {"address": raw_addr, "addressType": "EVM",
                                     "message": msg, "signature": sig}})
    tok = data.get("signin", "")
    if not tok:
        raise RuntimeError("SignIn returned empty token")
    if save:
        creds = {}
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE) as f:
                creds = json.load(f)
        creds["access_token"] = tok
        creds["address"] = f"EVM:{raw_addr}" if not raw_addr.startswith("EVM:") else raw_addr
        os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(creds, f, indent=2)
    print(f"[Galxe] Signed in as {raw_addr}")
    return tok


def read_quiz(cred_id: str, token: str = None) -> list:
    data = gql(Q_READ_QUIZ, {"id": cred_id}, token)
    return data.get("credential", {}).get("credQuiz", {}).get("quizzes", []) or []


def verify_credentials(cred_ids: list, token: str = None) -> dict:
    inp = {"address": _get_address(token), "credIds": cred_ids}
    return gql(M_VERIFY_CREDS, {"input": inp}, token)


def sync_evaluate_credential_value(eval_expr: dict, sync_options: dict, token: str = None) -> dict:
    inp = {"evalExpr": eval_expr, "syncOptions": sync_options}
    return gql(M_SYNC_EVAL, {"input": inp}, token).get("syncEvaluateCredentialValue", {})


def _sync_quiz(cred_id: str, answers: list, token: str = None) -> dict:
    sync_opts = {"address": _get_address(token), "credId": cred_id,
                 "quiz": {"answers": [str(a) for a in answers]}}
    return gql(M_SYNC_QUIZ, {"input": {"syncOptions": sync_opts}}, token).get("syncCredentialValue", {})


def solve_quiz(cred_id: str, token: str = None) -> bool:
    """Brute-force a multiple-choice quiz credential. Returns True if solved."""
    quizzes = read_quiz(cred_id, token)
    if not quizzes or any(q.get("type") != "MULTI_CHOICE" for q in quizzes):
        print(f"[Quiz] Non-multi-choice or empty quiz, cannot auto-solve: {cred_id}")
        return False
    answers = [0] * len(quizzes)
    correct = [False] * len(quizzes)
    for attempt in range(1, 21):
        answers = [answers[i] if correct[i] else answers[i] + (0 if attempt == 1 else 1)
                   for i in range(len(answers))]
        if any(answers[i] >= len(quizzes[i]["items"]) for i in range(len(answers))):
            print(f"[Quiz] Exhausted answer combinations for {cred_id}")
            return False
        res = _sync_quiz(cred_id, answers, token)
        correct = (res.get("value", {}) or {}).get("quiz", {}).get("correct", [False] * len(answers))
        print(f"[Quiz] Attempt {attempt}: answers={answers}, correct={correct}")
        if all(correct):
            print(f"[Quiz] Solved! Answers: {answers}")
            return True
    print(f"[Quiz] Failed to solve {cred_id}")
    return False


def _follow_space_and_sync(campaign_id: str, cred_id: str, space_id: int, token: str = None):
    # quest_claim_section's space sometimes lacks `id` → fetch it reliably.
    if not space_id:
        try:
            sp = gql("query C($id:ID!){campaign(id:$id){space{id}}}", {"id": campaign_id}, token).get("campaign", {})
            space_id = int((sp.get("space") or {}).get("id", 0) or 0)
        except Exception:
            space_id = 0
    if space_id:
        try:
            follow_space([int(space_id)], token)
        except Exception as e:
            print(f"[Quest] follow_space note: {e}")
    eval_expr = {"address": _get_address(token), "credId": cred_id, "entityExpr": {
        "attrFormula": "ALL",
        "attrs": [{"attrName": "follow", "operatorSymbol": "==", "targetValue": "1",
                   "__typename": "ExprEntityAttr"}],
        "credId": cred_id}}
    sync_evaluate_credential_value(eval_expr, {"address": _get_address(token), "credId": cred_id}, token)


# ============================================================
# Social action helpers (Twitter via x-client, Telegram via telegram-userbot)
# ============================================================
# Both twikit (x-client) and telethon (telegram-userbot) are in the runtime venv,
# so we import each tool's modules directly (by file path, to dodge the duplicate
# `auth.py` name) and run their async fns via asyncio.run. Galxe reward links are
# "intent" URLs: .../intent/follow?screen_name=X, .../intent/(like|retweet)?tweet_id=Y,
# and t.me/<channel> for Telegram.

import re as _re

_X_CLIENT_DIR = str(Path.home() / "scripts" / "x-client")
_TG_BOT_DIR = str(Path.home() / "scripts" / "telegram-userbot")
_social_mods = {}


def _load_tool_module(directory: str, mod: str):
    key = f"{directory}:{mod}"
    if key in _social_mods:
        return _social_mods[key]
    import importlib.util
    path = os.path.join(directory, mod + ".py")
    spec = importlib.util.spec_from_file_location(f"_galxe_ext_{abs(hash(key))}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _social_mods[key] = m
    return m


def _run_coro(coro_factory):
    """Run an async coroutine to completion in a DEDICATED thread.

    Playwright's sync API (used by the WASM captcha) keeps an event loop running in
    the main thread, so `asyncio.run()` there raises "cannot be called from a running
    event loop". Running in a fresh thread gives the coroutine its own clean loop.
    """
    import threading
    import asyncio
    box = {}

    def worker():
        try:
            box["v"] = asyncio.run(coro_factory())
        except BaseException as e:  # noqa: BLE001
            box["e"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join()
    if "e" in box:
        raise box["e"]
    return box.get("v")


def _twitter_action(kind: str, target: str, text: str = None) -> bool:
    """Perform a Twitter action via x-client (twikit). kind: follow|like|retweet|quote.
    For `quote`, target = the quoted tweet URL and text = the comment."""
    import sys
    # x-client's users/tweets do `from auth import get_client`, so the dir must be
    # on sys.path (its `auth` is self-contained; telegram-userbot uses importlib).
    if _X_CLIENT_DIR not in sys.path:
        sys.path.insert(0, _X_CLIENT_DIR)
    try:
        import auth as xauth
        import users as xusers
        import tweets as xtweets
    except Exception as e:
        print(f"[Social] x-client unavailable: {str(e)[:120]}")
        return False

    async def run():
        c = await xauth.get_client()
        if kind == "follow":
            u = await xauth.get_user_by_screen_name(target, c)
            await xusers.follow(u.id, c)
        elif kind == "like":
            await xtweets.like(target, c)
        elif kind == "retweet":
            await xtweets.retweet(target, c)
        elif kind == "quote":
            # quote-tweet = a new tweet with the quoted tweet URL attached
            await xtweets.create_tweet(text or "", attachment_url=target, client=c)

    try:
        _run_coro(run)
        print(f"[Social] Twitter {kind}: {target}")
        return True
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("already", "duplicate", "327", "139")):
            print(f"[Social] Twitter {kind} already done: {target}")
            return True
        print(f"[Social] Twitter {kind} failed ({target}): {str(e)[:140]}")
        return False


def _join_telegram(channel: str) -> bool:
    """Join a Telegram channel/group via telegram-userbot (telethon)."""
    import asyncio
    try:
        tgauth = _load_tool_module(_TG_BOT_DIR, "auth")
        tggroups = _load_tool_module(_TG_BOT_DIR, "groups")
    except Exception as e:
        print(f"[Social] telegram-userbot unavailable: {str(e)[:120]}")
        return False

    async def run():
        tgauth._client = None  # fresh client bound to THIS event loop
        c = await tgauth.get_client()
        try:
            return await tggroups.join_group(c, channel)
        finally:
            try:
                await c.disconnect()
            except Exception:
                pass
            tgauth._client = None

    try:
        res = _run_coro(run) or {}
        ok = bool(res.get("joined"))
        print(f"[Social] Telegram join {channel}: {'ok' if ok else res.get('error', 'failed')}")
        return ok
    except Exception as e:
        print(f"[Social] Telegram join failed ({channel}): {str(e)[:140]}")
        return False


def _do_twitter_cred(cred: dict) -> bool:
    """Parse a Twitter cred's reward link + source, then perform the real action."""
    from urllib.parse import unquote
    link = cred.get("referenceLink") or cred.get("reference_link") or ""
    name = cred.get("name") or ""
    csrc = (cred.get("credSource") or cred.get("source") or "").upper()
    if csrc == "TWITTER_FOLLOW":
        m = _re.search(r"screen_name=([A-Za-z0-9_]{1,20})", link)
        if m:
            return _twitter_action("follow", m.group(1))
    elif csrc in ("TWITTER_LIKE", "TWITTER_RT", "TWITTER_RETWEET"):
        m = _re.search(r"tweet_id=(\d+)", link)
        if m:
            return _twitter_action("like" if csrc == "TWITTER_LIKE" else "retweet", m.group(1))
    elif csrc == "TWITTER_QUOTE":
        # link: "intent/tweet?text=<txt> https://x.com/<user>/status/<id>"; quote = a
        # new tweet with that status URL attached. Tweet id often only in the name.
        mu = _re.search(r"(https?://(?:x|twitter)\.com/\w+/status/\d+)", link)
        quoted = mu.group(1) if mu else None
        if not quoted:
            mid = _re.search(r"(\d{15,})", name) or _re.search(r"status/(\d+)", link)
            if mid:
                quoted = f"https://x.com/i/web/status/{mid.group(1)}"
        mt = _re.search(r"intent/tweet\?text=([^ &]*)", link)
        text = unquote(mt.group(1)) if mt else "#"
        if quoted:
            return _twitter_action("quote", quoted, text=text)
    elif csrc == "TWITTER_USER":
        return False  # passive account requirement — nothing to do
    print(f"[Social] Can't parse Twitter task ({csrc}): {link or name}")
    return False


def _do_telegram_cred(cred: dict) -> bool:
    link = cred.get("referenceLink") or cred.get("reference_link") or ""
    m = _re.search(r"t\.me/(\+?[A-Za-z0-9_]+)", link)
    if m:
        return _join_telegram(m.group(1))
    print(f"[Social] Can't parse Telegram link: {link or cred.get('name')}")
    return False


def _complete_credential(campaign_id: str, cred: dict, eligible: bool,
                         space_id: int = 0, token: str = None) -> bool:
    """Complete one credential. Returns True if a follow-up sync_credential is needed."""
    if eligible:
        return False
    ctype = cred.get("credType", cred.get("type", ""))
    csrc = cred.get("credSource", cred.get("source", ""))
    cid = cred.get("id", "")
    cname = cred.get("name", "")
    print(f"[Quest] Completing: {cname} (type={ctype}, source={csrc})")

    if csrc in (SRC_SPACE_USERS, SRC_SPACE_FOLLOWER):
        _follow_space_and_sync(campaign_id, cid, space_id, token)
        return False
    if csrc == SRC_QUIZ:
        solve_quiz(cid, token)
        return False
    if csrc in (SRC_VISIT_LINK, SRC_WATCH_YOUTUBE):
        cap = solve_geetest_captcha(action="AddTypedCredentialItems")
        add_cred_items(cid, campaign_id, [_get_address(token)], cap, token)
        return True
    if csrc == SRC_SURVEY:
        print("[Quest] Survey needs manual answers — skipping")
        return False
    if csrc == SRC_CAMPAIGN_REFERRAL:
        print("[Quest] Referral can't be automated — skipping")
        return False
    if ctype == CRED_TWITTER:
        # TWITTER_USER is a passive account gate (age/followers) — no action, no
        # typed items (add_cred_items errors "unsupported credential source").
        if csrc == "TWITTER_USER":
            print("[Quest] X Account Requirement — passive check (verify only)")
            return True
        # Perform the actual Twitter action (follow/like/RT) via x-client, then sync.
        _do_twitter_cred(cred)
        cap = solve_geetest_captcha(action="AddTypedCredentialItems")
        add_cred_items(cid, campaign_id, [_get_address(token)], cap, token)
        return True
    if ctype == CRED_TELEGRAM or csrc == "JOIN_TELEGRAM":
        # Join the Telegram channel/group via telegram-userbot, then sync.
        _do_telegram_cred(cred)
        return True
    if ctype == CRED_DISCORD:
        # Discord membership — account must already be a member (no automation).
        return True
    print(f"[Quest] Unsupported credential (type={ctype}, source={csrc}) — skipping")
    return False


def _sync_cred(campaign_id: str, cred: dict, token: str = None):
    ctype = cred.get("credType", cred.get("type", ""))
    src = "TWITTER" if ctype == CRED_TWITTER else (
        "DISCORD" if ctype == CRED_DISCORD else ("TELEGRAM" if ctype == CRED_TELEGRAM else None))
    cap = None
    if ctype == CRED_TWITTER:
        cap = solve_geetest_captcha(action="SyncCredentialValue")
    sync_credential(cred["id"], campaign_id=campaign_id, captcha=cap, cred_source=src, token=token)
    print(f"[Quest] Synced credential {cred['id']}")


def _eligibility_map(cred_data: dict) -> dict:
    """Map credId -> eligible (0/1) from a quest_cred_list result."""
    m = {}
    tc = cred_data.get("taskConfig") or {}
    cond_groups = []
    pc = tc.get("participateCondition")
    if pc:
        cond_groups.append(pc.get("conditions", []))
    for rc in tc.get("rewardConfigs", []) or []:
        cond_groups.append(rc.get("conditions", []))
    for conds in cond_groups:
        for c in conds or []:
            cr = c.get("cred") or {}
            if cr.get("id"):
                m[cr["id"]] = cr.get("eligible", 0)
    for g in cred_data.get("credentialGroups", []) or []:
        for cr in g.get("credentials", []) or []:
            if cr.get("id"):
                m[cr["id"]] = cr.get("eligible", 0)
    return m


def complete_quest(campaign_id: str, token: str = None) -> None:
    """Complete all auto-completable tasks of a quest (prereqs + reward credential groups)."""
    cred_data = quest_cred_list(campaign_id, token)
    claim_data = quest_claim_section(campaign_id, token)
    name = claim_data.get("name", campaign_id)
    space_id = int((claim_data.get("space") or {}).get("id", 0) or 0)
    print(f"\n[Quest] === Completing: {name} ===")

    groups = []
    tc = cred_data.get("taskConfig") or {}
    pc = tc.get("participateCondition")
    if pc:
        groups.append([(c.get("cred") or {}, c.get("eligible")) for c in pc.get("conditions", [])])
    for rc in tc.get("rewardConfigs", []) or []:
        groups.append([(c.get("cred") or {}, c.get("eligible")) for c in rc.get("conditions", [])])
    # Also handle credentialGroups shape (some campaigns)
    for g in cred_data.get("credentialGroups", []) or []:
        creds = g.get("credentials", []) or []
        conds = g.get("conditions", []) or []
        pairs = [(creds[i], conds[i].get("eligible") if i < len(conds) else creds[i].get("eligible"))
                 for i in range(len(creds))]
        groups.append(pairs)

    to_verify = []
    lagging = set()  # social-action creds whose Galxe verify can lag ~1 min
    for group in groups:
        for cred, eligible in group:
            cid = cred.get("id")
            if not cid:
                continue
            ctype = cred.get("credType", cred.get("type", ""))
            csrc = cred.get("credSource", cred.get("source", ""))
            try:
                need_sync = _complete_credential(campaign_id, cred, bool(eligible), space_id, token)
                if need_sync:
                    _sync_cred(campaign_id, cred, token)
                if not eligible:
                    to_verify.append(cid)
                    if (ctype == CRED_TWITTER and csrc != "TWITTER_USER") \
                            or ctype == CRED_TELEGRAM or csrc == "JOIN_TELEGRAM":
                        lagging.add(cid)
                _time.sleep(_rnd.uniform(2, 4))
            except Exception as e:
                print(f"[Quest] Failed {cred.get('name')}: {e}")

    to_verify = list(dict.fromkeys(to_verify))
    if to_verify:
        try:
            verify_credentials(to_verify, token)
        except Exception as e:
            print(f"[Quest] verify_credentials failed: {e}")
        elig = _eligibility_map(quest_cred_list(campaign_id, token))
        # Galxe's Twitter verification (esp. quote/RT) lags ~1 min — re-verify the
        # still-pending social creds a few times before giving up.
        pending = [c for c in to_verify if c in lagging and not elig.get(c)]
        for _ in range(3):
            if not pending:
                break
            print(f"[Quest] {len(pending)} social cred(s) not verified yet — waiting for Galxe...")
            _time.sleep(25)
            try:
                verify_credentials(pending, token)
            except Exception:
                pass
            elig = _eligibility_map(quest_cred_list(campaign_id, token))
            pending = [c for c in pending if not elig.get(c)]
        done = sum(1 for c in to_verify if elig.get(c))
        print(f"[Quest] Verified {done}/{len(to_verify)} credentials"
              + (f" ({len(pending)} still pending)" if pending else ""))
    print(f"[Quest] === Done: {name} ===\n")


def claim_quest(campaign_id: str, token: str = None) -> bool:
    """Solve captcha, prepareParticipate, execute the on-chain tx, and confirm. Returns True if claimed."""
    status = full_quest_status(campaign_id, token)
    name = status.get("name", campaign_id)
    if status.get("already_claimed"):
        print(f"[Claim] Already claimed: {name}")
        return False
    # Token / LuckBasedToken campaigns (ZK_RAFFLE etc.) are ENTERED on-chain,
    # not "claimed" via loyalty/NFT.
    if status.get("type") in ("Token", "LuckBasedToken"):
        if (status.get("user_participation") or {}).get("status"):
            print(f"[Claim] Already entered raffle: {name}")
            return False
        enter_zk_raffle(campaign_id, token)
        return True
    wl = status.get("whitelist", {}) or {}
    point_amount = int(wl.get("currentPeriodMaxLoyaltyPoints", 0)) - int(wl.get("currentPeriodClaimedLoyaltyPoints", 0))
    nft_amount = 0 if wl.get("maxCount", -1) == -1 else max(0, int(wl.get("maxCount", 0)) - int(wl.get("usedCount", 0)))
    if point_amount <= 0 and nft_amount <= 0:
        print(f"[Claim] Nothing to claim for {name}")
        return False
    claim_chain = "GRAVITY_ALPHA" if point_amount > 0 else (status.get("chain") or "GRAVITY_ALPHA")
    mint_count = max(1, nft_amount) if nft_amount > 0 else 0
    print(f"[Claim] {name}: points={point_amount}, nft={nft_amount}, chain={claim_chain}")

    captcha = solve_geetest_captcha(action="PrepareParticipate")
    prep = prepare_participate(campaign_id, chain=claim_chain, captcha=captcha,
                               mint_count=mint_count, point_mint_amount=point_amount or 1, token=token)
    lp = prep.get("loyaltyPointsTxResp") or {}
    mint = prep.get("mintFuncInfo") or {}
    if not (prep.get("allow") or lp.get("allow") or mint.get("verifyIDs")):
        print(f"[Claim] Not allowed: {prep.get('disallowReason') or lp.get('disallowReason') or 'unknown'}")
        return False

    tx_hash = execute_onchain_claim(prep, claim_chain, number_id=status.get("number_id", 0))
    if lp.get("loyaltyPointContract"):
        participate_point(campaign_id, lp.get("nonce", 0), tx_hash, lp.get("VerifyIDs", []), claim_chain, token)
    elif mint.get("verifyIDs"):
        ss = prep.get("spaceStationInfo") or {}
        participate(campaign_id, ss.get("chain", claim_chain), prep.get("nonce", 0), tx_hash, mint["verifyIDs"][0], token)
    print(f"[Claim] ✅ Claimed {name} (tx {tx_hash})")
    return True


def complete_and_claim(campaign_id: str, token: str = None) -> bool:
    """Complete all tasks, then claim."""
    complete_quest(campaign_id, token)
    _time.sleep(_rnd.uniform(3, 6))
    return claim_quest(campaign_id, token)


# ============================================================
# ZK_RAFFLE entry (on-chain on Gravity; reward chain is separate)
# ============================================================
# Token campaigns with distributionType ZK_RAFFLE are ENTERED (not "claimed") by
# an on-chain tx on GRAVITY to the raffle contract (= prepareParticipate.spaceStation),
# then a Participate mutation on GRAVITY_ALPHA with that tx hash. The user signs the
# Gravity tx and pays ~0.1 G gas (NO BNB — BSC/USDT is only the reward chain).
# Verified by decoding a real entry tx (HAR). See enter_zk_raffle() below.
# (gasless_available/M_SS_PRECHECK_CAMPAIGN below are kept for the relayer-sponsored
#  variant; the implemented path is the Gravity wallet tx.)

M_SS_PRECHECK_CAMPAIGN = """query ssPreCheckCampaign($id: ID!, $mc: Int!, $chains: [Chain!]!) {
  campaign(id: $id) {
    numberID chain
    space { spaceBalance { sufficientForGaslessClaimOnChain(chains: $chains) { sufficient chain } } }
    ssPaymentPreCheck(mintCount: $mc) { checkRes }
  }
}"""


def gasless_available(campaign_id: str, chain: str = "GRAVITY_ALPHA", token: str = None) -> tuple:
    """Return (is_sufficient: bool, checkRes: str) for relayer-sponsored gasless on `chain`."""
    d = gql(M_SS_PRECHECK_CAMPAIGN, {"id": campaign_id, "mc": 1, "chains": [chain]}, token).get("campaign", {})
    suff = (((d.get("space") or {}).get("spaceBalance") or {}).get("sufficientForGaslessClaimOnChain") or [])
    ok = any(x.get("sufficient") for x in suff)
    return ok, (d.get("ssPaymentPreCheck") or {}).get("checkRes", "?")


# ZK raffle on-chain entry fn on Gravity (contract = prepareParticipate.spaceStation):
#   participate(uint256 campaignNumberId, address account, uint256 verifyID, bytes signature)
# selector 0xc8cbf5e3 (decoded from a real entry tx; reward chain is separate, e.g. BSC USDT).
_ZK_RAFFLE_SELECTOR = bytes.fromhex("c8cbf5e3")
GRAVITY_RPC = "https://rpc.gravity.xyz"


def enter_zk_raffle(campaign_id: str, token: str = None) -> dict:
    """Enter a ZK_RAFFLE token campaign: prepareParticipate (reward chain) -> on-chain
    tx on Gravity -> Participate. Pays a tiny bit of Gravity gas (G); no BNB needed.
    Requires all tasks done (prepareParticipate must allow) and a little G in the wallet.
    """
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    from eth_abi import encode as abi_encode

    info = quest_claim_section(campaign_id, token)
    num = int(info.get("numberID"))
    reward_chain = info.get("chain") or "BSC"

    cap = solve_geetest_captcha(action="PrepareParticipate")
    prep = prepare_participate(campaign_id, chain=reward_chain, captcha=cap,
                              mint_count=1, point_mint_amount=0, token=token)
    if not prep.get("allow"):
        raise RuntimeError(f"prepareParticipate not allowed: {prep.get('disallowReason') or 'unknown'}")
    # Raffle (Token) uses tokenRewardCampaignTxResp.verifyID + the top-level signature;
    # LuckBasedToken uses luckBasedTokenCampaignTxResp.dummyId + its own signature.
    # Both hit the SAME on-chain fn (selector 0xc8cbf5e3) on spaceStation.
    tr = prep.get("tokenRewardCampaignTxResp") or {}
    lk = prep.get("luckBasedTokenCampaignTxResp") or {}
    if tr.get("verifyID"):
        vid, sig = int(tr["verifyID"]), prep.get("signature") or ""
    elif lk.get("dummyId"):
        vid, sig = int(lk["dummyId"]), (lk.get("signature") or prep.get("signature") or "")
    else:
        raise RuntimeError("prepareParticipate has no token/luck raffle data")
    if not sig:
        raise RuntimeError("prepareParticipate returned no signature")
    nonce_sig = prep["nonce"]
    sig_b = bytes.fromhex(sig[2:] if sig.startswith("0x") else sig)
    contract = Web3.to_checksum_address(prep["spaceStation"])

    pk = _load_private_key()
    w3 = Web3(Web3.HTTPProvider(GRAVITY_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    acct = w3.eth.account.from_key(pk)
    data = _ZK_RAFFLE_SELECTOR + abi_encode(
        ["uint256", "address", "uint256", "bytes"], [num, acct.address, vid, sig_b])
    # de-risk: simulate before spending gas — a revert surfaces here, no tx sent
    try:
        w3.eth.call({"from": acct.address, "to": contract, "value": 0, "data": data})
    except Exception as e:
        raise RuntimeError(f"raffle entry would revert (eth_call): {str(e)[:160]}")
    tx = {"from": acct.address, "to": contract, "value": 0, "data": data,
          "nonce": w3.eth.get_transaction_count(acct.address),
          "gas": 200000, "gasPrice": w3.eth.gas_price, "chainId": w3.eth.chain_id}
    signed = w3.eth.account.sign_transaction(tx, pk)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash = w3.to_hex(txh)
    print(f"[Raffle] Gravity entry tx: {tx_hash}")
    rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=180)
    if rcpt["status"] != 1:
        raise RuntimeError(f"raffle entry tx reverted: {tx_hash}")
    # confirm participation on Gravity
    participate(campaign_id, "GRAVITY_ALPHA", nonce_sig, tx_hash, vid, token)
    print(f"[Raffle] ✅ Entered raffle {campaign_id} (verifyID {vid}, tx {tx_hash})")
    return {"tx": tx_hash, "verifyID": vid}
