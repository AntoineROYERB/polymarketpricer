import json

from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import safe_value

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

NUM_COLS = [
    "total_pnl", "total_realized_pnl", "total_unrealized_pnl",
    "total_bought", "total_sold", "total_redeemed",
    "total_merged", "total_split", "total_rebates",
    "open_position_value",
]
STR_COLS = ["wallet"]
INT_COLS = ["num_activity_events"]
JSON_COLS = ["category_breakdown"]


@data_exporter
def export_data(df: DataFrame, **kwargs) -> None:
    if df.empty:
        print("No PnL snapshots to export")
        return
    print(f"Exporting {len(df)} wallet PnL snapshots")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for _, row in df.iterrows():
            params = {"snapshot_date": row["snapshot_date"]}
            for c in STR_COLS:
                params[c] = row.get(c)
            for c in INT_COLS:
                params[c] = safe_value(row.get(c))
            for c in NUM_COLS:
                params[c] = safe_value(row.get(c))
            for c in JSON_COLS:
                v = row.get(c)
                params[c] = json.dumps(safe_value(v)) if v is not None else None

            conn.execute(
                text("""
                    INSERT INTO wallet_pnl_snapshots (
                        wallet, snapshot_date,
                        total_pnl, total_realized_pnl, total_unrealized_pnl,
                        total_bought, total_sold, total_redeemed,
                        total_merged, total_split, total_rebates,
                        num_activity_events, open_position_value,
                        category_breakdown
                    ) VALUES (
                        :wallet, :snapshot_date,
                        :total_pnl, :total_realized_pnl, :total_unrealized_pnl,
                        :total_bought, :total_sold, :total_redeemed,
                        :total_merged, :total_split, :total_rebates,
                        :num_activity_events, :open_position_value,
                        :category_breakdown
                    )
                    ON CONFLICT (wallet, snapshot_date) DO UPDATE SET
                        total_pnl = EXCLUDED.total_pnl,
                        total_realized_pnl = EXCLUDED.total_realized_pnl,
                        total_unrealized_pnl = EXCLUDED.total_unrealized_pnl,
                        total_bought = EXCLUDED.total_bought,
                        total_sold = EXCLUDED.total_sold,
                        total_redeemed = EXCLUDED.total_redeemed,
                        total_merged = EXCLUDED.total_merged,
                        total_split = EXCLUDED.total_split,
                        total_rebates = EXCLUDED.total_rebates,
                        num_activity_events = EXCLUDED.num_activity_events,
                        open_position_value = EXCLUDED.open_position_value,
                        category_breakdown = EXCLUDED.category_breakdown,
                        computed_at = NOW()
                """),
                params,
            )
    engine.dispose()
    print("PnL snapshot export complete")


@test
def test_output(*args) -> None:
    pass
