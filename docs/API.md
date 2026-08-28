# API Reference

All routes are under `/api/v1` unless stated otherwise. Interactive documentation is
served at `http://localhost:8000/docs`.

**Authentication.** Read endpoints are open. Every `/follow` and `/portfolio` endpoint
except `/follow/recommendations*` requires a bearer token matching the backend's
`API_KEY`, and returns `401` without it:

```
Authorization: Bearer <API_KEY>
```

The alert WebSocket accepts an optional `api_key` query parameter and closes with code
`4001` on mismatch. Rate limit: 60 requests per minute per client (slowapi).

## `GET /health`

Health check.

## `GET /api/v1/leaderboard`

Top 100 traders ranked by composite wallet score.

**Score formula:** `0.40×edge_score + 0.20×consistency_score + 0.20×normalized_roi + 0.10×experience_score + 0.10×normalized_sharpe`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Results per page (max 500) |
| `offset` | int | 0 | Pagination offset |

Each entry includes `edge_score`, `edge_consistency`, and `num_edge_trades` in addition to the core metrics.

## `GET /api/v1/leaderboard/emerging`

Top 10 emerging traders.

## `GET /api/v1/leaderboard/consistent`

Top 10 most consistent traders.

## `GET /api/v1/leaderboard/edge`

Traders ranked by edge score. Edge per trade = `(exit_price - entry_price) / entry_price`. The wallet `edge_score` is a min-max normalized `avg_edge` across all wallets (0–1). `edge_consistency` is the proportion of trades with positive edge.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Results per page (max 200) |
| `offset` | int | 0 | Pagination offset |

**Example response:**
```json
{
  "data": [
    {
      "rank": 1,
      "wallet": "0x17e5...",
      "edge_score": "0.950000",
      "avg_edge": "0.123400",
      "edge_consistency": "0.870000",
      "num_edge_trades": 45
    }
  ],
  "limit": 50,
  "offset": 0
}
```

---

## `GET /api/v1/wallets/{address}`

Full wallet profile with analytics, current positions, category breakdown, and **edge metrics**.

The `edge_metrics` field (when available) contains the edge scoring snapshot for the wallet.

## `GET /api/v1/markets`

Every ingested market, most traded first.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | — | Filter by category. Matches either the category reported by the Polymarket API or the one derived by the classifier — ~70% of markets only have the derived one |
| `search` | string | — | Case-insensitive substring match on the market question (max 200 chars) |
| `sort` | string | `volume` | `volume`, `liquidity` or `recent` (creation date). Anything else returns `422` |
| `limit` | int | 50 | Results per page (max 500) |
| `offset` | int | 0 | Pagination offset |

The response carries a `total` alongside `data`, `limit` and `offset`, so a client can
paginate without over-fetching. An unknown `category` returns an empty page with
`total: 0` rather than an error.

## `GET /api/v1/categories`

List all 8 market categories with their labels.

## `GET /api/v1/leaderboard/{category}`

Top traders in a specific category, ranked by skill score.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | — | One of `politics`, `crypto`, `sports`, `economics`, `technology`, `ai`, `geopolitics`, `entertainment` |
| `limit` | int | 50 | Results per page (max 200) |
| `offset` | int | 0 | Pagination offset |

**Example response:**

```json
{
  "category": "politics",
  "data": [
    {
      "rank": 1,
      "wallet": "0x17e5...",
      "wallet_score": 0.85,
      "roi": 41.29,
      "win_rate": 0.62,
      "total_pnl": 37053.07,
      "num_trades": 840,
      "total_volume": 89730.34,
      "is_specialist": true
    }
  ],
  "limit": 50,
  "offset": 0
}
```

## `GET /api/v1/leaderboard/{category}/specialists`

Specialist traders in a category (wallets with >30 trades and above-median ROI).

Same response shape as the main category leaderboard, filtered to specialists only.

## `GET /api/v1/wallets/{address}/categories`

Per-category performance breakdown for a wallet.

**Example response:**

```json
{
  "wallet": "0x17e5...",
  "categories": [
    {
      "category": "politics",
      "num_trades": 840,
      "total_volume": 89730.34,
      "total_pnl": 37053.07,
      "roi": 41.29,
      "win_rate": 0.62,
      "profit_factor": 3.21,
      "avg_position_size": 106.82,
      "is_specialist": true,
      "category_rank": 1
    }
  ]
}
```

## `GET /api/v1/wallets/{address}/categories/{category}`

Detailed analytics for a specific wallet+category combination.

**Example response:**

```json
{
  "wallet": "0x17e5...",
  "category": "politics",
  "num_trades": 840,
  "total_volume": 89730.34,
  "total_cost_basis": 52300.00,
  "total_pnl": 37053.07,
  "total_realized_pnl": 28000.00,
  "total_unrealized_pnl": 9053.07,
  "roi": 41.29,
  "win_rate": 0.62,
  "profit_factor": 3.21,
  "avg_position_size": 106.82,
  "avg_holding_duration": "7 days, 3:42:00",
  "is_specialist": true,
  "category_rank": 1
}
```

## `GET /api/v1/alerts`

List detected smart money alerts.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Results per page (max 200) |
| `offset` | int | 0 | Pagination offset |
| `category` | string | — | Filter by category (case-insensitive) |
| `min_score` | decimal | — | Minimum wallet score |
| `wallet` | string | — | Partial-match filter on wallet address |

