from datetime import datetime, timezone

from pandas import DataFrame, isna
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL

POS_COLS = [
    "wallet", "market_id", "outcome_id", "side", "status",
    "avg_entry_price", "shares", "entry_time", "exit_time",
    "realized_pnl", "unrealized_pnl", "total_pnl",
]
HIST_COLS = [
    "wallet", "market_id", "outcome_id", "side",
    "shares_before", "shares_after", "pnl_change", "recorded_at",
]


def row_gen(df):
    for _, r in df.iterrows():
        yield tuple(None if isna(v) else v for v in (r.get(c) for c in POS_COLS))


@transformer
def transform_df(positions: DataFrame, *args, **kwargs) -> dict:
    """Diff positions against DB using SQL temp table + CTEs (no pandas merge)."""
    now = datetime.now(timezone.utc)

    engine = create_engine(DATABASE_URL)
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()

        new_count = changed_count = closed_count = 0

        if not positions.empty:
            before = len(positions)
            positions = positions.drop_duplicates(subset=["wallet", "market_id"], keep="last")
            if len(positions) < before:
                print(f"Deduplicated {before - len(positions)} duplicate wallet+market_id rows")

            cur.execute(
                "CREATE TEMP TABLE _cp (LIKE positions INCLUDING DEFAULTS) "
                "ON COMMIT DROP"
            )

            execute_values(
                cur,
                f"INSERT INTO _cp ({', '.join(POS_COLS)}) VALUES %s",
                row_gen(positions),
                page_size=5000,
            )
            print(f"Bulk inserted {len(positions)} rows into temp table")

            cur.execute("""
                INSERT INTO positions (wallet, market_id, outcome_id, side, status,
                                       avg_entry_price, shares, entry_time, exit_time,
                                       realized_pnl, unrealized_pnl, total_pnl)
                SELECT cp.wallet, cp.market_id, cp.outcome_id, cp.side, 'OPEN',
                       cp.avg_entry_price, cp.shares,
                       COALESCE(cp.entry_time, %(now)s), NULL,
                       cp.realized_pnl, cp.unrealized_pnl, cp.total_pnl
                FROM _cp cp
                WHERE NOT EXISTS (
                    SELECT 1 FROM positions p
                    WHERE p.wallet = cp.wallet AND p.market_id = cp.market_id
                )
                ON CONFLICT (wallet, market_id) DO NOTHING
            """, {"now": now})
            new_count = cur.rowcount
            print(f"New positions: {new_count}")

            cur.execute("""
                WITH changed AS (
                    UPDATE positions p
                    SET outcome_id = cp.outcome_id,
                        side = cp.side,
                        status = 'OPEN',
                        avg_entry_price = cp.avg_entry_price,
                        shares = cp.shares,
                        entry_time = COALESCE(p.entry_time, cp.entry_time),
                        exit_time = NULL,
                        realized_pnl = cp.realized_pnl,
                        unrealized_pnl = cp.unrealized_pnl,
                        total_pnl = cp.total_pnl
                    FROM _cp cp
                    WHERE p.wallet = cp.wallet AND p.market_id = cp.market_id
                      AND (p.shares IS DISTINCT FROM cp.shares
                           OR p.status IS DISTINCT FROM 'OPEN'
                           OR p.realized_pnl IS DISTINCT FROM cp.realized_pnl)
                    RETURNING p.wallet, p.market_id, cp.outcome_id, cp.side,
                              p.shares AS shares_before,
                              cp.shares AS shares_after,
                              cp.realized_pnl,
                              p.realized_pnl AS pnl_before
                )
                INSERT INTO position_history (wallet, market_id, outcome_id, side,
                                              shares_before, shares_after,
                                              pnl_change, recorded_at)
                SELECT wallet, market_id, outcome_id, side,
                       shares_before, shares_after,
                       COALESCE(realized_pnl, 0) - COALESCE(pnl_before, 0) AS pnl_change,
                       %(now)s
                FROM changed
                WHERE shares_before IS DISTINCT FROM shares_after
                   OR COALESCE(realized_pnl, 0) != COALESCE(pnl_before, 0)
            """, {"now": now})
            changed_count = cur.rowcount
            print(f"Changed positions: {changed_count}")

            cur.execute("""
                WITH closed AS (
                    UPDATE positions p
                    SET status = 'CLOSED',
                        exit_time = %(now)s,
                        shares = 0
                    WHERE p.status != 'CLOSED'
                      AND NOT EXISTS (
                        SELECT 1 FROM _cp cp
                        WHERE cp.wallet = p.wallet
                          AND cp.market_id = p.market_id
                    )
                    RETURNING p.wallet, p.market_id, p.outcome_id, p.side,
                              p.shares AS shares_before
                )
                INSERT INTO position_history (wallet, market_id, outcome_id, side,
                                              shares_before, shares_after,
                                              pnl_change, recorded_at)
                SELECT wallet, market_id, outcome_id, side,
                       shares_before, 0, 0, %(now)s
                FROM closed
                WHERE shares_before != 0
            """, {"now": now})
            closed_count = cur.rowcount
            print(f"Closed positions: {closed_count}")
        else:
            cur.execute("""
                WITH closed AS (
                    UPDATE positions p
                    SET status = 'CLOSED',
                        exit_time = %(now)s,
                        shares = 0
                    WHERE p.status != 'CLOSED'
                    RETURNING p.wallet, p.market_id, p.outcome_id, p.side,
                              p.shares AS shares_before
                )
                INSERT INTO position_history (wallet, market_id, outcome_id, side,
                                              shares_before, shares_after,
                                              pnl_change, recorded_at)
                SELECT wallet, market_id, outcome_id, side,
                       shares_before, 0, 0, %(now)s
                FROM closed
                WHERE shares_before != 0
            """, {"now": now})
            closed_count = cur.rowcount
            print(f"Closed positions (no API data): {closed_count}")

        raw.commit()

        processed_wallets = positions["wallet"].dropna().unique().tolist() if not positions.empty else []
        if processed_wallets:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE wallets
                        SET last_position_sync = :now
                        WHERE wallet = ANY(:wallets)
                    """),
                    {"now": now, "wallets": processed_wallets},
                )
            print(f"Updated last_position_sync for {len(processed_wallets)} wallets")
    finally:
        raw.close()
        engine.dispose()

    print(f"Position sync: {new_count} new, {changed_count} changed, {closed_count} closed")
    return {"positions": DataFrame(columns=POS_COLS), "position_history": DataFrame(columns=HIST_COLS)}


@test
def test_output(result) -> None:
    assert "positions" in result, "Missing positions"
    assert "position_history" in result, "Missing position_history"
