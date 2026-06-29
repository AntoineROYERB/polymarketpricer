# API Reference

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

List known markets.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | — | Filter by category |
| `limit` | int | 50 | Results per page (max 500) |
| `offset` | int | 0 | Pagination offset |

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
