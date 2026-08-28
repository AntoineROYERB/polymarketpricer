# Database Schema

## Tables

| Table | Purpose |
|-------|---------|
| `events` | Event metadata (titles, slugs, categories) |
| `markets` | Market metadata (question, category, outcomes, resolution) |
| `outcomes` | Market outcome tokens (token_id, price, winner flag) |
| `trades` | Individual trade records (wallet, market, side, price, shares) |
| `wallets` | Wallet identity with proxy wallet mapping |
| `positions` | Current open positions (avg entry, shares, PnL) |
| `position_history` | Historical snapshots of position changes (diff tracking) |
| `wallet_pnl_snapshots` | Cashflow-reconstructed PnL from `/activity` endpoint |
| `wallet_analytics` | Daily snapshots of computed metrics and ranking scores |
| `ranking_snapshots` | Materialized top-100 / emerging / consistent rankings |
| `wallet_edge_snapshots` | Per-wallet edge scoring metrics (FIFO matching, avg_edge, edge_score) |
| `category_analytics` | Per-wallet, per-category PnL, ROI, win rate, specialist flags |
| `category_rankings` | Top-50 rankings per category (+ specialist lists) |
| `categories` | Lookup table for the 8 target categories |
| `alerts` | Detected high-signal trading events (smart money) |
| `alert_rules` | Configurable threshold configuration for alert generation |
| `pipeline_run_log` | Execution history of Mage ETL pipeline runs |
| `wallet_category_follow_scores` | Per-wallet, per-category follow score, recommendation and reasons |
| `wallet_follows` | Wallets a user follows, with copy mode and category filter |
| `paper_portfolios` | Simulated portfolios (balance, realized/unrealized PnL, ROI) |
| `paper_positions` | Open and closed simulated positions |
| `paper_trades` | Simulated fills, linked to the source alert and followed wallet |

### Key Relationships

- `wallet_edge_snapshots.wallet` → `wallets.wallet` (FK), composite PK `(wallet, snapshot_date)`
- `wallet_analytics.edge_score` → computed from `wallet_edge_snapshots` (LEFT JOIN)
- `ranking_snapshots.edge_score` → propagated from `wallet_analytics`
- `wallet_category_follow_scores` composite PK `(wallet, category, snapshot_date)`, FKs to `wallets` and `categories`
- `paper_positions` / `paper_trades` → `paper_portfolios`, `markets`, `wallets` (followed wallet) and optionally `alerts` (source alert)

All monetary and score columns use `NUMERIC` rather than floating point, so PnL and ROI
arithmetic is exact end to end.

## Category Classification

Markets are classified into 8 target categories using a 3-tier classifier:

| Tier | Method | Description |
|------|--------|-------------|
| 1 | Raw API map | Direct mapping from API's `category` field to target category |
| 2 | Event inheritance | Inherits category from parent event when available |
| 3 | Keyword rules | 300+ keywords matched against market question text |

**Categories:** `politics`, `crypto`, `sports`, `economics`, `technology`, `ai`, `geopolitics`, `entertainment`

Classifier source: `magic/default_repo/utils/category_classifier.py`

## Migrations

Database migrations are managed via Alembic under `alembic/versions/`:

| Migration | Description |
|---|---|
| `001_initial.py` | Core tables: events, markets, outcomes, wallets, trades, positions, position_history, wallet_analytics, ranking_snapshots |
| `002_category_analytics.py` | Category analytics and rankings tables |
| `003_add_mapped_category.py` | Add `mapped_category` column to markets |
| `004_add_categories_table.py` | Lookup table for the 8 categories |
| `005_smart_money_alerts.py` | Alerts and alert_rules tables |
| `006_drop_outcome_id_fks.py` | Clean up foreign keys on outcome_id |
| `007_add_wallet_pnl_snapshots.py` | Cashflow PnL snapshots table |
| `008_drop_trades_outcome_id_fk.py` | Remove dangling FK from trades to outcomes |
| `009_add_sync_indexes.py` | Performance indexes for ETL sync operations |
| `010_add_wallet_tier.py` | Wallet tier column for incremental sync |
| `011_add_alert_action_index.py` | Index on alerts.action for faster filtering |
| `012_add_condition_id_to_markets.py` | Add `condition_id` column for CLOB API lookups |
| `013_fix_min_score_default.py` | Fix default value of alert_rules.min_score |
| `014_add_pipeline_run_log.py` | Pipeline execution tracking table |
| `015_increase_wallet_analytics_precision.py` | Widen numeric precision to `NUMERIC(28,6)` |
| `016_increase_ranking_snapshots_precision.py` | Same precision widening for ranking_snapshots |
| `017_add_edge_scoring.py` | New `wallet_edge_snapshots` table + `edge_score` columns on `wallet_analytics` and `ranking_snapshots` |
| `018_add_wallet_follows.py` | `wallet_follows` table (label, copy mode, copy value, category filter, soft delete) |
| `019_add_paper_trading.py` | `paper_portfolios`, `paper_positions`, `paper_trades` tables |
| `020_add_follow_score.py` | `follow_score` column on `wallet_analytics` |
| `021_add_category_follow_scores.py` | `wallet_category_follow_scores` table + `category_follow_scores` column on `wallet_analytics` |

### Migration 017 — Edge Scoring Details

Creates the `wallet_edge_snapshots` table with:

| Column | Type | Description |
|--------|------|-------------|
| `wallet` | TEXT (PK, FK→wallets) | Wallet address |
| `snapshot_date` | DATE (PK) | Date of the edge computation |
| `avg_edge` | NUMERIC(28,6) | Average edge across all trades for this wallet |
| `median_edge` | NUMERIC(28,6) | Median edge |
| `edge_consistency` | NUMERIC(28,6) | Proportion of trades with positive edge |
| `edge_volatility` | NUMERIC(28,6) | Standard deviation of edge values |
| `edge_score` | NUMERIC(28,6) | Min-max normalized avg_edge (0–1) |
| `num_edge_trades` | INTEGER | Number of trades used in edge computation |
| `positive_edge_trades` | INTEGER | Count of trades with positive edge |
| `negative_edge_trades` | INTEGER | Count of trades with negative edge |
| `computed_at` | TIMESTAMPTZ | When the computation was performed |

Indexes: `(wallet, snapshot_date DESC)`, `(snapshot_date DESC)`, `(edge_score DESC)`.
