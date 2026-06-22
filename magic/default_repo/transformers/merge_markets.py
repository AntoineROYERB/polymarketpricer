import pandas as pd
from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.category_classifier import infer_category


@transformer
def transform_df(active: DataFrame, resolved: DataFrame, *args, **kwargs) -> dict:
    combined = DataFrame()
    if not active.empty:
        combined = pd.concat([combined, active], ignore_index=True)
    if not resolved.empty:
        combined = pd.concat([combined, resolved], ignore_index=True)

    if combined.empty:
        return {"events": DataFrame(), "markets": DataFrame(), "outcomes": DataFrame()}

    before = len(combined)
    combined = combined.drop_duplicates(subset=["market_id"], keep="last")
    removed = before - len(combined)
    print(f"Combined {len(active)} active + {len(resolved)} resolved markets, removed {removed} duplicates")

    no_event = combined["event_id"].isna().sum()
    if no_event:
        print(f"Warning: {no_event} markets have no event_id — skipping event rows for those")
    events = combined[combined["event_id"].notna()][["event_id", "event_title", "event_slug", "event_category",
                                                      "event_start_date", "event_end_date", "event_closed"]].drop_duplicates(subset=["event_id"]).copy()
    events.columns = ["id", "title", "slug", "category", "start_date", "end_date", "closed"]
    events = events.reset_index(drop=True)

    markets = combined[["market_id", "condition_id", "question", "category", "event_id", "event_slug",
                        "volume_usd", "liquidity_usd", "close_time", "created_at",
                        "resolved_at", "winning_outcome"]].drop_duplicates(subset=["market_id"]).copy()
    markets.columns = ["id", "condition_id", "question", "category", "event_id", "event_slug",
                       "volume_usd", "liquidity_usd", "close_time", "created_at",
                       "resolved_at", "winning_outcome"]
    markets = markets.reset_index(drop=True)

    markets["mapped_category"] = markets.apply(
        lambda r: infer_category(
            question=r.get("question", "") or "",
            raw_category=r.get("category"),
        ),
        axis=1,
    )
    mapped_count = markets["mapped_category"].notna().sum()
    print(f"Category classification: {mapped_count}/{len(markets)} markets classified")

    outcome_rows = []
    for _, row in combined.iterrows():
        outcomes = row.get("outcomes")
        if isinstance(outcomes, list):
            for o in outcomes:
                if isinstance(o, dict):
                    outcome_rows.append({
                        "id": o.get("id"),
                        "market_id": row["market_id"],
                        "label": o.get("label"),
                        "price": o.get("price"),
                        "winner": o.get("winner"),
                    })
    outcomes = DataFrame(outcome_rows).drop_duplicates(subset=["id"]) if outcome_rows else DataFrame(
        columns=["id", "market_id", "label", "price", "winner"]
    )

    print(f"Result: {len(events)} events, {len(markets)} markets, {len(outcomes)} outcomes")
    return {"events": events, "markets": markets, "outcomes": outcomes}


@test
def test_output(result) -> None:
    assert "events" in result, "Missing events"
    assert "markets" in result, "Missing markets"
    assert "outcomes" in result, "Missing outcomes"
