"""Post-run verification: checks every table for row counts, NOT NULL,
referential integrity, analytics quality, and timestamp sanity.

This block is meant to run as the final step after enrichment_ranking_computation.
It raises on failure so the pipeline run is marked as failed.
"""

import os
from datetime import date, datetime, timezone

from pandas import DataFrame
from sqlalchemy import create_engine, text

from default_repo.utils.db_helpers import DATABASE_URL

if "data_loader" not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if "test" not in globals():
    from mage_ai.data_preparation.decorators import test

# ── SQL injection guard: whitelist-only table/column names ────────────
ALLOWED_TABLES = frozenset({
    "markets", "outcomes", "wallets", "events", "trades", "positions",
    "wallet_analytics", "ranking_snapshots", "category_analytics",
    "category_rankings", "categories", "alerts", "alert_rules",
    "wallet_pnl_snapshots", "position_history",
})

ALLOWED_COLUMNS = frozenset({
    # wallet_analytics columns
    "total_pnl", "total_realized_pnl", "total_unrealized_pnl", "roi",
    "total_volume", "total_cost_basis", "win_rate", "num_trades",
    "num_resolved_positions", "profit_factor", "sharpe_ratio", "max_drawdown",
    "avg_position_size", "avg_holding_duration", "consistency_score",
    "experience_score", "wallet_score",
    # wallets columns
    "wallet", "proxy_wallet", "is_tracked", "tier", "first_seen", "last_seen",
    "last_position_sync", "last_trade_sync",
    # positions columns
    "market_id", "outcome_id", "side", "status", "avg_entry_price", "shares",
    "entry_time", "exit_time", "realized_pnl", "unrealized_pnl", "total_pnl",
    # trades columns
    "amount_usd", "fee_usd", "tx_hash",
    # general
    "question", "price", "timestamp", "snapshot_date", "category",
    "id", "label", "condition_id", "list_type", "rank",
})


def _validate_table(tbl: str) -> None:
    if tbl not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {tbl}")


def _validate_column(col: str) -> None:
    if col not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column name: {col}")


def _validate_condition(condition: str) -> None:
    """Parse a simple WHERE clause to ensure only known columns are referenced.
    
    Extracts bare column names (words followed by comparison operators, IS,
    IN, etc.) and validates each one against the allowed set.
    """
    import re
    # Match word-boundary identifiers that appear in SQL predicate position
    tokens = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', condition)
    for token in tokens:
        # Skip SQL keywords
        if token.upper() in {
            "AND", "OR", "NOT", "IN", "IS", "NULL", "WHERE", "SELECT",
            "COUNT", "AS", "ON", "LEFT", "RIGHT", "JOIN", "FROM",
            "TRUE", "FALSE",
        }:
            continue
        # Skip numeric literals
        if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
            continue
        if token not in ALLOWED_COLUMNS:
            raise ValueError(f"Invalid column reference in condition: {token}")


# ── Global defaults (mirrored from default_repo/__init__.py) ─────────
# Override by passing matching keys in trigger variables or environment variables.
DEFAULT_THRESHOLDS = {
    "markets": 50_000,
    "outcomes": 100_000,
    "wallets": int(os.environ.get("VERIFY_MIN_WALLETS", 500)),
    "positions": 5_000,
    "trades": int(os.environ.get("VERIFY_MIN_TRADES", 25000)),
    "wallet_analytics": int(os.environ.get("VERIFY_MIN_WALLET_ANALYTICS", 2)),
    "ranking_snapshots": int(os.environ.get("VERIFY_MIN_RANKING_SNAPSHOTS", 5)),
}

