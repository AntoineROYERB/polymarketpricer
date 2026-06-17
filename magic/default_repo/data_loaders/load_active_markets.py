import json
import requests
import time
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

GAMMA_API = "https://gamma-api.polymarket.com"
PAGE_SIZE = 100
MAX_PAGES = 500


def fetch_markets(closed: bool) -> list[dict]:
    all_markets: list[dict] = []
    seen_ids: set[str] = set()
    cursor = None
    page = 0
    while page < MAX_PAGES:
        params: dict = {"limit": PAGE_SIZE, "closed": str(closed).lower()}
        if cursor:
            params["after_cursor"] = cursor
        try:
            resp = requests.get(f"{GAMMA_API}/markets/keyset", params=params, timeout=30)
            if resp.status_code == 422:
                break
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  request failed: {e}")
            break
        data = resp.json()
        batch = data.get("markets", [])
        if not batch:
            break
        batch_ids = {m["id"] for m in batch if "id" in m}
        if batch_ids.issubset(seen_ids):
            print(f"  page {page}: all {len(batch_ids)} markets already seen — stopping")
            break
        seen_ids.update(batch_ids)
        all_markets.extend(batch)
        cursor = data.get("next_cursor")
        page += 1
        print(f"  page {page}: {len(batch)} markets ({len(seen_ids)} unique)")
        if not cursor:
            break
        time.sleep(0.1)
    return all_markets


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    markets = fetch_markets(closed=False)
    print(f"Fetched {len(markets)} active markets total")
    rows = []
    for m in markets:
        outcomes_raw = m.get("outcomes", "[]")
        if isinstance(outcomes_raw, str):
            try:
                outcomes_list = json.loads(outcomes_raw)
            except (json.JSONDecodeError, TypeError):
                outcomes_list = []
        else:
            outcomes_list = outcomes_raw if isinstance(outcomes_raw, list) else []

        outcome_prices_raw = m.get("outcomePrices", "[]")
        if isinstance(outcome_prices_raw, str):
            try:
                outcome_prices = json.loads(outcome_prices_raw)
            except (json.JSONDecodeError, TypeError):
                outcome_prices = []
        else:
            outcome_prices = outcome_prices_raw if isinstance(outcome_prices_raw, list) else []

        outcomes_merged = []
        for i, label in enumerate(outcomes_list):
            outcomes_merged.append({
                "id": f"{m['id']}_{i}",
                "label": label,
                "price": outcome_prices[i] if i < len(outcome_prices) else None,
            })
        event = None
        events_list = m.get("events")
        if isinstance(events_list, list) and len(events_list) > 0:
            event = events_list[0]
        rows.append({
            "event_id": event["id"] if event else None,
            "event_title": event["title"] if event else None,
            "event_slug": event.get("slug") if event else None,
            "event_category": m.get("category"),
            "event_start_date": event.get("startDate") if event else None,
            "event_end_date": event.get("endDate") if event else None,
            "event_closed": event.get("closed", False) if event else False,
            "market_id": m["id"],
            "condition_id": m.get("conditionId"),
            "question": m.get("question"),
            "category": m.get("category"),
            "volume_usd": m.get("volume"),
            "liquidity_usd": m.get("liquidity"),
            "close_time": m.get("endDate"),
            "created_at": m.get("startDate"),
            "resolved_at": m.get("resolvedAt"),
            "winning_outcome": m.get("outcome"),
            "outcomes": outcomes_merged,
        })
    return DataFrame(rows)


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
    assert not df.empty, 'No active markets loaded'
