# Phase 2 — Category Mapping Strategy: Implementation Specification

> **Version**: 1.0  
> **Status**: Draft  
> **Target Release**: v0.2.0  
> **Plan Reference**: `.opencode/plans/phase-02-category-mapping.md`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Target Categories](#2-target-categories)
3. [Inference Architecture](#3-inference-architecture)
4. [Tier 1: Raw API Category Map](#4-tier-1-raw-api-category-map)
5. [Tier 2: Event Category Inheritance](#5-tier-2-event-category-inheritance)
6. [Tier 3: Keyword Classifier](#6-tier-3-keyword-classifier)
7. [`infer_category()` — Complete Implementation](#7-infer_category--complete-implementation)
8. [Schema Change: `mapped_category` Column](#8-schema-change-mapped_category-column)
9. [Integration into `merge_markets` Transformer](#9-integration-into-merge_markets-transformer)
10. [Integration into `export_markets` Exporter](#10-integration-into-export_markets-exporter)
11. [Alembic Migration](#11-alembic-migration)
12. [Backfill Script](#12-backfill-script)
13. [Test Matrix](#13-test-matrix)
14. [Acceptance Criteria](#14-acceptance-criteria)
15. [Edge Cases & Known Issues](#15-edge-cases--known-issues)

---

## 1. Overview

95.2% of markets in the database have `category IS NULL` in the raw Gamma API payload. Phase 2 introduces a deterministic 3-tier classifier that assigns every market to one of 8 canonical categories (defined in `MarketCategory` enum). The classified value is stored in a new `mapped_category` column on the `markets` table, separate from the raw API `category` field.

### Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Storage | New `mapped_category` column on `markets` | Preserves raw `category` for audit; single source of truth for downstream analytics |
| Classification point | `merge_markets` transformer (load time) | Classify once at ingestion; all consumers see the same category |
| Classification approach | Deterministic rules, no ML | Simpler to debug, audit, and maintain; no training data required |
| Fallback ordering | Tier 1 → Tier 2 → Tier 3 | Highest-confidence match first; keyword classifier is the broadest net |

### Data Flow

```
Gamma API Response
    │
    ├── market.category   ──── Tier 1 (direct map) ──┐
    │                                                 │
    ├── event.category    ──── Tier 2 (inherit)  ─────┤
    │                                                 │
    └── market.question   ──── Tier 3 (keywords) ─────┤
                                                      │
                                                      ▼
                                             mapped_category
                                             (stored in DB)
```

---

## 2. Target Categories

Exactly 8 categories, defined in `/app/models/enums.py`:

| Enum Value | Canonical Name | Domain |
|---|---|---|
| `Politics` | Politics | Elections, candidates, policy, legislation |
| `Crypto` | Crypto | Blockchain, tokens, DeFi, NFTs, Web3 |
| `Sports` | Sports | Professional & collegiate sports, esports |
| `Economics` | Economics | Macroeconomics, markets, trade, employment |
| `Technology` | Technology | Software, hardware, tech companies, space |
| `AI` | AI | Artificial intelligence, LLMs, robotics |
| `Geopolitics` | Geopolitics | International relations, conflicts, sanctions |
| `Entertainment` | Entertainment | Film, music, television, celebrity, awards |

All returned values from `infer_category()` MUST match these strings exactly (case-sensitive).

---

## 3. Inference Architecture

### 3.1 Function Signature

```python
def infer_category(
    question: str,
    raw_category: str | None = None,
    event_category: str | None = None,
) -> str | None:
```

**Parameters:**

| Parameter | Source | Description |
|---|---|---|
| `question` | `market.question` | The market's question text (e.g., "Will BTC reach $100k by Dec 2025?") |
| `raw_category` | `market.category` | Raw category from Gamma API (typically NULL, rarely populated) |
| `event_category` | `events.category` | Category inherited from the parent event row (typically NULL) |

**Returns:** One of the 8 canonical category strings, or `None` if unclassifiable.

### 3.2 Tier Logic

1. **Tier 1**: If `raw_category` is not NULL and exists as a key in `RAW_CATEGORY_MAP`, return the mapped value.
2. **Tier 2**: If Tier 1 returned nothing and `event_category` is not NULL and exists as a key in `RAW_CATEGORY_MAP`, return the mapped value.
3. **Tier 3**: If both tiers returned nothing, run keyword classification on `question`. Return the first matching category.
4. **Fallback**: Return `None` if no tier matched.

### 3.3 Expected Coverage

| Tier | Source | Est. Population | Est. Coverage |
|---|---|---|---|
| 1 | Raw API category | ~4.8% of markets | 100% of those with non-null raw category |
| 2 | Event category | ~0.5% of markets | ~80% of those with non-null event category |
| 3 | Keyword classifier | ~94.7% of markets | ~95% of those previously NULL |
| **Total** | | **100%** | **≥ 95% classified** |

---

## 4. Tier 1: Raw API Category Map

### 4.1 Mapping Dictionary

This maps every known raw API category string to its canonical category. Each raw value observed in production data should be listed here to guarantee 0 loss on Tier 1.

```python
RAW_CATEGORY_MAP: dict[str, str] = {
    # ── Sports ────────────────────────────────────────────────────────
    "Sports": "Sports",
    "NBA Playoffs": "Sports",
    "Olympics": "Sports",
    "Soccer": "Sports",
    "Football": "Sports",
    "Baseball": "Sports",
    "Basketball": "Sports",
    "Tennis": "Sports",
    "MMA": "Sports",
    "Boxing": "Sports",
    "Hockey": "Sports",
    "Golf": "Sports",
    "Racing": "Sports",
    "Cricket": "Sports",
    "Rugby": "Sports",
    "Horse Racing": "Sports",
    "Chess": "Sports",
    "Poker": "Sports",
    "Esports": "Sports",
    "Winter Sports": "Sports",

    # ── Crypto ────────────────────────────────────────────────────────
    "Crypto": "Crypto",
    "NFTs": "Crypto",
    "Bitcoin": "Crypto",
    "Ethereum": "Crypto",
    "DeFi": "Crypto",
    "Web3": "Crypto",

    # ── Politics ──────────────────────────────────────────────────────
    "Politics": "Politics",
    "US-current-affairs": "Politics",
    "US Elections": "Politics",
    "UK Politics": "Politics",

    # ── Geopolitics ───────────────────────────────────────────────────
    "Global Politics": "Geopolitics",
    "Ukraine & Russia": "Geopolitics",
    "Middle East": "Geopolitics",
    "China": "Geopolitics",
    "International Relations": "Geopolitics",

    # ── Economics ─────────────────────────────────────────────────────
    "Business": "Economics",
    "Coronavirus": "Economics",
    "Economy": "Economics",
    "Markets": "Economics",
    "Finance": "Economics",

    # ── Technology ────────────────────────────────────────────────────
    "Science": "Technology",
    "Tech": "Technology",
    "Space": "Technology",
    "Technology": "Technology",

    # ── Entertainment ─────────────────────────────────────────────────
    "Pop-Culture": "Entertainment",
    "Art": "Entertainment",
    "Movies": "Entertainment",
    "Music": "Entertainment",
    "TV": "Entertainment",
    "Celebrity": "Entertainment",
    "Gaming": "Entertainment",
}
```

### 4.2 Design Note

The map uses **exact string matching** (no partial matching, no lowercasing). This is intentional: raw API categories are controlled strings from a finite set. If a new raw category appears in production, it must be added to this dict. Add a `log.warning` when an unrecognized raw category is encountered so the operator can update the map.

---

## 5. Tier 2: Event Category Inheritance

### 5.1 Logic

Tier 2 applies the same `RAW_CATEGORY_MAP` to the `event_category` parameter. This handles markets that lack their own category but are linked to an event that has one.

### 5.2 Data Pipeline Fix Required

**Bug in data loaders**: Both `load_active_markets.py` and `load_resolved_markets.py` set:

```python
"event_category": m.get("category"),  # BUG: this is the market's category, not the event's
```

This should instead extract the category from the event object:

```python
"event_category": event.get("category") if event else None,
```

**Fix required in both loaders** before Tier 2 will function correctly. The fix is in Section 9.1.

### 5.3 Fallback Behavior

If `event_category` is not NULL but not found in `RAW_CATEGORY_MAP`, fall through to Tier 3 (do not return None at Tier 2). The unrecognized value should be logged.

---

## 6. Tier 3: Keyword Classifier

### 6.1 Design Rules

- **Ordered matching**: Rules are evaluated top-to-bottom. The first match wins.
- **Case-insensitive**: All comparisons are done on `question.lower()`.
- **Substring matching**: Uses `in` operator (not regex, not word boundaries). This is intentionally broad to maximize coverage.
- **Single-pass**: Each question is scanned once with no backtracking.
- **Prioritization**: Categories with more specific/less ambiguous keywords are checked first. Politics and Geopolitics are checked before broader categories like Entertainment.

### 6.2 Complete Keyword Lists

```python
def _classify_by_keywords(question: str) -> str | None:
    """Classify a market question using ordered keyword rules."""
    q = question.lower()

    # ── Politics (checked first — most specific signals) ──────────────
    POLITICS_KW = [
        # US politics
        "president", "election", "vote", "voter", "voting",
        "democrat", "republican", "senate", "senator", "congress",
        "congressional", "governor", "candidate", "primary",
        "trump", "biden", "harris", "newsom", "desantis",
        "pelosi", "schumer", "mcconnell", "aoc", "ocasio-cortez",
        "supreme court", "justice", "scotus",
        "electoral", "swing state", "battleground",
        "gop", "dnc", "rnc", "midterm", "impeach",
        "cabinet", "administration", "white house",
        "filibuster", "legislation", "bill passes", "executive order",
        "inauguration", "state of the union",
        "campaign", "poll", "approval rating",
        # UK / European politics
        "prime minister", "chancellor", "parliament",
        "labour party", "conservative party", "tory", "brexit",
        "uk general election", "snap election",
        "european union", "eu commission",
        "macron", "scholz", "meloni", "modi",
        # Generic political
        "political party", "elected", "presidential",
        "senate seat", "house seat", "mayoral",
    ]

    # ── Geopolitics (checked before Economics/Sports) ─────────────────
    GEOPOLITICS_KW = [
        "war", "sanction", "military", "nato", "invasion",
        "nuclear", "treaty", "ceasefire", "refugee",
        "ukraine", "russia", "putin", "zelensky",
        "iran", "israel", "gaza", "hamas", "hezbollah",
        "china", "xi jinping", "taiwan", "south china sea",
        "north korea", "kim jong", "missile test",
        "armed conflict", "civil war", "insurgent",
        "terrorist", "terrorism", "geopolitical",
        "annex", "sovereignty", "territorial dispute",
        "united nations", "un security council", "veto",
        "foreign policy", "diplomatic", "embassy",
        "border dispute", "military aid", "arms deal",
        "nuclear weapon", "denuclearization",
        "peace deal", "peace treaty", "armistice",
    ]

    # ── Crypto (checked next — strong signal words) ───────────────────
    CRYPTO_KW = [
        "bitcoin", "btc", "ethereum", "eth", "crypto",
        "solana", "sol", "defi", "nft", "blockchain",
        "polygon", "matic", "avalanche", "avax",
        "chainlink", "link", "uniswap", "uni",
        "token", "web3", "smart contract",
        "ethereum merge", "proof of stake", "proof of work",
        "layer 2", "l2", "rollup", "zksync", "arbitrum", "optimism",
        "bitcoin halving", "mining difficulty", "hash rate",
        "stablecoin", "usdc", "usdt", "dai", "fip",
        "binance", "bsc", "coinbase", "exchange",
        "crypto regulation", "sec crypto", "etf crypto",
        "bitcoin etf", "ethereum etf",
        "altcoin", "memecoin", "shitcoin",
        "wallet", "cold storage", "self-custody",
        "dao", "governance token", "airdrop",
        "liquidity pool", "amm", "yield farming", "staking",
        "metaverse", "virtual land", "decentraland", "sandbox",
        "cryptocurrency",
    ]

    # ── Sports (broad but well-defined) ────────────────────────────────
    SPORTS_KW = [
        # Leagues
        "nfl", "nba", "mlb", "nhl", "mls", "wnba", "ncaa",
        "premier league", "epl", "laliga", "serie a", "bundesliga",
        "champions league", "uefa", "fifa", "world cup",
        "super bowl", "super bowl", "superbowl",
        "world series", "stanley cup", "nba finals",
        "masters", "grand slam", "wimbledon", "us open",
        "olympic", "paralympic",
        # Sports
        "soccer", "football", "basketball", "baseball",
        "hockey", "tennis", "golf", "boxing", "mma",
        "ufc", "wrestling", "rugby", "cricket",
        "horse racing", "formula 1", "f1", "nascar", "motogp",
        "cycling", "tour de france", "swimming", "track and field",
        "athletics",
        # Game events
        " vs ", "fight", "match", "race", "game",
        "playoff", "quarterfinal", "semifinal", "final",
        "champion", "championship", "title match",
        "goal", "touchdown", "homerun", "home run",
        "run", "point", "score", "win", "defeat",
        "draft pick", "trade", "signing", "free agent",
        "coach", "manager", "head coach",
        "quarterback", "pitcher", "forward",
        "season", "regular season", "postseason",
        "over/under", "spread", "moneyline",
        "to win", "winning team",
        # Esports
        "esports", "league of legends", "dota", "counter-strike",
        "valorant", "overwatch", "fortnite",
        # Well-known athletes (non-political)
        "lebron", "curry", "messi", "ronaldo", "mbappe",
        "mahomes", "brady", "rodgers",
    ]

    # ── AI (checked before generic Technology) ─────────────────────────
    AI_KW = [
        "artificial intelligence", "ai ", " ai", "ai-",
        "gpt", "chatgpt", "openai", "llm", "large language model",
        "agi", "deep learning", "neural network",
        "machine learning", "ml model",
        "generative ai", "genai", "diffusion model",
        "transformer", "bert", "claude", "gemini", "copilot",
        "midjourney", "dall-e", "stable diffusion",
        "ai regulation", "ai safety", "alignment",
        "ai agent", "autonomous agent",
        "rag", "retrieval augmented",
        "fine-tuning", "instruction tuning",
        "hallucination", "prompt injection",
        "robot", "robotics", "self-driving",
        "autonomous vehicle", "lidar",
        "computer vision", "natural language processing",
        "speech recognition", "text-to-speech",
        "turing test", "singularity",
    ]

    # ── Technology (generic tech + space) ─────────────────────────────
    TECHNOLOGY_KW = [
        # Companies
        "apple", "google", "alphabet", "microsoft", "meta",
        "amazon", "tesla", "nvidia", "intel", "amd",
        "netflix", "twitter", "x.com", "x corp",
        # Hardware
        "iphone", "ipad", "macbook", "vision pro",
        "android", "samsung", "playstation", "xbox", "nintendo",
        "chip", "semiconductor", "processor", "gpu", "cpu",
        "5g", "6g", "quantum computing",
        "smartphone", "tablet", "wearable",
        # Software
        "software", "operating system", "ios", "macos", "windows",
        "linux", "open source", "kubernetes",
        "saas", "cloud computing", "aws", "azure", "gcp",
        "cybersecurity", "hack", "ransomware", "data breach",
        # Space
        "space", "rocket", "launch", "satellite",
        "nasa", "spacex", "starship", "falcon",
        "blue origin", "virgin galactic",
        "mars", "moon landing", "lunar",
        "space station", "iss", "orbit",
        # Startups / Business
        "ipo", "startup", "acquisition", "merger",
        "venture capital", "funding round", "series a",
        "unicorn", "valuation", "buyout",
        # Other tech
        "tech", "technology", "digital", "innovation",
        "patent", "copyright", "intellectual property",
        "drone", "autonomous",
    ]

    # ── Economics (specific financial/macro signals) ──────────────────
    ECONOMICS_KW = [
        # Macro
        "inflation", "gdp", "gross domestic product",
        "interest rate", "fed", "federal reserve",
        "recession", "depression", "economic growth",
        "unemployment", "jobs report", "nonfarm payrolls",
        "cpi", "consumer price index", "ppi",
        "trade deficit", "trade surplus", "tariff",
        "supply chain", "shortage",
        # Markets
        "stock market", "s&p", "s&p 500", "nasdaq", "dow jones",
        "nyse", "bull market", "bear market",
        "market crash", "correction", "volatility",
        "vix", "fear index",
        # Fiscal / Monetary
        "quantitative easing", "tightening", "rate hike",
        "rate cut", "monetary policy", "fiscal policy",
        "government spending", "stimulus", "debt ceiling",
        "default", "sovereign debt", "bond yield",
        "treasury", "treasury yield",
        # Corporate
        "earnings", "revenue", "profit", "quarterly report",
        "dividend", "buyback", "share price",
        "market cap", "market capitalization",
        # Commodities
        "oil price", "gold price", "commodity",
        "cryptocurrency as economics",  # intentionally weak; crypto catches most
        # Trade
        "trade war", "export", "import", "protectionism",
        "wto", "tariff", "trade deal",
    ]

    # ── Entertainment (checked last — broadest category) ──────────────
    ENTERTAINMENT_KW = [
        # Film / TV
        "movie", "film", "oscar", "academy award", "emmy",
        "golden globe", "grammy", "tony", "brit award",
        "box office", "blockbuster", "premiere",
        "actor", "actress", "director", "producer",
        "netflix", "disney", "hbo", "hulu", "amazon prime",
        "streaming", "tv show", "television", "episode",
        "season finale", "series", "canceled", "renewed",
        "marvel", "dc", "star wars", "avatar",
        # Music
        "album", "concert", "tour", "spotify",
        "billboard", "chart", "number one", "platinum record",
        "singer", "rapper", "musician", "band",
        # Celebrity / Pop Culture
        "celebrity", "influencer", "tiktok", "instagram",
        "kardashian", "royal family", "king charles",
        "wedding", "divorce", "scandal",
        "reality tv", "bachelor", "survivor",
        "award", "red carpet", "festival",
        "cannes", "sundance", "coachella",
        # Gaming (non-esports)
        "video game", "gaming", "console",
        "grand theft auto", "gta",
        "minecraft", "nintendo switch",
        # Broad entertainment
        "entertainment", "pop culture", "pop-culture",
        "porn", "onlyfans",
        "comic con", "anime", "manga",
    ]

    # ── Evaluate rules in order ───────────────────────────────────────
    if any(kw in q for kw in POLITICS_KW):
        return "Politics"

    if any(kw in q for kw in GEOPOLITICS_KW):
        return "Geopolitics"

    if any(kw in q for kw in CRYPTO_KW):
        return "Crypto"

    if any(kw in q for kw in SPORTS_KW):
        return "Sports"

    if any(kw in q for kw in AI_KW):
        return "AI"

    if any(kw in q for kw in TECHNOLOGY_KW):
        return "Technology"

    if any(kw in q for kw in ECONOMICS_KW):
        return "Economics"

    if any(kw in q for kw in ENTERTAINMENT_KW):
        return "Entertainment"

    return None
```

---

## 7. `infer_category()` — Complete Implementation

This is the single callable function. Place it in a new module at:

```
magic/default_repo/transformers/category_classifier.py
```

This keeps the classifier isolated and testable independently of the ETL pipeline.

```python
"""
Category classifier for Polymarket markets.

3-tier fallback strategy:
  1. Map raw API category via RAW_CATEGORY_MAP
  2. Inherit event category via RAW_CATEGORY_MAP
  3. Keyword classification on market question text

Usage:
    from transformers.category_classifier import infer_category

    category = infer_category(
        question="Will BTC reach $100k by Dec 2025?",
        raw_category=None,
        event_category=None,
    )
    # Returns: "Crypto"
"""

import logging

logger = logging.getLogger(__name__)

# ── Raw API → Canonical Category Map ──────────────────────────────────

RAW_CATEGORY_MAP: dict[str, str] = {
    # Sports
    "Sports": "Sports",
    "NBA Playoffs": "Sports",
    "Olympics": "Sports",
    "Soccer": "Sports",
    "Football": "Sports",
    "Baseball": "Sports",
    "Basketball": "Sports",
    "Tennis": "Sports",
    "MMA": "Sports",
    "Boxing": "Sports",
    "Hockey": "Sports",
    "Golf": "Sports",
    "Racing": "Sports",
    "Cricket": "Sports",
    "Rugby": "Sports",
    "Horse Racing": "Sports",
    "Chess": "Sports",
    "Poker": "Sports",
    "Esports": "Sports",
    "Winter Sports": "Sports",
    # Crypto
    "Crypto": "Crypto",
    "NFTs": "Crypto",
    "Bitcoin": "Crypto",
    "Ethereum": "Crypto",
    "DeFi": "Crypto",
    "Web3": "Crypto",
    # Politics
    "Politics": "Politics",
    "US-current-affairs": "Politics",
    "US Elections": "Politics",
    "UK Politics": "Politics",
    # Geopolitics
    "Global Politics": "Geopolitics",
    "Ukraine & Russia": "Geopolitics",
    "Middle East": "Geopolitics",
    "China": "Geopolitics",
    "International Relations": "Geopolitics",
    # Economics
    "Business": "Economics",
    "Coronavirus": "Economics",
    "Economy": "Economics",
    "Markets": "Economics",
    "Finance": "Economics",
    # Technology
    "Science": "Technology",
    "Tech": "Technology",
    "Space": "Technology",
    "Technology": "Technology",
    # Entertainment
    "Pop-Culture": "Entertainment",
    "Art": "Entertainment",
    "Movies": "Entertainment",
    "Music": "Entertainment",
    "TV": "Entertainment",
    "Celebrity": "Entertainment",
    "Gaming": "Entertainment",
}


def _apply_raw_map(value: str | None) -> str | None:
    """Map a raw category string to its canonical form.

    Returns None if value is None or not in the map.
    Logs a warning for unrecognized values to alert operators.
    """
    if value is None:
        return None
    mapped = RAW_CATEGORY_MAP.get(value)
    if mapped is None:
        logger.warning("Unrecognized raw category: %r — consider adding to RAW_CATEGORY_MAP", value)
    return mapped


# ── Keyword Lists ─────────────────────────────────────────────────────

# Each list contains lowercase substrings matched against question.lower().
# Rules are ordered: first match wins. Keep lists focused and unambiguous.

POLITICS_KW = [
    "president", "election", "vote", "voter", "voting",
    "democrat", "republican", "senate", "senator", "congress",
    "congressional", "governor", "candidate", "primary",
    "trump", "biden", "harris", "newsom", "desantis",
    "pelosi", "schumer", "mcconnell", "aoc", "ocasio-cortez",
    "supreme court", "justice", "scotus",
    "electoral", "swing state", "battleground",
    "gop", "dnc", "rnc", "midterm", "impeach",
    "cabinet", "administration", "white house",
    "filibuster", "legislation", "bill passes", "executive order",
    "inauguration", "state of the union",
    "campaign", "poll", "approval rating",
    "prime minister", "chancellor", "parliament",
    "labour party", "conservative party", "tory", "brexit",
    "uk general election", "snap election",
    "european union", "eu commission",
    "macron", "scholz", "meloni", "modi",
    "political party", "elected", "presidential",
    "senate seat", "house seat", "mayoral",
]

GEOPOLITICS_KW = [
    "war", "sanction", "military", "nato", "invasion",
    "nuclear", "treaty", "ceasefire", "refugee",
    "ukraine", "russia", "putin", "zelensky",
    "iran", "israel", "gaza", "hamas", "hezbollah",
    "china", "xi jinping", "taiwan", "south china sea",
    "north korea", "kim jong", "missile test",
    "armed conflict", "civil war", "insurgent",
    "terrorist", "terrorism", "geopolitical",
    "annex", "sovereignty", "territorial dispute",
    "united nations", "un security council", "veto",
    "foreign policy", "diplomatic", "embassy",
    "border dispute", "military aid", "arms deal",
    "nuclear weapon", "denuclearization",
    "peace deal", "peace treaty", "armistice",
]

CRYPTO_KW = [
    "bitcoin", "btc", "ethereum", "eth", "crypto",
    "solana", "sol", "defi", "nft", "blockchain",
    "polygon", "matic", "avalanche", "avax",
    "chainlink", "link", "uniswap", "uni",
    "token", "web3", "smart contract",
    "ethereum merge", "proof of stake", "proof of work",
    "layer 2", "l2", "rollup", "zksync", "arbitrum", "optimism",
    "bitcoin halving", "mining difficulty", "hash rate",
    "stablecoin", "usdc", "usdt", "dai", "fip",
    "binance", "bsc", "coinbase", "exchange",
    "crypto regulation", "sec crypto", "etf crypto",
    "bitcoin etf", "ethereum etf",
    "altcoin", "memecoin", "shitcoin",
    "wallet", "cold storage", "self-custody",
    "dao", "governance token", "airdrop",
    "liquidity pool", "amm", "yield farming", "staking",
    "metaverse", "virtual land", "decentraland", "sandbox",
    "cryptocurrency",
]

SPORTS_KW = [
    "nfl", "nba", "mlb", "nhl", "mls", "wnba", "ncaa",
    "premier league", "epl", "laliga", "serie a", "bundesliga",
    "champions league", "uefa", "fifa", "world cup",
    "super bowl", "superbowl",
    "world series", "stanley cup", "nba finals",
    "masters", "grand slam", "wimbledon", "us open",
    "olympic", "paralympic",
    "soccer", "football", "basketball", "baseball",
    "hockey", "tennis", "golf", "boxing", "mma",
    "ufc", "wrestling", "rugby", "cricket",
    "horse racing", "formula 1", "f1", "nascar", "motogp",
    "cycling", "tour de france", "swimming", "track and field",
    "athletics",
    " vs ", "fight", "match", "race", "game",
    "playoff", "quarterfinal", "semifinal", "final",
    "champion", "championship", "title match",
    "goal", "touchdown", "homerun", "home run",
    "run", "point", "score", "win", "defeat",
    "draft pick", "trade", "signing", "free agent",
    "coach", "manager", "head coach",
    "quarterback", "pitcher", "forward",
    "season", "regular season", "postseason",
    "over/under", "spread", "moneyline",
    "to win", "winning team",
    "esports", "league of legends", "dota", "counter-strike",
    "valorant", "overwatch", "fortnite",
    "lebron", "curry", "messi", "ronaldo", "mbappe",
    "mahomes", "brady", "rodgers",
]

AI_KW = [
    "artificial intelligence", "ai ", " ai", "ai-",
    "gpt", "chatgpt", "openai", "llm", "large language model",
    "agi", "deep learning", "neural network",
    "machine learning", "ml model",
    "generative ai", "genai", "diffusion model",
    "transformer", "bert", "claude", "gemini", "copilot",
    "midjourney", "dall-e", "stable diffusion",
    "ai regulation", "ai safety", "alignment",
    "ai agent", "autonomous agent",
    "rag", "retrieval augmented",
    "fine-tuning", "instruction tuning",
    "hallucination", "prompt injection",
    "robot", "robotics", "self-driving",
    "autonomous vehicle", "lidar",
    "computer vision", "natural language processing",
    "speech recognition", "text-to-speech",
    "turing test", "singularity",
]

TECHNOLOGY_KW = [
    "apple", "google", "alphabet", "microsoft", "meta",
    "amazon", "tesla", "nvidia", "intel", "amd",
    "netflix", "twitter", "x.com", "x corp",
    "iphone", "ipad", "macbook", "vision pro",
    "android", "samsung", "playstation", "xbox", "nintendo",
    "chip", "semiconductor", "processor", "gpu", "cpu",
    "5g", "6g", "quantum computing",
    "smartphone", "tablet", "wearable",
    "software", "operating system", "ios", "macos", "windows",
    "linux", "open source", "kubernetes",
    "saas", "cloud computing", "aws", "azure", "gcp",
    "cybersecurity", "hack", "ransomware", "data breach",
    "space", "rocket", "launch", "satellite",
    "nasa", "spacex", "starship", "falcon",
    "blue origin", "virgin galactic",
    "mars", "moon landing", "lunar",
    "space station", "iss", "orbit",
    "ipo", "startup", "acquisition", "merger",
    "venture capital", "funding round", "series a",
    "unicorn", "valuation", "buyout",
    "tech", "technology", "digital", "innovation",
    "patent", "copyright", "intellectual property",
    "drone", "autonomous",
]

ECONOMICS_KW = [
    "inflation", "gdp", "gross domestic product",
    "interest rate", "fed", "federal reserve",
    "recession", "depression", "economic growth",
    "unemployment", "jobs report", "nonfarm payrolls",
    "cpi", "consumer price index", "ppi",
    "trade deficit", "trade surplus", "tariff",
    "supply chain", "shortage",
    "stock market", "s&p", "s&p 500", "nasdaq", "dow jones",
    "nyse", "bull market", "bear market",
    "market crash", "correction", "volatility",
    "vix", "fear index",
    "quantitative easing", "tightening", "rate hike",
    "rate cut", "monetary policy", "fiscal policy",
    "government spending", "stimulus", "debt ceiling",
    "default", "sovereign debt", "bond yield",
    "treasury", "treasury yield",
    "earnings", "revenue", "profit", "quarterly report",
    "dividend", "buyback", "share price",
    "market cap", "market capitalization",
    "oil price", "gold price", "commodity",
    "trade war", "export", "import", "protectionism",
    "wto", "trade deal",
]

ENTERTAINMENT_KW = [
    "movie", "film", "oscar", "academy award", "emmy",
    "golden globe", "grammy", "tony", "brit award",
    "box office", "blockbuster", "premiere",
    "actor", "actress", "director", "producer",
    "netflix", "disney", "hbo", "hulu", "amazon prime",
    "streaming", "tv show", "television", "episode",
    "season finale", "series", "canceled", "renewed",
    "marvel", "dc", "star wars", "avatar",
    "album", "concert", "tour", "spotify",
    "billboard", "chart", "number one", "platinum record",
    "singer", "rapper", "musician", "band",
    "celebrity", "influencer", "tiktok", "instagram",
    "kardashian", "royal family", "king charles",
    "wedding", "divorce", "scandal",
    "reality tv", "bachelor", "survivor",
    "award", "red carpet", "festival",
    "cannes", "sundance", "coachella",
    "video game", "gaming", "console",
    "grand theft auto", "gta",
    "minecraft", "nintendo switch",
    "entertainment", "pop culture", "pop-culture",
    "porn", "onlyfans",
    "comic con", "anime", "manga",
]


def _classify_by_keywords(question: str) -> str | None:
    """Run ordered keyword matching on a market question.

    First match wins. Case-insensitive via .lower().
    """
    q = question.lower()

    if any(kw in q for kw in POLITICS_KW):
        return "Politics"
    if any(kw in q for kw in GEOPOLITICS_KW):
        return "Geopolitics"
    if any(kw in q for kw in CRYPTO_KW):
        return "Crypto"
    if any(kw in q for kw in SPORTS_KW):
        return "Sports"
    if any(kw in q for kw in AI_KW):
        return "AI"
    if any(kw in q for kw in TECHNOLOGY_KW):
        return "Technology"
    if any(kw in q for kw in ECONOMICS_KW):
        return "Economics"
    if any(kw in q for kw in ENTERTAINMENT_KW):
        return "Entertainment"

    return None


def infer_category(
    question: str,
    raw_category: str | None = None,
    event_category: str | None = None,
) -> str | None:
    """Classify a Polymarket market into one of 8 canonical categories.

    Uses a 3-tier fallback:
      1. Map the market's raw API category (``raw_category``) via CATEGORY_MAP.
      2. Map the parent event's category (``event_category``) via CATEGORY_MAP.
      3. Run keyword classification on the market's ``question`` text.

    Args:
        question: The market's question string (required).
        raw_category: The market's ``category`` field from the Gamma API.
        event_category: The parent event's ``category`` field.

    Returns:
        One of: "Politics", "Crypto", "Sports", "Economics", "Technology",
        "AI", "Geopolitics", "Entertainment".
        Returns ``None`` if the market cannot be classified.
    """
    # Tier 1: Direct API category match
    result = _apply_raw_map(raw_category)
    if result is not None:
        return result

    # Tier 2: Event category inheritance
    result = _apply_raw_map(event_category)
    if result is not None:
        return result

    # Tier 3: Keyword classification on question text
    if question:
        return _classify_by_keywords(question)

    return None
```

---

## 8. Schema Change: `mapped_category` Column

### 8.1 SQL

```sql
ALTER TABLE markets ADD COLUMN mapped_category TEXT;
CREATE INDEX idx_markets_mapped_category ON markets (mapped_category);
```

### 8.2 SQLAlchemy Model Update

In `/app/db/models.py`, add the new column to the `Market` class:

```python
class Market(Base):
    __tablename__ = "markets"

    id = Column(Text, primary_key=True)
    question = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    mapped_category = Column(Text, nullable=True)  # NEW: inferred category
    event_id = Column(Text, ForeignKey("events.id"), nullable=True)
    # ... (existing columns unchanged)

    __table_args__ = (
        Index("idx_markets_category", "category"),
        Index("idx_markets_mapped_category", "mapped_category"),  # NEW
        Index("idx_markets_created_at", "created_at"),
        Index("idx_markets_event_id", "event_id"),
    )
```

### 8.3 Design Notes

- `mapped_category` is nullable (`TEXT`). This preserves the ability to distinguish "unclassified" from "not yet processed."
- The raw `category` column is **preserved unchanged** for audit and debugging. Downstream analytics should read `mapped_category` exclusively.
- The index on `mapped_category` supports efficient `WHERE mapped_category = 'Sports'` queries in the per-category analytics pipeline.

---

## 9. Integration into `merge_markets` Transformer

### 9.1 Fix Event Category in Data Loaders

**File**: `magic/default_repo/data_loaders/load_active_markets.py`

**Change**: Replace the `event_category` assignment (lines 91 and 98) to use the event object's category, not the market's category.

Current (buggy):
```python
"event_category": m.get("category"),   # line 91
# and later:
"category": m.get("category"),         # line 98 — correct
```

Fixed:
```python
"event_category": event.get("category") if event else None,  # line 91 — now reads from event
"category": m.get("category"),                                # line 98 — unchanged, correct
```

**File**: `magic/default_repo/data_loaders/load_resolved_markets.py`

Same fix: line 91 change `m.get("category")` to `event.get("category") if event else None`.

### 9.2 Add `infer_category()` Call in Transformer

**File**: `magic/default_repo/transformers/merge_markets.py`

**Changes**:

1. Add import at top of file:
```python
from transformers.category_classifier import infer_category
```

2. After the `markets` DataFrame is built (after line 40, before `markets = markets.reset_index(drop=True)`), add the classification step:

```python
    # ── Category inference ────────────────────────────────────────────
    # Build lookup: event_id → event_category for Tier 2
    event_categories = {}
    if not events.empty:
        event_categories = dict(zip(events["id"], events["category"]))

    def classify_row(row) -> str | None:
        return infer_category(
            question=row["question"],
            raw_category=row["category"],
            event_category=event_categories.get(row["event_id"]),
        )

    markets["mapped_category"] = markets.apply(classify_row, axis=1)

    # Log coverage stats
    total = len(markets)
    classified = markets["mapped_category"].notna().sum()
    pct = (classified / total * 100) if total > 0 else 0
    print(f"Category classification: {classified}/{total} ({pct:.1f}%)")
```

### 9.3 Updated `merge_markets.py` (Full File)

```python
import pandas as pd
from pandas import DataFrame
from transformers.category_classifier import infer_category

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform_df(active: DataFrame, resolved: DataFrame, *args, **kwargs) -> dict:
    combined = DataFrame()
    if not active.empty:
        combined = pd.concat([combined, active], ignore_index=True)
    if not resolved.empty:
        combined = pd.concat([combined, resolved], ignore_index=True)

    if combined.empty:
        return {"events": DataFrame(), "markets": DataFrame(), "outcomes": DataFrame()}

    before = len(combined)
    combined = combined.drop_duplicates(subset=["market_id"], keep="last")
    removed = before - len(combined)
    print(f"Combined {len(active)} active + {len(resolved)} resolved markets, removed {removed} duplicates")

    no_event = combined["event_id"].isna().sum()
    if no_event:
        print(f"Warning: {no_event} markets have no event_id — skipping event rows for those")
    events = combined[combined["event_id"].notna()][["event_id", "event_title", "event_slug", "event_category",
                                                      "event_start_date", "event_end_date", "event_closed"]].drop_duplicates(subset=["event_id"]).copy()
    events.columns = ["id", "title", "slug", "category", "start_date", "end_date", "closed"]
    events = events.reset_index(drop=True)

    markets = combined[["market_id", "condition_id", "question", "category", "event_id", "event_slug",
                        "volume_usd", "liquidity_usd", "close_time", "created_at",
                        "resolved_at", "winning_outcome"]].drop_duplicates(subset=["market_id"]).copy()
    markets.columns = ["id", "condition_id", "question", "category", "event_id", "event_slug",
                       "volume_usd", "liquidity_usd", "close_time", "created_at",
                       "resolved_at", "winning_outcome"]

    # ── Category inference ────────────────────────────────────────────
    event_categories = {}
    if not events.empty:
        event_categories = dict(zip(events["id"], events["category"]))

    def classify_row(row) -> str | None:
        return infer_category(
            question=row["question"],
            raw_category=row["category"],
            event_category=event_categories.get(row["event_id"]),
        )

    markets["mapped_category"] = markets.apply(classify_row, axis=1)

    total = len(markets)
    classified = markets["mapped_category"].notna().sum()
    pct = (classified / total * 100) if total > 0 else 0
    print(f"Category classification: {classified}/{total} ({pct:.1f}%)")

    markets = markets.reset_index(drop=True)

    outcome_rows = []
    for _, row in combined.iterrows():
        outcomes = row.get("outcomes")
        if isinstance(outcomes, list):
            for o in outcomes:
                if isinstance(o, dict):
                    outcome_rows.append({
                        "id": o.get("id"),
                        "market_id": row["market_id"],
                        "label": o.get("label"),
                        "price": o.get("price"),
                        "winner": o.get("winner"),
                    })
    outcomes = DataFrame(outcome_rows).drop_duplicates(subset=["id"]) if outcome_rows else DataFrame(
        columns=["id", "market_id", "label", "price", "winner"]
    )

    print(f"Result: {len(events)} events, {len(markets)} markets, {len(outcomes)} outcomes")
    return {"events": events, "markets": markets, "outcomes": outcomes}


@test
def test_output(result) -> None:
    assert "events" in result, "Missing events"
    assert "markets" in result, "Missing markets"
    assert "outcomes" in result, "Missing outcomes"
```

### 9.4 Important: Column Name Conflict

The `events` DataFrame renames `event_category` to `category`. The `markets` DataFrame also has a `category` column (the raw API category). These are distinct DataFrames returned in the same dict — the column name collision is **not a problem** because they are independent structures. The transformer returns `{"events": events_df, "markets": markets_df, "outcomes": outcomes_df}`.

---

## 10. Integration into `export_markets` Exporter

### 10.1 Changes to `upsert_markets()`

**File**: `magic/default_repo/data_exporters/export_markets.py`

Three changes:

1. Add `mapped_category` to the INSERT column list.
2. Add `mapped_category` to the VALUES parameter dict.
3. Add `mapped_category` to the ON CONFLICT DO UPDATE SET clause.

### 10.2 Updated `upsert_markets()` Function

```python
def upsert_markets(engine, df: DataFrame):
    if df.empty:
        return
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO markets (id, condition_id, question, category, mapped_category,
                                         event_id, event_slug,
                                         volume_usd, liquidity_usd, close_time,
                                         created_at, resolved_at, winning_outcome)
                    VALUES (:id, :condition_id, :question, :category, :mapped_category,
                            :event_id, :event_slug,
                            :volume_usd, :liquidity_usd, :close_time,
                            :created_at, :resolved_at, :winning_outcome)
                    ON CONFLICT (id) DO UPDATE SET
                        condition_id = EXCLUDED.condition_id,
                        question = EXCLUDED.question,
                        category = EXCLUDED.category,
                        mapped_category = EXCLUDED.mapped_category,
                        event_id = EXCLUDED.event_id,
                        event_slug = EXCLUDED.event_slug,
                        volume_usd = EXCLUDED.volume_usd,
                        liquidity_usd = EXCLUDED.liquidity_usd,
                        close_time = EXCLUDED.close_time,
                        created_at = EXCLUDED.created_at,
                        resolved_at = EXCLUDED.resolved_at,
                        winning_outcome = EXCLUDED.winning_outcome
                """),
                {
                    "id": row["id"],
                    "condition_id": row.get("condition_id"),
                    "question": row["question"],
                    "category": row.get("category"),
                    "mapped_category": row.get("mapped_category"),  # NEW
                    "event_id": row.get("event_id"),
                    "event_slug": row.get("event_slug"),
                    "volume_usd": row.get("volume_usd"),
                    "liquidity_usd": row.get("liquidity_usd"),
                    "close_time": row.get("close_time"),
                    "created_at": row.get("created_at"),
                    "resolved_at": row.get("resolved_at"),
                    "winning_outcome": row.get("winning_outcome"),
                },
            )
```

### 10.3 Important: Safe Handling of Missing Column

The `row.get("mapped_category")` call safely returns `None` if the column is absent (e.g., during testing or if the transformer hasn't been updated yet). This ensures backward compatibility with old pipeline runs.

---

## 11. Alembic Migration

### 11.1 Migration File

Create `/Users/antoine/Git/polymarketpricer/alembic/versions/002_add_mapped_category.py`:

```python
"""Add mapped_category column to markets table.

Revision ID: 002
Revises: 001
Create Date: 2026-06-17

This migration adds a new column to store the inferred market category
from the 3-tier classifier. An index is created for efficient filtering.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("mapped_category", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_markets_mapped_category",
        "markets",
        ["mapped_category"],
    )


def downgrade() -> None:
    op.drop_index("idx_markets_mapped_category", table_name="markets")
    op.drop_column("markets", "mapped_category")
```

### 11.2 Execution

```bash
docker compose exec app alembic upgrade head
```

### 11.3 Verify

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'markets' AND column_name = 'mapped_category';
-- Expected: 1 row, data_type = 'text'

SELECT indexname FROM pg_indexes
WHERE tablename = 'markets' AND indexname = 'idx_markets_mapped_category';
-- Expected: 1 row
```

---

## 12. Backfill Script

### 12.1 Script: `scripts/backfill_categories.py`

This script classifies all existing markets that have `mapped_category IS NULL` and updates them in bulk. It can be run after the migration is applied and the new ETL code is deployed.

```python
#!/usr/bin/env python3
"""Backfill mapped_category for all markets where it is NULL.

Usage:
    python scripts/backfill_categories.py [--batch-size 1000] [--dry-run]

Requires:
    - Database running (docker compose up -d)
    - Alembic migration 002 applied (mapped_category column exists)
    - category_classifier module accessible from PYTHONPATH

This script:
    1. Reads all markets with NULL mapped_category in batches.
    2. Loads event categories for Tier 2 classification.
    3. Runs infer_category() on each market.
    4. Updates mapped_category in bulk.
"""

import argparse
import sys
import time
from typing import Generator

from sqlalchemy import create_engine, text

# Add parent dir to path for module discovery
sys.path.insert(0, ".")
from transformers.category_classifier import infer_category  # noqa: E402

DATABASE_URL = "postgresql+psycopg2://app:devpassword@localhost:5432/polymarket"
BATCH_SIZE = 1000


def get_engine():
    return create_engine(DATABASE_URL)


def count_unclassified(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM markets WHERE mapped_category IS NULL")
        ).scalar() or 0


def load_event_categories(engine) -> dict[str, str | None]:
    """Load all event IDs and their categories for Tier 2 lookups."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, category FROM events WHERE category IS NOT NULL")
        ).fetchall()
    return {row[0]: row[1] for row in rows}


def iter_unclassified_batches(engine, batch_size: int) -> Generator[list[tuple], None, None]:
    """Yield batches of (id, question, category, event_id) for markets with NULL mapped_category."""
    offset = 0
    while True:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT m.id, m.question, m.category, m.event_id
                    FROM markets m
                    WHERE m.mapped_category IS NULL
                    ORDER BY m.id
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": batch_size, "offset": offset},
            ).fetchall()
        if not rows:
            break
        yield rows
        offset += batch_size


def update_batch(engine, updates: list[tuple[str, str | None]]) -> None:
    """Update mapped_category for a batch of market IDs.

    Args:
        updates: List of (mapped_category, market_id) tuples.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE markets
                SET mapped_category = data.mapped_category
                FROM (VALUES :updates) AS data(market_id, mapped_category)
                WHERE markets.id = data.market_id
            """),
            {"updates": updates},
        )


def main():
    parser = argparse.ArgumentParser(description="Backfill mapped_category for NULL markets")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Rows per batch")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without updating")
    args = parser.parse_args()

    engine = get_engine()
    total = count_unclassified(engine)
    if total == 0:
        print("No markets with NULL mapped_category found. Nothing to do.")
        return

    print(f"Found {total} markets with NULL mapped_category")
    event_categories = load_event_categories(engine)
    print(f"Loaded {len(event_categories)} event categories for Tier 2")

    if args.dry_run:
        print("DRY RUN: no updates will be performed")
        return

    t0 = time.time()
    updated = 0
    errors = 0
    category_counts: dict[str, int] = {}

    for batch in iter_unclassified_batches(engine, args.batch_size):
        batch_updates = []
        for market_id, question, raw_category, event_id in batch:
            try:
                event_category = event_categories.get(event_id) if event_id else None
                mapped = infer_category(
                    question=question or "",
                    raw_category=raw_category,
                    event_category=event_category,
                )
                batch_updates.append((market_id, mapped))
                if mapped:
                    category_counts[mapped] = category_counts.get(mapped, 0) + 1
                else:
                    category_counts["__unclassified__"] = category_counts.get("__unclassified__", 0) + 1
            except Exception as e:
                print(f"Error processing market {market_id}: {e}")
                errors += 1
                continue

        if batch_updates:
            update_batch(engine, batch_updates)
            updated += len(batch_updates)

        elapsed = time.time() - t0
        pct = (updated / total * 100) if total > 0 else 0
        print(f"  Processed {updated}/{total} ({pct:.1f}%) in {elapsed:.0f}s — {errors} errors", end="\r")

    elapsed = time.time() - t0
    print(f"\nDone. Updated {updated} markets in {elapsed:.1f}s with {errors} errors.")

    # Summary
    print("\nCategory distribution:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = (count / updated * 100) if updated > 0 else 0
        label = "UNCLASSIFIED" if cat == "__unclassified__" else cat
        print(f"  {label:20s}: {count:6d} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
```

### 12.2 Execution

```bash
# From host (requires postgres on localhost:5432 or adjust URL)
python scripts/backfill_categories.py --batch-size 5000

# Dry run to preview coverage
python scripts/backfill_categories.py --dry-run
```

### 12.3 Usage Notes

- Run this **after** deploying the Alembic migration and deploying the new ETL code.
- The script uses `psycopg2` (sync driver) for simplicity. If running inside Docker, use the `postgresql+psycopg2://app:devpassword@postgres:5432/polymarket` URL.
- For large databases (500k+ markets), the script may take several minutes. The batch size can be tuned.
- The script is **idempotent**: it only touches rows where `mapped_category IS NULL`. Re-running after partial completion picks up only the remaining rows.

---

## 13. Test Matrix

### 13.1 Unit Tests for `infer_category()`

Create test file: `app/tests/classifier/test_category_classifier.py`

```python
"""Unit tests for the category classifier.

Tests cover:
- Each of the 8 categories (at least 2 examples per category)
- Each of the 3 tiers
- Edge cases: empty strings, None inputs, ambiguous questions
- Unclassifiable inputs
"""

import pytest

from transformers.category_classifier import (
    RAW_CATEGORY_MAP,
    _apply_raw_map,
    _classify_by_keywords,
    infer_category,
)


class TestRawCategoryMap:
    """Tier 1: Direct API category mapping."""

    def test_known_raw_category(self):
        assert _apply_raw_map("Sports") == "Sports"
        assert _apply_raw_map("NBA Playoffs") == "Sports"
        assert _apply_raw_map("Crypto") == "Crypto"
        assert _apply_raw_map("NFTs") == "Crypto"
        assert _apply_raw_map("Politics") == "Politics"
        assert _apply_raw_map("Global Politics") == "Geopolitics"
        assert _apply_raw_map("Business") == "Economics"
        assert _apply_raw_map("Science") == "Technology"
        assert _apply_raw_map("Pop-Culture") == "Entertainment"

    def test_none_raw_category(self):
        assert _apply_raw_map(None) is None

    def test_unrecognized_raw_category(self):
        assert _apply_raw_map("UnknownCategory") is None

    def test_all_raw_categories_are_covered(self):
        """Every value in RAW_CATEGORY_MAP maps to a valid category."""
        valid = {"Politics", "Crypto", "Sports", "Economics",
                 "Technology", "AI", "Geopolitics", "Entertainment"}
        for raw, canonical in RAW_CATEGORY_MAP.items():
            assert canonical in valid, f"{raw} → {canonical} is not a valid category"


class TestInferCategoryTier1:
    """Tier 1 takes priority over keyword classification."""

    def test_tier1_wins_over_tier3(self):
        """Even if question contains sports keywords, raw_category wins."""
        result = infer_category(
            question="Who will win the Super Bowl?",
            raw_category="Politics",
        )
        assert result == "Politics"

    def test_tier1_sports(self):
        result = infer_category(
            question="Some random question",
            raw_category="NBA Playoffs",
        )
        assert result == "Sports"

    def test_tier1_crypto(self):
        result = infer_category(
            question="Some random question",
            raw_category="NFTs",
        )
        assert result == "Crypto"


class TestInferCategoryTier2:
    """Tier 2 falls back to event category."""

    def test_tier2_wins_over_tier3(self):
        result = infer_category(
            question="Who will win the Super Bowl?",
            raw_category=None,
            event_category="Sports",
        )
        assert result == "Sports"

    def test_tier2_only_when_tier1_null(self):
        """Tier 2 only applies if Tier 1 returned nothing."""
        result = infer_category(
            question="Who will win?",
            raw_category="Politics",
            event_category="Sports",
        )
        assert result == "Politics", "Tier 1 should take priority over Tier 2"

    def test_tier2_none_falls_through(self):
        result = infer_category(
            question="Will the Fed raise rates?",
            raw_category=None,
            event_category=None,
        )
        assert result == "Economics"


class TestInferCategoryTier3:
    """Keyword classification on question text."""

    # ── Politics ──────────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Who will win the 2024 US presidential election?",
        "Will Donald Trump be the Republican nominee?",
        "Which party will control the Senate after the midterms?",
        "Will the Supreme Court overturn the ruling?",
        "Will there be a snap election in the UK?",
        "Will Biden approve the executive order?",
        "Who will be the next Prime Minister of Canada?",
    ])
    def test_politics(self, question):
        assert infer_category(question=question) == "Politics"

    # ── Geopolitics ──────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Will Russia invade another country this year?",
        "Will a ceasefire be declared in Gaza?",
        "Will NATO invoke Article 5?",
        "Will China impose sanctions on Taiwan?",
        "Will North Korea conduct a nuclear test?",
        "Will the UN Security Council pass a resolution?",
    ])
    def test_geopolitics(self, question):
        assert infer_category(question=question) == "Geopolitics"

    # ── Crypto ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Will Bitcoin reach $100,000 by end of 2025?",
        "Will Ethereum complete the merge successfully?",
        "Will Solana surpass 1000 TPS?",
        "Will the SEC approve a Bitcoin ETF?",
        "Will Uniswap v4 be deployed on mainnet?",
        "Will the Fed issue a central bank digital currency?",
    ])
    def test_crypto(self, question):
        assert infer_category(question=question) == "Crypto"

    # ── Sports ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Who will win the Super Bowl in 2026?",
        "Will LeBron James score 40,000 career points?",
        "Which team will win the FIFA World Cup?",
        "Will there be a Grand Slam winner from Spain this year?",
        "Who will win the NBA MVP award?",
        "Will Messi score in the final?",
    ])
    def test_sports(self, question):
        assert infer_category(question=question) == "Sports"

    # ── AI ────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Will GPT-5 pass the Turing test?",
        "Will AGI be achieved by 2030?",
        "Will OpenAI release a text-to-video model?",
        "Will self-driving cars be legal in California?",
        "Will the EU pass AI regulation this year?",
        "Will a neural network win a Nobel Prize?",
    ])
    def test_ai(self, question):
        assert infer_category(question=question) == "AI"

    # ── Technology ────────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Will Apple release a foldable iPhone?",
        "Will SpaceX successfully land Starship on Mars?",
        "Will NVIDIA's market cap exceed $5 trillion?",
        "Will a quantum computer break RSA encryption?",
        "Will Microsoft acquire another major gaming studio?",
        "Will the first 5G-connected city launch by 2027?",
    ])
    def test_technology(self, question):
        assert infer_category(question=question) == "Technology"

    # ── Economics ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Will the Fed cut interest rates in Q2 2026?",
        "Will US GDP growth exceed 3% next quarter?",
        "Will the S&P 500 reach 7,000 by year end?",
        "Will inflation drop below 2%?",
        "Will the US avoid a recession in 2026?",
        "Will oil prices exceed $100 per barrel?",
    ])
    def test_economics(self, question):
        assert infer_category(question=question) == "Economics"

    # ── Entertainment ─────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Which movie will win the Oscar for Best Picture?",
        "Will Taylor Swift announce a world tour?",
        "Will Netflix subscriber count exceed 300 million?",
        "Will the new Marvel film open above $200M?",
        "Will a K-pop group top the Billboard charts?",
        "Will the next season of the show be renewed?",
    ])
    def test_entertainment(self, question):
        assert infer_category(question=question) == "Entertainment"

    # ── Unclassifiable ────────────────────────────────────────────────

    @pytest.mark.parametrize("question", [
        "Will the weather be sunny tomorrow?",
        "Is the sky blue?",
        "Will my coffee taste good today?",
        "",  # empty string
    ])
    def test_unclassifiable(self, question):
        assert infer_category(question=question) is None

    # ── Edge Cases ────────────────────────────────────────────────────

    def test_none_question(self):
        # Should not crash; keyword classification will be skipped
        result = infer_category(question=None, raw_category="Sports")
        assert result == "Sports"

    def test_question_with_special_characters(self):
        result = infer_category(
            question="Will BTC (Bitcoin) reach $100k? 🚀"
        )
        assert result == "Crypto"

    def test_ambiguous_sports_vs_entertainment(self):
        """First matching rule wins — sports before entertainment."""
        result = infer_category(
            question="Will the Super Bowl halftime show win an Emmy?"
        )
        # "Super Bowl" matches sports first
        assert result == "Sports"

    def test_mixed_politics_and_economics(self):
        """Politics is checked before Economics."""
        result = infer_category(
            question="Will the President's economic plan reduce inflation?"
        )
        assert result == "Politics"

    def test_event_category_fallback_with_unknown_raw_category(self):
        """Unknown raw category falls through to event category."""
        result = infer_category(
            question="Who will win the match?",
            raw_category="SomeUnknownCategory",
            event_category="Sports",
        )
        assert result == "Sports"

    def test_all_tiers_null(self):
        """All three tiers return None."""
        result = infer_category(
            question="What is the meaning of life?",
            raw_category=None,
            event_category=None,
        )
        assert result is None
```

### 13.2 Integration Tests

Add the following checks to `app/tests/test_db_integrity.py`:

| Test | What It Validates |
|---|---|
| `test_mapped_category_populated` | At least 95% of markets have non-null `mapped_category` |
| `test_mapped_category_valid_values` | All `mapped_category` values are one of the 8 canonical strings |
| `test_mapped_category_index_exists` | `idx_markets_mapped_category` index exists |

Suggested test implementations:

```python
# In test_db_integrity.py, add:

VALID_CATEGORIES = {
    "Politics", "Crypto", "Sports", "Economics",
    "Technology", "AI", "Geopolitics", "Entertainment",
}


def test_mapped_category_populated(conn: Connection) -> None:
    total = conn.execute(text("SELECT count(*) FROM markets")).scalar() or 0
    classified = conn.execute(
        text("SELECT count(*) FROM markets WHERE mapped_category IS NOT NULL")
    ).scalar() or 0
    pct = (classified / total * 100) if total > 0 else 0
    assert pct >= 95, (
        f"Only {classified}/{total} ({pct:.1f}%) markets have mapped_category populated"
    )


def test_mapped_category_valid_values(conn: Connection) -> None:
    rows = conn.execute(
        text("SELECT DISTINCT mapped_category FROM markets WHERE mapped_category IS NOT NULL")
    ).scalars().all()
    for cat in rows:
        assert cat in VALID_CATEGORIES, (
            f"Invalid mapped_category value: {cat!r}"
        )


def test_mapped_category_index_exists(conn: Connection) -> None:
    result = conn.execute(
        text("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'markets'
            AND indexname = 'idx_markets_mapped_category'
        """)
    ).scalar()
    assert result == 1, "idx_markets_mapped_category index does not exist"
```

---

## 14. Acceptance Criteria

- [ ] **Alembic migration 002** runs cleanly on existing databases (no data loss)
- [ ] **`infer_category()`** correctly classifies all test matrix examples
- [ ] **Tier 1**: All known raw API categories in `RAW_CATEGORY_MAP` return correct canonical values
- [ ] **Tier 2**: Event category used when raw_category is NULL and event_category is not
- [ ] **Tier 3**: Keyword classification covers ≥ 95% of previously unclassified questions
- [ ] **Overall coverage**: `mapped_category IS NOT NULL` for ≥ 95% of markets after backfill
- [ ] **No regression**: Existing `market_discovery` pipeline runs without errors
- [ ] **`export_markets`** writes `mapped_category` to the database correctly
- [ ] **Integration tests** all pass
- [ ] **Backfill script** updates existing rows without errors
- [ ] **Seed refresh** (`./scripts/refresh-seed.sh`) captures the new column

---

## 15. Edge Cases & Known Issues

### 15.1 Known Issues

| Issue | Severity | Mitigation |
|---|---|---|
| Data loaders set `event_category = m.get("category")` (bug) | High | Fix in loaders (Section 9.1) before Tier 2 works |
| Keyword matching uses `in` operator (no word boundaries) | Low | "ai" in "train" matches AI. Mitigation: use `" ai "` (with spaces) in addition to `"ai "` and `" ai"` to reduce false positives |
| Ambiguous questions: "Will England win the World Cup?" → Geopolitics (no, it's Sports — "world cup" is in SPORTS_KW) | Low | Ordering handles this; "world cup" in SPORTS_KW is checked before GEOPOLITICS_KW |
| False positive: "Will Apple stock reach $300?" → Technology (correct, Apple is a tech company; could also be Economics) | Low | Technology is intentional; Economics captures "stock market" signals if they appear alone |
| AI vs Technology overlap: "Will GPT-5 launch on Azure?" → hits both AI and Technology; AI rule comes first | Intended | AI is a subset of Technology; we classify as AI for more granular analytics |

### 15.2 Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Empty string question (`question=""`) | Tier 1 → Tier 2 → Tier 3 (skipped) → returns None |
| None question (`question=None`) | Tier 1 → Tier 2 → Tier 3 (skipped because `if question:` is False) → returns None |
| Both raw_category and event_category are non-NULL | Tier 1 wins |
| Unknown raw_category value | Logged as warning; falls through to Tier 2 |
| Market with no event_id | Tier 2 gets `None` for event_category; falls through to Tier 3 |
| Very long question text (1000+ chars) | Works correctly; `in` operator on long string is O(n) per keyword |
| HTML entities in question (e.g., `&amp;`) | Matched as-is; lowercased. Not a concern since keywords are ASCII |
| Unicode characters (e.g., emoji, accents) | Lowercased by `.lower()`. Keywords are ASCII, so non-ASCII text won't match |

### 15.3 Monitoring & Maintenance

- Add a **Grafana alert** (or equivalent) if `mapped_category` coverage drops below 90%.
- When new raw API categories appear in logs, add them to `RAW_CATEGORY_MAP`.
- Review keyword coverage quarterly by sampling the unclassified pool.
- If coverage drops significantly, expand keyword lists or adjust ordering.