**Example response:**
```json
{
  "data": [
    {
      "id": "a1b2c3d4-...",
      "wallet": "0x1234...",
      "market_id": "12345",
      "market_question": "Will candidate X win?",
      "action": "NEW_POSITION",
      "price": "0.420000000000",
      "position_size": "12000.00",
      "wallet_score": "89.500000",
      "category": "Politics",
      "detected_at": "2026-06-24T12:00:00Z",
      "notified_at": null
    }
  ],
  "limit": 50,
  "offset": 0
}
```

## `GET /api/v1/alerts/{wallet}`

Alerts for a specific wallet address (paginated).

## `GET /api/v1/alerts/stats`

Aggregated alert statistics.

**Example response:**
```json
{
  "total_alerts": 142,
  "alerts_today": 12,
  "top_categories": [
    {"category": "Politics", "count": 58},
    {"category": "Crypto", "count": 43}
  ],
  "top_wallets": [
    {"wallet": "0x1234...", "alert_count": 15},
    {"wallet": "0xabcd...", "alert_count": 10}
  ]
}
```

---

## `GET /api/v1/wallets/{address}/edge`

Latest edge scoring snapshot for a specific wallet.

**Example response:**
```json
{
  "wallet": "0x17e5...",
  "snapshot_date": "2026-06-27",
  "avg_edge": "0.123400",
  "median_edge": "0.110000",
  "edge_consistency": "0.870000",
  "edge_volatility": "0.050000",
  "edge_score": "0.950000",
  "num_edge_trades": 45,
  "positive_edge_trades": 39,
  "negative_edge_trades": 6,
  "computed_at": "2026-06-27T23:59:59Z"
}
```

When no edge data exists, returns a default response with `avg_edge: 0` and `num_edge_trades: 0`.

---

## `WS /api/v1/alerts/ws`

Real-time WebSocket stream of new smart money alerts. The server sends heartbeat pings (`{"type": "ping"}`) and alert payloads (`{"type": "alert", "payload": {...}}`). Clients should respond with `{"type": "pong"}` to keep the connection alive.

**Authentication is required.** Browsers cannot set headers on a WebSocket handshake, so
the key travels as a query parameter instead of an `Authorization` header:

```
ws://localhost:8000/api/v1/alerts/ws?api_key=<API_KEY>
```

A missing, empty or incorrect key closes the socket with code `4001`, as does a request
carrying an `Origin` header outside `CORS_ORIGINS`. Because the key appears in the URL it
can be captured by proxy and access logs; behind a real deployment, terminate TLS and
rotate the key rather than treating the URL as private.


---

## `GET /api/v1/markets/{market_id}`

Detailed market info: outcomes with current prices, buy/sell sentiment ratio, and the
tracked wallets active in the market.

---

# Follow

Requires `Authorization: Bearer <API_KEY>` unless noted.

## `GET /api/v1/follow`

List the wallets the user follows.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `active` | bool | `true` | Only active follows |
| `auto_copy` | bool | — | Filter on whether copy trading is enabled |

Each entry: `id`, `wallet`, `label`, `active`, `auto_copy_enabled`, `copy_mode`,
`copy_value`, `category_filter`, `followed_at`, `updated_at`.

## `POST /api/v1/follow/{wallet}`

Start following a wallet.

```json
{
  "label": "sports specialist",
  "auto_copy_enabled": true,
  "copy_mode": "fixed",
  "copy_value": "50.00",
  "category_filter": "sports"
}
```

`copy_mode` is one of `fixed` (a fixed USD amount per copied trade), `proportional`
(scaled to the followed wallet's position size) or `percentage` (a share of the paper
portfolio balance). `category_filter` restricts copying to a single category.

## `PATCH /api/v1/follow/{wallet}`

Update a follow's configuration. Same fields as above, plus `active`.

## `DELETE /api/v1/follow/{wallet}`

Unfollow (soft delete — the row is kept with `unfollowed_at` set).

## `GET /api/v1/follow/recommendations`

Wallets ranked by global follow score, each with a `FOLLOW` / `WATCH` / `IGNORE`
recommendation and the reasons behind it. No authentication required.

**Score formula:** `0.30×edge + 0.20×consistency + 0.20×specialization + 0.15×recency + 0.15×frequency`,
where recency decays as `e^(−days/90)` and frequency is a sigmoid over trades per month.
Thresholds: `FOLLOW` at ≥ 0.70, `WATCH` at ≥ 0.35.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Results per page |
| `offset` | int | 0 | Pagination offset |

## `GET /api/v1/follow/recommendations/by-category/{category}`

Same, restricted to one category and scored with the per-category weights
(`0.25×edge + 0.25×roi_percentile + 0.20×win_rate + 0.15×specialist_bonus + 0.10×volume_percentile + 0.05×recency`).

## `GET /api/v1/follow/recommendations/{wallet}/by-category`

Per-category follow scores for a single wallet.

---

# Portfolio (paper trading)

Requires `Authorization: Bearer <API_KEY>`. All trades are simulated; the service never
touches a wallet or real funds.

## `GET /api/v1/portfolio`

Portfolio overview: `initial_balance`, `current_balance`, `total_realized_pnl`,
`total_unrealized_pnl`, `total_pnl`, `total_roi`, `total_trades`, `total_volume`.

## `GET /api/v1/portfolio/positions`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | str | `OPEN` | `OPEN` or `CLOSED` |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Pagination offset |

## `GET /api/v1/portfolio/trades`

Paper trade history, most recent first (`limit`, `offset`).

## `POST /api/v1/portfolio/positions/{position_id}/close`

Close an open position at the current market price.

## `POST /api/v1/portfolio/reset`

Clear all positions and trades and set a new starting balance.
