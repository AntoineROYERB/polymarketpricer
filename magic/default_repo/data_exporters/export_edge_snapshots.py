from datetime import date
from typing import Any

from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL

UPSERT_SQL = """
INSERT INTO wallet_edge_snapshots (
    wallet, snapshot_date, avg_edge, median_edge,
    edge_consistency, edge_volatility, edge_score,
    num_edge_trades, positive_edge_trades, negative_edge_trades,
    computed_at
)
VALUES (
    :wallet, :snapshot_date, :avg_edge, :median_edge,
    :edge_consistency, :edge_volatility, :edge_score,
    :num_edge_trades, :positive_edge_trades, :negative_edge_trades,
    NOW()
)
ON CONFLICT (wallet, snapshot_date)
DO UPDATE SET
    avg_edge = EXCLUDED.avg_edge,
    median_edge = EXCLUDED.median_edge,
    edge_consistency = EXCLUDED.edge_consistency,
    edge_volatility = EXCLUDED.edge_volatility,
    edge_score = EXCLUDED.edge_score,
    num_edge_trades = EXCLUDED.num_edge_trades,
    positive_edge_trades = EXCLUDED.positive_edge_trades,
    negative_edge_trades = EXCLUDED.negative_edge_trades,
    computed_at = NOW()
"""

_ROW_FIELDS = [
    "median_edge", "edge_consistency", "edge_volatility",
    "edge_score", "positive_edge_trades", "negative_edge_trades",
]


def _row_to_params(row, snapshot_date: date) -> dict[str, Any]:
    params = {
        "wallet": str(row["wallet"]),
        "snapshot_date": snapshot_date,
        "avg_edge": float(row["avg_edge"]),
        "num_edge_trades": int(row["num_edge_trades"]),
    }
    for f in _ROW_FIELDS:
        params[f] = float(row.get(f, 0))
    return params


@data_exporter
def export_data(snapshots: DataFrame, **kwargs) -> None:
    if snapshots.empty:
        print("No edge snapshots to export")
        return
    sd = snapshots.get("snapshot_date", date.today())
    if hasattr(sd, "iloc"):
        sd = sd.iloc[0] if not sd.empty else date.today()

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        params_list = [_row_to_params(row, sd) for _, row in snapshots.iterrows()]
        conn.execute(text(UPSERT_SQL), params_list)
    engine.dispose()
    print(f"Exported {len(snapshots)} edge snapshots")


@test
def test_output(output) -> None:
    assert output is None, "Export function should return None"