REQUIRED_COLUMNS = {
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


@data_loader
def load_data_from_api(*args, **kwargs) -> DataFrame:
    variables = kwargs.get("variables", {})
    thresholds = {tbl: variables.get(f"min_{tbl}", d) for tbl, d in DEFAULT_THRESHOLDS.items()}

    engine = create_engine(DATABASE_URL)
    errors = []
    today = date.today()

    # ── 1. Row counts ────────────────────────────────────────────────
    print("=== Row counts ===")
    for tbl, min_rows in thresholds.items():
        _validate_table(tbl)
        count = engine.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
        if count < min_rows:
            errors.append(f"{tbl}: {count} rows, expected >= {min_rows}")
        else:
            print(f"  PASS  {tbl}: {count} rows")

    # ── 2. NOT NULL on critical columns ──────────────────────────────
    print("=== NOT NULL checks ===")
    for tbl, cols in REQUIRED_COLUMNS.items():
        _validate_table(tbl)
        for col in cols:
            _validate_column(col)
            nulls = engine.execute(
                text(f"SELECT count(*) FROM {tbl} WHERE {col} IS NULL")
            ).scalar()
            if nulls > 0:
                errors.append(f"{tbl}.{col}: {nulls} NULL values")

    # ── 3. Referential integrity ─────────────────────────────────────
    print("=== Foreign key integrity ===")
    fk_checks = [
        ("positions", "wallets", "wallet", "wallet"),
        ("positions", "markets", "market_id", "id"),
        ("trades", "wallets", "wallet", "wallet"),
        ("trades", "markets", "market_id", "id"),
        ("wallet_analytics", "wallets", "wallet", "wallet"),
        ("ranking_snapshots", "wallets", "wallet", "wallet"),
    ]
    for child, parent, c_col, p_col in fk_checks:
        _validate_table(child)
        _validate_table(parent)
        _validate_column(c_col)
        _validate_column(p_col)
        orphans = engine.execute(
            text(
                f"SELECT count(*) FROM {child} c "
                f"LEFT JOIN {parent} p ON c.{c_col} = p.{p_col} "
                f"WHERE p.{p_col} IS NULL"
            )
        ).scalar()
        if orphans > 0:
            errors.append(f"FK {child}.{c_col} → {parent}.{p_col}: {orphans} orphans")

    # ── 4. Analytics data quality ────────────────────────────────────
    print("=== Analytics quality ===")
    quality_checks = [
        ("total_pnl > 500000 OR total_pnl < -500000", "PNL outside ±100k"),
        ("win_rate IS NOT NULL AND (win_rate < 0 OR win_rate > 1)", "win_rate outside [0,1]"),
        ("wallet_score IS NOT NULL AND (wallet_score < 0 OR wallet_score > 100)", "wallet_score outside [0,100]"),
        ("max_drawdown IS NOT NULL AND max_drawdown > 0", "max_drawdown > 0"),
        ("profit_factor IS NOT NULL AND profit_factor < 0", "profit_factor < 0"),
        ("consistency_score IS NULL", "consistency_score NULL"),
        ("experience_score IS NULL", "experience_score NULL"),
    ]
    for condition, label in quality_checks:
        _validate_condition(condition)
        bad = engine.execute(
            text(f"SELECT count(*) FROM wallet_analytics WHERE {condition}")
        ).scalar()
        if bad > 0:
            errors.append(f"wallet_analytics: {label} ({bad} rows)")

    # ── 5. No future timestamps ──────────────────────────────────────
    print("=== Timestamp sanity ===")
    now = datetime.now(timezone.utc)
    future_trades = engine.execute(
        text("SELECT count(*) FROM trades WHERE timestamp > :now"),
        {"now": now},
    ).scalar()
    if future_trades:
        errors.append(f"trades: {future_trades} future timestamps")

    future_analytics = engine.execute(
        text("SELECT count(*) FROM wallet_analytics WHERE snapshot_date > :today"),
        {"today": today},
    ).scalar()
    if future_analytics:
        errors.append(f"wallet_analytics: {future_analytics} future snapshot_date")

    # ── 6. Ranking diversity ─────────────────────────────────────────
    print("=== Ranking distribution ===")
    rows = engine.execute(
        text("SELECT list_type, count(*) FROM ranking_snapshots GROUP BY list_type")
    ).all()
    found = {r[0]: r[1] for r in rows}
    for lt in ["top_100", "emerging", "consistent"]:
        count = found.get(lt, 0)
        print(f"  {lt}: {count}")
        if count == 0:
            errors.append(f"ranking_snapshots: no entries for '{lt}'")

    engine.dispose()

    if errors:
        msg = "\n".join(errors)
        raise RuntimeError(f"ETL verification FAILED:\n{msg}")

    print("\n=== ETL VERIFICATION PASSED ===")
    return DataFrame({"status": ["passed"], "checked_at": [datetime.now(timezone.utc)]})


@test
def test_output(df) -> None:
    assert df is not None, "The output is undefined"
