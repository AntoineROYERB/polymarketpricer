from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from utils.db_helpers import safe_value

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


ANALYTICS_NUM_COLS = [
    "total_volume", "total_cost_basis", "total_pnl",
    "total_realized_pnl", "total_unrealized_pnl",
    "roi", "win_rate", "profit_factor", "avg_position_size",
]
ANALYTICS_INT_COLS = ["num_trades", "num_resolved_positions"]

RANKING_NUM_COLS = ["roi", "win_rate", "total_pnl", "total_volume"]
RANKING_INT_COLS = ["num_trades"]


@data_exporter
def export_data(data: dict, **kwargs) -> None:
    analytics = data.get("analytics", DataFrame())
    rankings = data.get("rankings", DataFrame())

    engine = create_engine(DATABASE_URL)

    # Step 1: Upsert category_analytics
    if not analytics.empty:
        print(f"Exporting {len(analytics)} category analytics rows")
        with engine.begin() as conn:
            # Delete existing rows for today to avoid duplicates
            today = analytics["snapshot_date"].iloc[0]
            conn.execute(
                text("DELETE FROM category_analytics WHERE snapshot_date = :sd"),
                {"sd": today},
            )
            print(f"  cleared category_analytics for snapshot_date={today}")

            for _, row in analytics.iterrows():
                params = {
                    "wallet": row["wallet"],
                    "category": row["category"],
                    "snapshot_date": row["snapshot_date"],
                    "is_specialist": bool(row.get("is_specialist", False)),
                    "category_rank": safe_value(row.get("category_rank")),
                }
                for c in ANALYTICS_INT_COLS:
                    params[c] = safe_value(row.get(c))
                for c in ANALYTICS_NUM_COLS:
                    params[c] = safe_value(row.get(c))
                params["avg_holding_duration"] = safe_value(row.get("avg_holding_duration"))

                conn.execute(
                    text("""
                        INSERT INTO category_analytics (
                            wallet, category, snapshot_date, num_trades,
                            total_volume, total_cost_basis, total_pnl,
                            total_realized_pnl, total_unrealized_pnl,
                            roi, win_rate, num_resolved_positions,
                            profit_factor, avg_position_size,
                            avg_holding_duration, is_specialist, category_rank
                        ) VALUES (
                            :wallet, :category, :snapshot_date, :num_trades,
                            :total_volume, :total_cost_basis, :total_pnl,
                            :total_realized_pnl, :total_unrealized_pnl,
                            :roi, :win_rate, :num_resolved_positions,
                            :profit_factor, :avg_position_size,
                            :avg_holding_duration, :is_specialist, :category_rank
                        )
                        ON CONFLICT (wallet, category, snapshot_date) DO UPDATE SET
                            num_trades = EXCLUDED.num_trades,
                            total_volume = EXCLUDED.total_volume,
                            total_cost_basis = EXCLUDED.total_cost_basis,
                            total_pnl = EXCLUDED.total_pnl,
                            total_realized_pnl = EXCLUDED.total_realized_pnl,
                            total_unrealized_pnl = EXCLUDED.total_unrealized_pnl,
                            roi = EXCLUDED.roi,
                            win_rate = EXCLUDED.win_rate,
                            num_resolved_positions = EXCLUDED.num_resolved_positions,
                            profit_factor = EXCLUDED.profit_factor,
                            avg_position_size = EXCLUDED.avg_position_size,
                            avg_holding_duration = EXCLUDED.avg_holding_duration,
                            is_specialist = EXCLUDED.is_specialist,
                            category_rank = EXCLUDED.category_rank
                    """),
                    params,
                )
    else:
        print("No category analytics to export")

    # Step 2: Replace category_rankings for today
    if not rankings.empty:
        print(f"Exporting {len(rankings)} category ranking rows")
        with engine.begin() as conn:
            today = rankings["snapshot_date"].iloc[0]
            conn.execute(
                text("DELETE FROM category_rankings WHERE snapshot_date = :sd"),
                {"sd": today},
            )
            print(f"  cleared category_rankings for snapshot_date={today}")

            for _, row in rankings.iterrows():
                params = {
                    "wallet": row["wallet"],
                    "category": row["category"],
                    "snapshot_date": row["snapshot_date"],
                    "list_type": row["list_type"],
                    "rank": int(row["rank"]),
                }
                for c in RANKING_NUM_COLS:
                    params[c] = safe_value(row.get(c))
                for c in RANKING_INT_COLS:
                    params[c] = safe_value(row.get(c))

                conn.execute(
                    text("""
                        INSERT INTO category_rankings (
                            wallet, category, snapshot_date, list_type,
                            rank, roi, win_rate, total_pnl, num_trades, total_volume
                        ) VALUES (
                            :wallet, :category, :snapshot_date, :list_type,
                            :rank, :roi, :win_rate, :total_pnl, :num_trades, :total_volume
                        )
                    """),
                    params,
                )
    else:
        print("No category rankings to export")

    engine.dispose()
    print("Category analytics export complete")
