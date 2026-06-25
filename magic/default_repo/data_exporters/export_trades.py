if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from default_repo.utils.db_helpers import DATABASE_URL
from sqlalchemy import create_engine, text
import pandas as pd


@data_exporter
def export_data(df: pd.DataFrame, **kwargs) -> None:
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
                row.to_dict()
            )
    engine.dispose()
