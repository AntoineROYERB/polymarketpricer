# Smart Money Alerts & Discord Delivery

The system automatically detects when top-performing Polymarket traders open, increase, decrease, or close positions, and delivers real-time alerts via Discord and WebSocket.

## Detection Pipeline

The `smart_money_detection` Mage AI pipeline runs after each ETL cycle and evaluates three types of signals:

| Transformer | Signal | Description |
|---|---|---|
| `detect_smart_money_alerts` | Position changes | Compares current vs. previous position snapshots to identify `NEW_POSITION`, `POSITION_INCREASE`, `POSITION_DECREASE`, and `FULL_EXIT` actions |
| `detect_trade_alerts` | Recent trades | Flags large trades from high-scoring wallets |
| `detect_first_movers` | Early entry | Detects smart money entering a market within minutes of its creation |

Each candidate alert is checked against configurable thresholds defined in the `alert_rules` table:

| Rule | Default | Description |
|---|---|---|
| `min_score` | 80 | Minimum wallet skill score (0–100) |
| `min_position_size` | $500 | Minimum position size in USD |
| `min_liquidity` | $1,000 | Minimum market liquidity |
| `cooldown_minutes` | 15 | Minimum interval between alerts for the same wallet+market pair |

Rules can be set globally (with a `wallet = NULL` row) or per-wallet for custom thresholds. Alerts that pass all checks are inserted into the `alerts` table with their classification, price, size, and wallet metadata.

## Delivery Flow

Once alerts are persisted, a background loop inside the FastAPI application (`app/main.py`) handles delivery:

```
┌─────────────────────────────────────────────────────┐
│  alert_delivery_loop() — runs every N seconds       │
│                                                      │
│  1. Poll unnofified alerts (notified_at IS NULL)     │
│  2. For each alert:                                  │
│     ├─ Broadcast to WebSocket clients                │
│     └─ If DISCORD_WEBHOOK_URL is set:                │
│          └─ POST rich embed to Discord webhook       │
│  3. Mark alert as notified (or increment attempts)   │
└─────────────────────────────────────────────────────┘
```

- **Poll interval** is configurable via `ALERT_POLL_INTERVAL_SECONDS` (default: `10`).
- Alerts with 3 or more failed delivery attempts are skipped.
- WebSocket delivery always runs; Discord delivery is optional.

## Discord Embed Format

When a Discord webhook URL is configured (`DISCORD_WEBHOOK_URL` in `.env`), alerts are sent as richly formatted embeds:

```json
{
  "embeds": [{
    "title": "🚨 Smart Money Alert",
    "color": 0x2ECC71,          // Green = new, Blue = increase,
                                // Orange = decrease, Red = exit
    "fields": [
      { "name": "Trader",   "value": "`0x1234...abcd`",     "inline": true },
      { "name": "Score",    "value": "89.50",               "inline": true },
      { "name": "Category", "value": "Politics",            "inline": true },
      { "name": "Action",   "value": "BUY (New Position @ $0.4200)", "inline": true },
      { "name": "Market",   "value": "Will candidate X win?",         "inline": false },
      { "name": "Price",    "value": "$0.4200",              "inline": true },
      { "name": "Position Size", "value": "$12,000.00",     "inline": true }
    ],
    "footer": { "text": "Polymarket Smart Money Tracker" },
    "timestamp": "2026-06-24T12:00:00Z"
  }]
}
```

The embed color reflects the action type:

| Action | Color |
|---|---|
| `NEW_POSITION` | 🟢 Green (`#2ECC71`) |
| `POSITION_INCREASE` | 🔵 Blue (`#3498DB`) |
| `POSITION_DECREASE` | 🟠 Orange (`#E67E22`) |
| `FULL_EXIT` | 🔴 Red (`#E74C3C`) |

## API & WebSocket Access

Alerts are also available programmatically without Discord:

| Endpoint | Description |
|---|---|
| `GET /api/v1/alerts` | List alerts with filters (`category`, `min_score`, `wallet`) |
| `GET /api/v1/alerts/{wallet}` | Alerts for a specific wallet |
| `GET /api/v1/alerts/stats` | Aggregated statistics (totals, top categories, top wallets) |
| `WS /api/v1/alerts/ws` | Real-time stream — receives `{"type": "alert", "payload": {...}}` messages as they are detected |

## Setup

To enable Discord notifications:

1. Create a Discord webhook in your server (Server Settings → Integrations → Webhooks).
2. Add the URL to your `.env`:
   ```env
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   ```
3. Restart the app. No other configuration is needed.

When `DISCORD_WEBHOOK_URL` is empty (default), alerts are still written to the database and available via API/WebSocket — Discord delivery is simply skipped.
