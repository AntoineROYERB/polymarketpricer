# Database Schema

## Tables

| Table | Purpose |
|-------|---------|
| `markets` | Market metadata (question, category, outcomes, resolution) |
| `trades` | Individual trade records (wallet, market, side, price, shares) |
| `wallets` | Wallet identity with proxy wallet mapping |
| `positions` | Current open positions (avg entry, shares, PnL) |
| `wallet_pnl_snapshots` | Cashflow-reconstructed PnL from `/activity` endpoint |
| `wallet_analytics` | Daily snapshots of computed metrics and ranking scores |
| `category_analytics` | Per-wallet, per-category PnL, ROI, win rate, specialist flags |
| `category_rankings` | Top-50 rankings per category (+ specialist lists) |
| `categories` | Lookup table for the 8 target categories |
| `alerts` | Detected high-signal trading events (smart money) |
| `alert_rules` | Configurable threshold configuration for alert generation |

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
| `001_initial.py` | Core tables: markets, trades, wallets, positions |
| `002_category_analytics.py` | Category analytics and rankings tables |
| `003_add_mapped_category.py` | Add mapped_category column to markets |
| `004_add_categories_table.py` | Lookup table for the 8 categories |
| `005_smart_money_alerts.py` | Alerts and alert_rules tables |
| `006_drop_outcome_id_fks.py` | Clean up foreign keys on outcome_id |
| `007_add_wallet_pnl_snapshots.py` | Cashflow PnL snapshots table |
