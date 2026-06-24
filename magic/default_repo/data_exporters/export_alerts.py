from datetime import datetime, timezone

from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_exporter
def export_data(alerts: DataFrame, **kwargs) -> None:
    if alerts.empty:
        print("No alerts to export")
        return

    engine = create_engine(DATABASE_URL)
    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        for _, row in alerts.iterrows():
            existing = conn.execute(text("""
                SELECT 1 FROM alerts
                WHERE wallet = :wallet
                  AND market_id = :market_id
                  AND action = :action
                  AND detected_at > NOW() - (
                      SELECT COALESCE(
                          (
                              SELECT (cooldown_minutes || ' minutes')::interval
                              FROM alert_rules
                              WHERE (wallet = :wallet OR wallet IS NULL)
                              ORDER BY wallet NULLS LAST
                              LIMIT 1
                          ),
                          '15 minutes'::interval
                      )
                  )
                LIMIT 1
            """), {
                "wallet": row["wallet"],
                "market_id": row["market_id"],
                "action": row["action"],
            }).scalar()

            if existing:
                skipped += 1
                continue

            conn.execute(text("""
                INSERT INTO alerts
                    (wallet, market_id, action, price, position_size,
                     wallet_score, category, market_question, detected_at)
                VALUES
                    (:wallet, :market_id, :action, :price, :position_size,
                     :wallet_score, :category, :market_question, :detected_at)
            """), {
                "wallet": row["wallet"],
                "market_id": row["market_id"],
                "action": row["action"],
                "price": float(row.get("price", 0)),
                "position_size": float(row.get("position_size", 0)),
                "wallet_score": float(row.get("wallet_score", 0)),
                "category": str(row.get("category", "unknown")),
                "market_question": str(row.get("market_question", "")),
                "detected_at": row.get("detected_at", datetime.now(timezone.utc)),
            })
            inserted += 1

    engine.dispose()
    print(f"Alerts exported: {inserted} inserted, {skipped} skipped (cooldown)")
