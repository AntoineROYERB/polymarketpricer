from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


def upsert_events(engine, df: DataFrame):
    if df.empty:
        return
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO events (id, title, slug, category, start_date, end_date, closed)
                    VALUES (:id, :title, :slug, :category, :start_date, :end_date, :closed)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        slug = EXCLUDED.slug,
                        category = EXCLUDED.category,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        closed = EXCLUDED.closed
                """),
                {
                    "id": row["id"],
                    "title": row["title"],
                    "slug": row.get("slug"),
                    "category": row.get("category"),
                    "start_date": row.get("start_date"),
                    "end_date": row.get("end_date"),
                    "closed": row.get("closed", False),
                },
            )


def upsert_markets(engine, df: DataFrame):
    if df.empty:
        return
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO markets (id, condition_id, question, category, event_id, event_slug,
                                         volume_usd, liquidity_usd, close_time,
                                         created_at, resolved_at, winning_outcome,
                                         mapped_category)
                    VALUES (:id, :condition_id, :question, :category, :event_id, :event_slug,
                            :volume_usd, :liquidity_usd, :close_time,
                            :created_at, :resolved_at, :winning_outcome,
                            :mapped_category)
                    ON CONFLICT (id) DO UPDATE SET
                        condition_id = EXCLUDED.condition_id,
                        question = EXCLUDED.question,
                        category = EXCLUDED.category,
                        event_id = EXCLUDED.event_id,
                        event_slug = EXCLUDED.event_slug,
                        volume_usd = EXCLUDED.volume_usd,
                        liquidity_usd = EXCLUDED.liquidity_usd,
                        close_time = EXCLUDED.close_time,
                        created_at = EXCLUDED.created_at,
                        resolved_at = EXCLUDED.resolved_at,
                        winning_outcome = EXCLUDED.winning_outcome,
                        mapped_category = EXCLUDED.mapped_category
                """),
                {
                    "id": row["id"],
                    "condition_id": row.get("condition_id"),
                    "question": row["question"],
                    "category": row.get("category"),
                    "event_id": row.get("event_id"),
                    "event_slug": row.get("event_slug"),
                    "volume_usd": row.get("volume_usd"),
                    "liquidity_usd": row.get("liquidity_usd"),
                    "close_time": row.get("close_time"),
                    "created_at": row.get("created_at"),
                    "resolved_at": row.get("resolved_at"),
                    "winning_outcome": row.get("winning_outcome"),
                    "mapped_category": row.get("mapped_category"),
                },
            )


def upsert_outcomes(engine, df: DataFrame):
    if df.empty:
        return
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO outcomes (id, market_id, label, price, winner)
                    VALUES (:id, :market_id, :label, :price, :winner)
                    ON CONFLICT (id) DO UPDATE SET
                        market_id = EXCLUDED.market_id,
                        label = EXCLUDED.label,
                        price = EXCLUDED.price,
                        winner = EXCLUDED.winner
                """),
                {
                    "id": row["id"],
                    "market_id": row["market_id"],
                    "label": row["label"],
                    "price": row.get("price"),
                    "winner": row.get("winner"),
                },
            )


@data_exporter
def export_data(data: dict, **kwargs) -> None:
    engine = create_engine(DATABASE_URL)
    print(f"Exporting {len(data['events'])} events, {len(data['markets'])} markets, {len(data['outcomes'])} outcomes")
    upsert_events(engine, data["events"])
    upsert_markets(engine, data["markets"])
    upsert_outcomes(engine, data["outcomes"])
    engine.dispose()
    print("Market export complete")
