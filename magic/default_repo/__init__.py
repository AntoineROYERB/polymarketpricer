"""Polymarket ETL — global variables and defaults.

All POLYMARKET_* constants are used across pipelines, triggers,
and the post-run verification block. Override at trigger runtime
by passing matching keys in trigger variables.
"""

import os

# ── Row count thresholds for post-run verification ───────────────────
POLYMARKET_MIN_MARKETS = 50_000
POLYMARKET_MIN_OUTCOMES = 100_000
POLYMARKET_MIN_WALLETS = 1_000
POLYMARKET_MIN_POSITIONS = 5_000
POLYMARKET_MIN_TRADES = 50_000
POLYMARKET_MIN_ANALYTICS = 500
POLYMARKET_MIN_RANKINGS = 100

# ── Ranking eligibility ──────────────────────────────────────────────
POLYMARKET_MIN_TRADES_FOR_RANKING = 50
POLYMARKET_MIN_VOLUME_FOR_RANKING = 1_000

# ── Pipeline-level SLA (seconds) ────────────────────────────────────
POLYMARKET_TIMEOUT_MARKET_DISCOVERY = 120
POLYMARKET_TIMEOUT_WALLET_DISCOVERY = 120
POLYMARKET_TIMEOUT_POSITION_SYNC = 120
POLYMARKET_TIMEOUT_TRADE_HISTORY = 120
POLYMARKET_TIMEOUT_ANALYTICS = 60
POLYMARKET_TIMEOUT_RANKING = 30

# ── Global ETL SLA (seconds) ────────────────────────────────────────
POLYMARKET_TOTAL_SLA_SECONDS = 300  # 5 minutes

# ── Database ─────────────────────────────────────────────────────────
POLYMARKET_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://app:changeme@postgres:5432/polymarket",
)

# ── Required columns per table (for NOT NULL verification) ───────────
POLYMARKET_REQUIRED_COLUMNS = {
    "markets": ["id", "question"],
    "outcomes": ["id", "market_id", "label"],
    "wallets": ["wallet"],
    "positions": ["wallet", "market_id", "status"],
    "trades": [
        "id", "wallet", "market_id", "side",
        "price", "shares", "amount_usd", "timestamp",
    ],
    "wallet_analytics": [
        "wallet", "snapshot_date", "total_pnl", "roi",
        "num_trades", "consistency_score", "experience_score",
        "wallet_score",
    ],
    "ranking_snapshots": [
        "wallet", "snapshot_date", "list_type", "rank", "wallet_score",
    ],
}
