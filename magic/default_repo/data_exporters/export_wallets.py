from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_exporter
def export_data(df: DataFrame, **kwargs) -> None:
    if df.empty:
        return
    print(f"Exporting {len(df)} wallet records")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO wallets (wallet, main_wallet, is_tracked, first_seen, last_seen,
                                         last_position_sync, last_trade_sync)
                    VALUES (:wallet, :main_wallet, :is_tracked, :first_seen, :last_seen,
                            :last_position_sync, :last_trade_sync)
                    ON CONFLICT (wallet) DO UPDATE SET
                        main_wallet = EXCLUDED.main_wallet,
                        last_seen = EXCLUDED.last_seen
                """),
                {
                    "wallet": row["wallet"],
                    "main_wallet": row.get("main_wallet"),
                    "is_tracked": row.get("is_tracked", True),
                    "first_seen": row.get("first_seen"),
                    "last_seen": row.get("last_seen"),
                    "last_position_sync": row.get("last_position_sync"),
                    "last_trade_sync": row.get("last_trade_sync"),
                },
            )
    engine.dispose()
    print("Wallet export complete")
