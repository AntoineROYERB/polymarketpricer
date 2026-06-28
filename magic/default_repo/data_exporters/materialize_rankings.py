from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from default_repo.utils.db_helpers import DATABASE_URL


INSERT_RANKING_SQL = """
    INSERT INTO ranking_snapshots (
        wallet, snapshot_date, list_type, rank, wallet_score,
        roi, win_rate, consistency_score, experience_score,
        risk_adj_return, total_pnl, num_trades, edge_score
    ) VALUES (
        :wallet, :snapshot_date, :list_type, :rank, :wallet_score,
        :roi, :win_rate, :consistency_score, :experience_score,
        :risk_adj_return, :total_pnl, :num_trades, :edge_score
    )
"""

_INSERT_FIELDS = [
    "wallet_score", "roi", "win_rate", "consistency_score",
    "experience_score", "risk_adj_return", "total_pnl", "num_trades", "edge_score",
]


def _ranking_row_params(row) -> dict:
    params = {
        "wallet": row["wallet"],
        "snapshot_date": row["snapshot_date"],
        "list_type": row["list_type"],
        "rank": row["rank"],
    }
    for f in _INSERT_FIELDS:
        params[f] = row.get(f)
    return params


@data_exporter
def export_data(data: dict, **kwargs) -> None:
    rankings = data.get("rankings", DataFrame())
    wallet_scores = data.get("wallet_scores", DataFrame())

    if rankings.empty:
        return

    engine = create_engine(DATABASE_URL)

    print(f"Materializing {len(rankings)} ranking rows, updating {len(wallet_scores)} wallet scores")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ranking_snapshots WHERE snapshot_date = CURRENT_DATE"))
        params_list = [_ranking_row_params(row) for _, row in rankings.iterrows()]
        conn.execute(text(INSERT_RANKING_SQL), params_list)

    if not wallet_scores.empty:
        print(f"Updating wallet_score in wallet_analytics for {len(wallet_scores)} wallets")
        with engine.begin() as conn:
            for _, row in wallet_scores.iterrows():
                conn.execute(
                    text("""
                        UPDATE wallet_analytics
                        SET wallet_score = :wallet_score
                        WHERE wallet = :wallet AND snapshot_date = :snapshot_date
                    """),
                    {
                        "wallet_score": row.get("wallet_score"),
                        "wallet": row["wallet"],
                        "snapshot_date": row["snapshot_date"],
                    },
                )

    engine.dispose()
    print("Ranking materialization complete")
