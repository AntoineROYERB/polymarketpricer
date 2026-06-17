from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_exporter
def export_data(df: DataFrame, **kwargs) -> None:
    if df.empty:
        return
    print(f"Exporting {len(df)} trades")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO trades (id, wallet, market_id, outcome_id, side, type,
                                        price, shares, amount_usd, fee_usd, timestamp, tx_hash)
                    VALUES (:id, :wallet, :market_id, :outcome_id, :side, :type,
                            :price, :shares, :amount_usd, :fee_usd, :timestamp, :tx_hash)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": row["id"],
                    "wallet": row["wallet"],
                    "market_id": row.get("market_id"),
                    "outcome_id": row.get("outcome_id"),
                    "side": row.get("side", "BUY"),
                    "type": row.get("type", "MARKET"),
                    "price": row.get("price"),
                    "shares": row.get("shares"),
                    "amount_usd": row.get("amount_usd"),
                    "fee_usd": row.get("fee_usd"),
                    "timestamp": row.get("timestamp"),
                    "tx_hash": row.get("tx_hash"),
                },
            )
    engine.dispose()
    print("Trade export complete")
