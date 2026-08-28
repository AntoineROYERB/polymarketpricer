# Phase 0 — Feasibility Study Report

> **Project:** Polymarket Smart Money Tracker  
> **Date:** 2026-06-16  
> **Status:** Complete  
> **Next Step:** Phase 1 — MVP Leaderboard (pending approval of this report)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Data Sources Overview](#2-data-sources-overview)
3. [Feasibility Assessment](#3-feasibility-assessment)
4. [API Rate Limits](#4-api-rate-limits)
5. [Source of Truth Analysis](#5-source-of-truth-analysis)
6. [Custom Blockchain Indexer Assessment](#6-custom-blockchain-indexer-assessment)
7. [Architecture Recommendation](#7-architecture-recommendation)
8. [Risks](#8-risks)
9. [Limitations](#9-limitations)
10. [Estimated Implementation Complexity](#10-estimated-implementation-complexity)
11. [Conclusion & Go/No-Go](#11-conclusion--go-no-go)

---

## 1. Executive Summary

Building a "Smart Money Tracker" for Polymarket is **feasible** using existing public data sources. The Polymarket ecosystem exposes three complementary APIs (Gamma, Data, CLOB) that together provide all the data required to reconstruct wallet PnL, track open positions, measure trader performance, and detect new positions in near-real-time. Third-party indexers (PolyNode, Envio, predmktdata) offer faster query paths and deeper historical coverage but introduce external dependencies.

**Key finding:** A custom blockchain indexer is **not required** for Phases 1–3. The Polymarket Data API (`data-api.polymarket.com`) provides pre-computed positions, PnL, and trade history without any authentication. A custom indexer may become justified in Phase 4+ (Edge Scoring) if sub-second latency or full raw event history is needed for advanced analytics.

**Primary recommendation:** Use the Polymarket Data API as the primary data source for positions and trades, the Gamma API for market metadata and categories, and the CLOB API for real-time price data. Supplement with a local PostgreSQL cache to avoid rate limit exhaustion.

---

## 2. Data Sources Overview

### 2.1 Polymarket Gamma API (`gamma-api.polymarket.com`)

| Attribute | Detail |
|-----------|--------|
| Authentication | None (fully public) |
| Primary use | Market discovery, metadata, categories, tags |
| Key endpoints | `GET /events`, `GET /markets`, `GET /tags`, `GET /series` |
| Rate limit | ~4,000 req / 10s (shared pool; `/markets`: 300/10s, `/events`: 500/10s) |
| Data freshness | Near real-time (sub-second lag) |

Provides event titles, market questions, resolution outcomes, categories (politics, crypto, sports, etc.), and timestamps. Essential for mapping `condition_id` and `token_id` to human-readable information.

### 2.2 Polymarket Data API (`data-api.polymarket.com`)

| Attribute | Detail |
|-----------|--------|
| Authentication | None (fully public) |
| Primary use | Positions, trades, activity, PnL, leaderboards |
| Key endpoints | `GET /trades`, `GET /positions?user=`, `GET /closed-positions?user=`, `GET /activity?user=`, `GET /value?user=`, `GET /holders` |
| Rate limit | ~1,000 req / 10s (`/trades`: 200/10s, `/positions`: 150/10s) |
| Data freshness | Near real-time (sub-second lag) |

**This is the single most important API for this project.** It provides:
- **Current positions** with `size`, `avgPrice`, `realizedPnl`, `cashPnl`, `totalBought`
- **Closed positions** with full PnL breakdown
- **Trade history** with `price`, `shares`, `amount_usd`, `side` (BUY/SELL), `timestamp`
- **Activity log** with on-chain event types (trade, split, merge, redemption)

### 2.3 Polymarket CLOB API (`clob.polymarket.com`)

| Attribute | Detail |
|-----------|--------|
| Authentication | Reads: none; Trading: API key + HMAC |
| Primary use | Order books, prices, midpoints, price history |
| Key endpoints | `GET /book`, `GET /price`, `GET /midpoint`, `GET /prices-history` |
| Rate limit | 9,000 req / 10s (general); `/book`: 1,500/10s, `/price`: 1,500/10s |
| Data freshness | Real-time (WebSocket available) |

Useful for real-time price data and market depth. The WebSocket (`wss://ws-subscriptions-clob.polymarket.com/ws/market`) provides push-based book updates and last-trade prices. Not strictly required for PnL reconstruction but valuable for edge scoring (entry vs. exit vs. resolution price comparison).

### 2.4 Polygon Blockchain (On-Chain)

| Attribute | Detail |
|-----------|--------|
| Data | Every trade, split, merge, redemption, resolution |
| Latency | ~2s block time |
| Key contracts | CTF Exchange (V1 + V2), ConditionalTokens, NegRiskAdapter, FPMM |
| Access | Public RPC (e.g., Infura, Alchemy, or Polygon public endpoint) |

All Polymarket trades settle on Polygon via the CTF Exchange contracts (`0x4bFb41d5B...` and newer V2 contracts). Key on-chain events:
- `OrderFilled` — executed trade
- `PositionSplit` — USDC → outcome tokens
- `PositionsMerge` — outcome tokens → USDC
- `PayoutRedemption` — claim winnings after resolution
- `ConditionResolution` — market resolved by oracle

Processing raw on-chain data requires parsing event logs and reconstructing state — this is what the Polymarket API and third-party indexers do internally.

### 2.5 Third-Party Indexers

| Service | Description | Pros | Cons |
|---------|-------------|------|------|
| **PolyNode** | Purpose-built Polymarket trade index. Covers every trade, position, settlement since Nov 2022. Pre-computes positions for 2.5M+ wallets in real time. | Sub-10ms queries, zero lag, full history, enriched metadata | Paid API, external dependency |
| **Envio polymarket-indexer** | Open-source HyperIndex indexer merging 8 subgraphs into one. Trades, positions, PnL, OI, FPMM, fees, sports. | Open source, runs locally, full control, TypeScript | Requires running own infrastructure, ~6 days to sync full history |
| **predmktdata** | CSV/Parquet dumps + API. Covers all fills, positions, resolutions since block 35,800,000. | Simple CSV access, daily snapshots, real-time (Pro) | Limited to pre-computed snapshots, API key required |

---

## 3. Feasibility Assessment

### 3.1 Can historical wallet PnL be reconstructed accurately?

**Assessment: YES — with caveats**

**How:**
- The Polymarket Data API returns `realizedPnl` and `cashPnl` directly on the `/positions` endpoint.
- The `/trades` endpoint provides every individual trade with `price`, `shares`, `amount_usd`, and `side`.
- Closed positions (resolved markets) are available via `/closed-positions` with full PnL.

**Method A: API-Aggregated PnL (Recommended for MVP)**
```
PnL per position = realizedPnl (from API)
Total PnL = SUM(realizedPnl) over all closed positions
           + SUM(cashPnl) over all current positions
```
Accuracy: **High**. The Polymarket API computes this from on-chain events internally.

**Method B: Trade-by-Trade Reconstruction (Verification)**
```
For each trade:
  If BUY: cost_basis += price * shares
  If SELL: realized_pnl += (price - avg_entry) * shares
After resolution:
  If WIN: realized_pnl += resolution_value * shares - cost_basis
  If LOSE: realized_pnl = -cost_basis
```
Accuracy: **Medium-High**. Depends on correctly matching trades to resolution outcomes.

**Caveats:**
- The API tracks positions by `proxyWallet` (Gnosis Safe), not the user's primary wallet address. A mapping step is required.
- Unrealized PnL fluctuates with market price and requires current price quotes from CLOB API.
- Very old markets (pre-2023) may have incomplete metadata in the API.

### 3.2 Can open positions be reconstructed from available data?

**Assessment: YES — directly provided by the API**

**How:**
- `GET /positions?user={proxyWallet}` returns all current open positions with:
  - `size` — number of shares held
  - `avgPrice` — average entry price
  - `totalBought` — cumulative shares bought
  - `realizedPnl` — PnL from partially closed positions
  - `cashPnl` — current unrealized PnL
  - `curPrice` — current market price
  - `redeemable` — whether the position can be redeemed (market resolved)

**Additional endpoints:**
- `GET /value?user={proxyWallet}` — aggregate portfolio value
- `GET /activity?user={proxyWallet}` — full event history (trades, splits, merges, redemptions)

**Key detail:** Polymarket uses proxy wallets (Gnosis Safe contracts deployed per-user). The user's main wallet address is not the same as their trading wallet. The mapping is:
- `GET /users/{address}` on Gamma API returns the user's profile, including their `proxyWallet`.
- Alternatively, query the `ProxyFactory` contract on Polygon to find proxy wallets.

**Recommendation:** Use the Data API directly. It handles proxy wallet abstraction internally.

### 3.3 Can trader performance be tracked over time?

**Assessment: YES**

**How:**
- Track positions and trades over time using daily snapshots.
- The Data API provides `timestamp` on every trade and position update.
- Compute rolling metrics:
  - **7-day PnL:** Compare position values 7 days apart.
  - **30-day ROI:** (Current Value + Realized PnL) / (Total Invested) over trailing 30 days.
  - **Win rate:** Count trades with positive PnL / total resolved trades within time window.
  - **Average holding duration:** Timestamp difference between first buy and full exit.

**Database schema from ROADMAP.md supports this:** The `positions` table with `realized_pnl`, `unrealized_pnl`, and `avg_entry_price` enables historical comparisons when snapshotted daily. The `wallet_analytics` table stores daily computed metrics.

**Limitation:** Historical performance before the tracker starts monitoring requires backfilling. The Data API supports this via paginated queries back to November 2022.

### 3.4 Can new positions be detected in near real-time?

**Assessment: YES**

**How:**

**Method A: Polling (Simple, MVP-ready)**
```
Every 60 seconds:
  GET /positions?user={wallet} for each tracked wallet
  Compare with previous snapshot
  Detect: new market, size increase, size decrease, full exit
```
- Latency: ~60-120 seconds
- Rate limit cost: 1 request per wallet per minute

**Method B: Activity Stream (Better, recommended)**
```
Every 30 seconds:
  GET /activity?user={wallet} with cursor pagination
  Watch for new events of type: "trade" with isAggressor=true
```
- Latency: ~30-60 seconds
- More efficient: detects only new activity, not full position scans

**Method C: On-Chain WebSocket (Lowest Latency)**
```
Connect to Polygon WebSocket (via Alchemy/Infura)
Subscribe to OrderFilled events on CTF Exchange contracts
Filter by tracked proxy wallets
```
- Latency: ~2-5 seconds (block time + processing)
- More complex infrastructure but truly real-time

**Method D: Third-Party Webhook (PolyNode Pro)**
- PolyNode offers webhook-style queries with sub-second latency
- Simplest integration but paid

**Recommendation for MVP:** Start with Method A (polling every 60 seconds for top 100 wallets). This costs ~100 req/min out of the 6,000 req/min Data API limit — well within budget.

### 3.5 What are the API rate limits?

| API | General Limit | Key Per-Endpoint Limits | Reset |
|-----|--------------|------------------------|-------|
| **Gamma** | 4,000 req / 10s | `/markets`: 300/10s, `/events`: 500/10s, search: 350/10s | Sliding window |
| **Data** | 1,000 req / 10s | `/trades`: 200/10s, `/positions`: 150/10s, `/activity`: 150/10s | Sliding window |
| **CLOB** | 9,000 req / 10s | `/book`: 1,500/10s, `/price`: 1,500/10s, `/prices-history`: 1,000/10s | Sliding window |

**Key behaviors:**
- Limits are enforced via Cloudflare throttling (requests are delayed, not rejected — unless sustained over limit).
- All limits use **sliding time windows** (not fixed calendar windows).
- The Data API general limit of 1,000/10s is the primary constraint for our use case.
- **Builder Program** offers tiered upgrades (Unverified → Verified → Partner) for higher limits.

**Capacity planning for MVP (tracking 100 wallets):**

| Operation | Frequency | Req/min | Req/10s |
|-----------|-----------|---------|---------|
| Position check (100 wallets) | Every 60s | 100 | ~17 |
| Trade history sync (10 active wallets) | Every 5 min | 2 | ~0.3 |
| Market metadata refresh | Every 15 min | ~7 | ~0.1 |
| CLOB price quotes (100 positions) | Every 60s | 100 | ~17 |
| **Total Data API** | | **~102** | **~17** |
| **Total CLOB** | | **~100** | **~17** |

**Margin:** We use ~2% of Data API limit and ~0.2% of CLOB limit. **Scaling to 1,000 wallets uses ~20% of Data API limit.** Rate limits are not a concern for MVP through Phase 3.

### 3.6 Which source should be considered the source of truth?

| Source | Trust Level | Strengths | Weaknesses |
|--------|------------|-----------|------------|
| **Polygon Blockchain** | **Absolute** | Immutable, verifiable, complete history | Raw format requires parsing; ~2s block latency; no enriched metadata |
| **Polymarket Data API** | **High** | Pre-computed positions/PnL, enriched metadata, public, no auth | Transient — could change schema; rate limited; depends on Polymarket infrastructure |
| **Polymarket Gamma API** | **High (metadata)** | Authoritative for market questions, categories, resolutions | Not designed for position/trade data |
| **Third-party indexers** | **Medium-High** | Often faster and more complete | External dependency; may lag (subgraph was 6.7 days behind); cost |

**Recommendation:**
- **Primary source of truth:** Polymarket Data API — for positions, trades, PnL, and activity.
- **Metadata source of truth:** Polymarket Gamma API — for market data, categories, tags, and outcomes.
- **Verification layer:** Polygon blockchain — for critical data integrity checks (audit trail).
- **Avoid sole reliance on third-party indexers** for the core data pipeline; use them only as supplementary speed layers if needed.

**Why the Data API as source of truth:**
1. It is **official** — maintained by Polymarket, consistent with the platform's own UI.
2. It provides **pre-computed PnL** — avoiding complex on-chain event reconstruction.
3. It is **free and public** — no API key required, no cost.
4. It has **near real-time latency** — sub-second for new trades.

**Why the blockchain as verification (not primary):**
1. Raw events are harder to query — no "give me all trades for wallet X" without custom indexing.
2. Proxy wallet abstraction adds complexity.
3. No enriched metadata — `token_id` values need decoding via Gamma API anyway.

### 3.7 Is a custom blockchain indexer required?

**Assessment: NOT REQUIRED for Phases 1–3**

| Phase | Custom Indexer Needed? | Reason |
|-------|----------------------|--------|
| **Phase 1 — MVP Leaderboard** | No | Data API provides all required data directly |
| **Phase 2 — Niche Expertise** | No | Gamma API provides categories; Data API provides trades |
| **Phase 3 — Smart Money Detection** | No | Polling or Data API activity stream works at scale |
| **Phase 4 — Edge Scoring** | Maybe | Real-time entry/exit price comparison may benefit from raw event stream |
| **Phase 5 — Recommendation Engine** | No | Aggregated from earlier phases |
| **Phase 6 — Dashboard** | No | Frontend consuming APIs |
| **Phase 7 — Advanced Features** | Maybe | ML features may need granular event data |

**When a custom indexer would be justified:**
1. **Sub-second detection** of new positions (Phases 3+).
2. **Full raw event history** for edge scoring (Phase 4) — comparing entry prices to market consensus evolution.
3. **Independence** from Polymarket's API availability or breaking changes.
4. **Scale** beyond 10,000 wallets.

**If a custom indexer is built, use:**
- **Envio HyperIndex** framework (TypeScript, handles reorgs, fast sync)
- Index key Polygon contracts: CTF Exchange (V1+V2), ConditionalTokens, NegRiskAdapter
- Target sync time: ~6 days for full history
- Infrastructure: Docker, PostgreSQL (stores indexed events)

---

## 4. API Rate Limits — Detailed Reference

### 4.1 Gamma API

| Endpoint | Limit | Notes |
|----------|-------|-------|
| General pool | 4,000 req / 10s | Shared across all Gamma endpoints |
| `GET /markets` | 300 req / 10s | Use cursors, not offset |
| `GET /events` | 500 req / 10s | |
| `GET /public-search` | 350 req / 10s | |

### 4.2 Data API

| Endpoint | Limit | Notes |
|----------|-------|-------|
| General pool | 1,000 req / 10s | Shared across all Data endpoints |
| `GET /trades` | 200 req / 10s | |
| `GET /positions` | 150 req / 10s | |
| `GET /closed-positions` | 150 req / 10s | |
| `GET /activity` | 150 req / 10s | |
| `GET /holders` | 150 req / 10s | |

### 4.3 CLOB API

| Endpoint | Limit | Notes |
|----------|-------|-------|
| General pool | 9,000 req / 10s | |
| `GET /book` | 1,500 req / 10s | |
| `GET /price` | 1,500 req / 10s | |
| `GET /midpoint` | 1,500 req / 10s | |
| `GET /prices-history` | 1,000 req / 10s | |

### 4.4 Strategies for Staying Within Limits

1. **Cache aggressively.** Store position snapshots locally in PostgreSQL. Only fetch what changed.
2. **Use cursors, not offsets.** The API paginates with `next_cursor` — always use it.
3. **Batch where possible.** CLOB supports batch endpoints (`/books`, `/prices`).
4. **Prefer WebSocket for real-time data.** CLOB WebSocket for price/book updates avoids REST calls.
5. **Stagger polling.** Don't hit all wallets at the same second; spread requests across the interval.
6. **Implement exponential backoff.** On any throttling (delayed responses), back off.
7. **Monitor usage.** Track `X-RateLimit-Remaining` headers.

---

## 5. Source of Truth Analysis

### 5.1 Decision Matrix

| Criterion | Data API | Gamma API | CLOB API | Polygon Chain | PolyNode (3rd party) |
|-----------|----------|-----------|----------|---------------|---------------------|
| Positions & PnL | ✅ Native | ❌ | ❌ | ⚠️ Needs indexing | ✅ Native |
| Trade history | ✅ Native | ❌ | ⚠️ Recent only | ⚠️ Needs indexing | ✅ Native |
| Market metadata | ⚠️ Partial | ✅ Native | ❌ | ❌ | ⚠️ Enriched |
| Categories/tags | ❌ | ✅ Native | ❌ | ❌ | ⚠️ Partial |
| Real-time prices | ❌ | ❌ | ✅ Native | ⚠️ ~2s delay | ❌ |
| Order book depth | ❌ | ❌ | ✅ Native | ❌ | ❌ |
| Historical (2022+) | ✅ | ✅ | ❌ | ✅ | ✅ |
| Free | ✅ | ✅ | ✅ | ⚠️ RPC costs | ❌ (paid) |
| No external dep. | ⚠️ Polymarket dep. | ⚠️ Polymarket dep. | ⚠️ Polymarket dep. | ✅ Truly sovereign | ⚠️ Third-party dep. |

### 5.2 Recommended Source Selection

| Data Domain | Primary Source | Secondary Source | Rationale |
|-------------|---------------|-----------------|-----------|
| **Positions** | Data API `/positions` | Polygon chain (audit) | Data API is authoritative and pre-computed |
| **Trades** | Data API `/trades` | CLOB `/prices-history` (price context) | Direct from exchange |
| **PnL** | Data API (realizedPnl, cashPnl) | Trade-by-trade reconstruction | Double-entry verification |
| **Market metadata** | Gamma API | Data API (enriched fields) | Gamma has canonical categories |
| **Current prices** | CLOB API `/price` | CLOB WebSocket (real-time) | Lowest latency |
| **Resolution outcomes** | Gamma API `/markets/{id}` | Polygon ConditionalTokens contract | Cross-verify |
| **Wallet identity** | Gamma API `/users/{address}` | ProxyFactory contract | Proxy wallet mapping |

---

## 6. Custom Blockchain Indexer Assessment

### 6.1 Effort Breakdown

Building a custom indexer would require:

| Component | Effort | Description |
|-----------|--------|-------------|
| Event parsing | 2-3 days | Decode OrderFilled, PositionSplit, PositionsMerge, PayoutRedemption, ConditionResolution |
| State reconstruction | 3-5 days | Rebuild user positions, PnL from raw events |
| Database schema | 1 day | Tables for events, positions, markets |
| Historical sync | 6 days* | Catch up from block ~35.8M (time, not dev effort) |
| Real-time listener | 2-3 days | WebSocket subscription + block processing |
| Proxy wallet mapping | 1-2 days | Track Gnosis Safe proxy deployments |
| Testing + validation | 3-5 days | Compare against Polymarket API outputs |
| **Total dev effort** | **~15-20 days** | |
| **Total calendar time** | **~21-26 days** | Including historical sync |

\* *Using Envio HyperIndex with HyperSync can reduce historical sync to ~6 days. Custom RPC-based sync could take 2-4 weeks.*

### 6.2 Build vs. Buy Comparison

| Approach | Dev Time | Cost | Control | Maintenance |
|----------|----------|------|---------|-------------|
| Polymarket API only | 0 days | Free | Low | None |
| Polymarket API + local cache | 3-5 days | Free (self-hosted DB) | Medium | Low |
| PolyNode API | 1 day | Paid | Low | None |
| Envio open-source indexer | 5-7 days (deploy) | Infrastructure only | High | Medium |
| Custom indexer from scratch | 15-20 days | Infrastructure + dev time | Full | High |

### 6.3 Recommendation

**Do not build a custom indexer for MVP (Phases 1-3).** The Polymarket Data API provides everything needed. Reserve the option to deploy the open-source Envio indexer if:
- API rate limits become a bottleneck (>1,000 wallets tracked).
- Sub-second detection is required.
- Polymarket API changes in breaking ways.
- Edge scoring (Phase 4) requires raw event-level granularity.

---

## 7. Architecture Recommendation

### 7.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE                                 │
│                                                                      │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────────┐   │
│  │ Gamma    │    │  Data API    │    │  CLOB API                │   │
│  │ API      │    │  (Public)    │    │  (Public reads)          │   │
│  │ (Public) │    │              │    │                          │   │
│  └────┬─────┘    └──────┬───────┘    └──────────┬───────────────┘   │
│       │                 │                       │                    │
│       ▼                 ▼                       ▼                    │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              Data Collection Layer (Python)                  │     │
│  │  - API client with rate limiting + retry                    │     │
│  │  - Cursor-based pagination for trade/position history       │     │
│  │  - WebSocket listener for real-time data (optional)         │     │
│  └─────────────────────────┬──────────────────────────────────┘     │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              PostgreSQL Database                             │     │
│  │  - markets, trades, wallets, positions, analytics            │     │
│  │  - Daily metric snapshots                                    │     │
│  │  - Cached API responses with TTL                             │     │
│  └──────────┬──────────┬──────────┬───────────────────────────┘     │
│             │          │          │                                  │
│             ▼          ▼          ▼                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│  │ Ranking  │  │Analytics │  │ Alerts   │                          │
│  │ Engine   │  │ Engine   │  │ Engine   │                          │
│  └──────────┘  └──────────┘  └──────────┘                          │
│       │             │             │                                  │
│       └─────────────┼─────────────┘                                  │
│                     ▼                                                │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                 FastAPI Backend                               │     │
│  │  - REST API for dashboard                                    │     │
│  │  - WebSocket for real-time alerts                            │     │
│  └─────────────────────────┬──────────────────────────────────┘     │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              Next.js Frontend (Dashboard)                    │     │
│  │  - Leaderboard, Wallet Profiles, Smart Money Feed           │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Backend** | Python 3.12+ | Existing team expertise, rich data ecosystem |
| **API Framework** | FastAPI | Async, type hints, auto-docs, WebSocket support |
| **Database** | PostgreSQL | Relational schema per ROADMAP, JSON support for analytics |
| **Cache** | Redis | Position snapshots, rate limit tracking, pub/sub for alerts |
| **Data Pipeline** | Mage AI (recommended) | Python-native, simpler than Airflow for this scale |
| **Frontend** | Next.js + TypeScript | Per ROADMAP requirement |
| **UI Kit** | Tailwind + shadcn/ui | Per ROADMAP requirement |
| **Infrastructure** | Docker + Railway/Fly.io | Per ROADMAP requirement |
| **CI/CD** | GitHub Actions | Per ROADMAP requirement |

### 7.3 Data Flow (MVP)

```
1. DISCOVERY (one-time)
   └── Gamma API GET /markets?closed=false → seed market table
   └── Gamma API GET /tags → seed category table

2. WALLET DISCOVERY (ongoing)
   └── Data API GET /holders?market={id} → discover active wallets
   └── Gamma API GET /users/{address} → get proxy wallet mapping

3. POSITION SYNC (every 60s)
   └── Data API GET /positions?user={proxyWallet} → upsert positions table
   └── Detect new/increased/decreased/exited positions
   └── Store daily snapshot in wallet_analytics table

4. TRADE HISTORY (daily backfill + real-time)
   └── Data API GET /trades?user={proxyWallet} → upsert trades table
   └── Paginate with cursor until caught up

5. RANKING (every 6 hours)
   └── Read from analytics tables
   └── Compute wallet_score formula
   └── Materialize Top 100, Top 10 Emerging, Top 10 Consistent

6. ALERTS (real-time, on position change)
   └── If score > 80 AND position_size > $500 → send alert
   └── Delivery: Telegram + Discord
```

### 7.4 Database Schema

Per ROADMAP.md, with one addition (`wallet_analytics` table for daily snapshots):

```sql
CREATE TABLE markets (
    id          TEXT PRIMARY KEY,
    question    TEXT NOT NULL,
    category    TEXT,
    created_at  TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    outcome     TEXT
);

CREATE INDEX idx_markets_category ON markets(category);

CREATE TABLE trades (
    id          TEXT PRIMARY KEY,
    wallet      TEXT NOT NULL,
    market_id   TEXT NOT NULL REFERENCES markets(id),
    side        TEXT NOT NULL,  -- BUY / SELL
    price       DOUBLE PRECISION NOT NULL,
    shares      DOUBLE PRECISION NOT NULL,
    amount_usd  DOUBLE PRECISION NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_trades_wallet ON trades(wallet);
CREATE INDEX idx_trades_market ON trades(market_id);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);

CREATE TABLE wallets (
    wallet      TEXT PRIMARY KEY,
    first_seen  TIMESTAMPTZ,
    last_seen   TIMESTAMPTZ
);

CREATE TABLE positions (
    wallet          TEXT NOT NULL,
    market_id       TEXT NOT NULL REFERENCES markets(id),
    avg_entry_price DOUBLE PRECISION,
    shares          DOUBLE PRECISION,
    realized_pnl    DOUBLE PRECISION,
    unrealized_pnl  DOUBLE PRECISION,
    PRIMARY KEY (wallet, market_id)
);

CREATE TABLE wallet_analytics (
    wallet              TEXT NOT NULL,
    snapshot_date       DATE NOT NULL,
    total_pnl           DOUBLE PRECISION,
    roi                 DOUBLE PRECISION,
    win_rate            DOUBLE PRECISION,
    num_trades          INTEGER,
    avg_position_size   DOUBLE PRECISION,
    risk_adj_return     DOUBLE PRECISION,
    avg_holding_duration INTERVAL,
    wallet_score        DOUBLE PRECISION,
    PRIMARY KEY (wallet, snapshot_date)
);
```

### 7.5 Python Project Structure

Per ROADMAP.md:

```
app/
├── api/            # FastAPI routes (leaderboard, wallet, feed, market)
├── analytics/      # PnL calculation, metrics, edge scoring
├── alerts/         # Alert rules, delivery (Telegram, Discord)
├── db/             # SQLAlchemy models, migrations (Alembic)
├── pipelines/      # Data collection, ETL (Mage AI or custom)
│   ├── collectors/ # Gamma, Data, CLOB API clients
│   └── processors/ # Ranking, analytics, expertise detection
├── ranking/        # Scoring formulas
├── services/       # Business logic layer
├── models/         # Pydantic schemas
├── utils/          # Config, logging, rate limiting, caching
└── tests/          # Pytest suite
```

---

## 8. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | **Polymarket API changes or deprecation** | Medium | High | Cache data locally; monitor API changelog; maintain option to deploy own indexer |
| R2 | **API rate limit throttling at scale** | Low-Medium | Medium | Cache aggressively; use staggered polling; request Builder Program upgrade |
| R3 | **Proxy wallet mapping complexity** | Medium | Medium | Test with known wallets first; use Gamma API `/users` endpoint as primary mapping |
| R4 | **Incomplete historical data** | Low | Medium | API covers back to Nov 2022; pre-2022 markets may be incomplete |
| R5 | **Wallet filtering misses skilled traders** | Medium | Low | 50-trade / $1k / 3-month thresholds are reasonable; tune after launch |
| R6 | **Markets with delayed resolution (UMA disputes)** | Low | Low | PnL may be inaccurate during dispute periods; handle resolution pending state |
| R7 | **V2 exchange contract migration** | Medium | Medium | Polymarket is migrating to V2 contracts; index both V1 and V2 event sources |
| R8 | **False signals from automated/manipulated wallets** | Medium | Medium | Add detection for wash trading, correlated wallets, and unusual patterns in Phase 3+ |

---

## 9. Limitations

1. **Proxy wallet abstraction:** Polymarket's proxy wallet architecture means one user identity may have multiple proxy wallets (though typically one per user). The Data API handles this, but cross-referencing with Gamma API profiles is needed.

2. **Unrealized PnL volatility:** Unrealized PnL depends on current market prices, which fluctuate. Daily snapshots provide stability for ranking but mask intraday volatility.

3. **Category classification:** Market categories are user/community-assigned on Polymarket and may be inconsistent. Some markets will fall through categorization cracks.

4. **No trade data for AMM users:** Trades executed via the old FPMM (AMM) contracts have different event signatures. The Data API covers CLOB fills well; FPMM trades may be missed.

5. **VPN/geo-restrictions:** Polymarket may apply geographic restrictions. The APIs appear fully public as of this writing but future restrictions could affect data access.

6. **Historical PnL for resolved markets:** Once a market is resolved and redeemed, the position disappears from `/positions`. The `/closed-positions` endpoint covers resolved positions, but very old ones may have been pruned.

7. **Non-USDC collateral (PolyUSD V2):** Markets migrating to PolyUSD (pUSD) may report PnL in pUSD rather than USDC. A conversion layer may be needed for consistent USD reporting.

---

## 10. Estimated Implementation Complexity

| Phase | Effort (dev-days) | Complexity | Dependencies |
|-------|-------------------|-----------|-------------|
| **Phase 1 — MVP Leaderboard** | 10-15 days | Medium | Data API, PostgreSQL, ranking formulas |
| - Data collection layer | 3-4 days | | API clients, pagination, rate limiting |
| - Database schema + migrations | 2-3 days | | Models, Alembic |
| - Wallet analytics engine | 3-4 days | | PnL, ROI, win rate, consistency |
| - Ranking engine | 2-3 days | | Score formula, materialized top lists |
| - Tests + docs | 2-3 days | | 80%+ coverage requirement |
| **Phase 2 — Niche Expertise** | 5-8 days | Low-Medium | Phase 1 complete, category classification |
| **Phase 3 — Smart Money Detection** | 8-12 days | Medium | Phases 1-2 complete, alert infrastructure |
| **Phase 4 — Edge Scoring** | 10-15 days | High | Full trade history, price evolution tracking |
| **Phase 5 — Recommendation Engine** | 5-8 days | Medium | Phase 4 complete |
| **Phase 6 — Dashboard** | 10-15 days | Medium | All backend phases complete |
| **Phase 7 — Advanced Features** | 15-25 days | High | All prior phases complete |
| **Total (all phases)** | **63-98 days** | | |

### Key Milestones

| Milestone | Target | Deliverable |
|-----------|--------|-------------|
| M1: Data pipeline operational | Week 2 | Collecting and storing positions/trades for 100 wallets |
| M2: MVP Leaderboard live | Week 3 | Top 100 traders ranked by ROI + win rate + consistency |
| M3: Niche expertise live | Week 4 | Category-specific rankings (Top Politics, Crypto, Sports, AI) |
| M4: Smart Money alerts | Week 5-6 | Telegram/Discord alerts for high-signal trades |
| M5: Edge scoring | Week 7-8 | Predictive accuracy metrics replacing raw profitability |
| M6: Dashboard public | Week 9-10 | Full Next.js dashboard |

---

## 11. Conclusion & Go/No-Go

### Feasibility Verdict: ✅ GO

All seven feasibility questions are answered positively:

| Question | Answer | Confidence |
|----------|--------|-----------|
| Can historical wallet PnL be reconstructed accurately? | **Yes** (via Data API) | High |
| Can open positions be reconstructed from available data? | **Yes** (directly from Data API) | High |
| Can trader performance be tracked over time? | **Yes** (daily snapshots + trade history) | High |
| Can new positions be detected in near real-time? | **Yes** (polling or activity stream) | High |
| What are the API rate limits? | **Documented** (see §4) | High |
| Which source is the source of truth? | **Polymarket Data API** (verified via Polygon chain) | High |
| Is a custom blockchain indexer required? | **No** (not for Phases 1-3) | High |

### Before Starting Phase 1:

1. ✅ This feasibility report has been reviewed and approved.
2. ✅ The architecture recommendation is accepted.
3. ✅ The risks and limitations are acknowledged.
4. ✅ The estimated effort and timeline fit within project constraints.

### Infrastructure Setup Needed for Phase 1:

- [ ] PostgreSQL instance (local dev: Docker; production: Railway/Fly.io managed DB)
- [ ] Redis instance (local dev: Docker; production: Upstash or Railway managed)
- [ ] Python 3.12+ environment with dependencies
- [ ] FastAPI project scaffold
- [ ] Mage AI or simple custom pipeline runner
- [ ] GitHub repository with CI (Ruff, MyPy, Pytest)
- [ ] Docker Compose for local development

---

*End of Feasibility Study Report. Proceed to Phase 1 upon approval.*
