from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_exporter
def export_data(data: dict, **kwargs) -> None:
    rankings = data.get("rankings", DataFrame())
    wallet_scores = data.get("wallet_scores", DataFrame())

    if rankings.empty:
        return

    engine = create_engine(DATABASE_URL)

    print(f"Materializing {len(rankings)} ranking rows, updating {len(wallet_scores)} wallet scores")
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                DELETE FROM ranking_snapshots
                WHERE snapshot_date = CURRENT_DATE
            """)
        )
        print(f"Deleted {result.rowcount} existing ranking snapshots for today")

    with engine.begin() as conn:
        for _, row in rankings.iterrows():
            conn.execute(
                text("""
                    INSERT INTO ranking_snapshots (
                        wallet, snapshot_date, list_type, rank, wallet_score,
                        roi, win_rate, consistency_score, experience_score,
                        risk_adj_return, total_pnl, num_trades
                    ) VALUES (
                        :wallet, :snapshot_date, :list_type, :rank, :wallet_score,
                        :roi, :win_rate, :consistency_score, :experience_score,
                        :risk_adj_return, :total_pnl, :num_trades
                    )
                """),
                {
                    "wallet": row["wallet"],
                    "snapshot_date": row["snapshot_date"],
                    "list_type": row["list_type"],
                    "rank": row["rank"],
                    "wallet_score": row.get("wallet_score"),
                    "roi": row.get("roi"),
                    "win_rate": row.get("win_rate"),
                    "consistency_score": row.get("consistency_score"),
                    "experience_score": row.get("experience_score"),
                    "risk_adj_return": row.get("risk_adj_return"),
                    "total_pnl": row.get("total_pnl"),
                    "num_trades": row.get("num_trades"),
                },
            )

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
