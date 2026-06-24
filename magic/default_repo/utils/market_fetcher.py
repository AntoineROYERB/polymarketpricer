"""Shared market fetching logic for Polymarket Gamma API."""

import json
import time

import requests

GAMMA_API = "https://gamma-api.polymarket.com"
PAGE_SIZE = 100
MAX_PAGES = 500


def fetch_markets(closed: bool) -> list[dict]:
    """Paginate through Gamma /markets/keyset with dedup."""
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


def _parse_json_list(raw, default=None):
    """Parse a JSON string or return as-is if already a list."""
    if default is None:
        default = []
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default
    return raw if isinstance(raw, list) else default


def build_market_rows(markets: list[dict]) -> list[dict]:
    """Convert raw Gamma market objects into normalised rows with merged outcomes."""
    rows = []
    for m in markets:
        outcomes_list = _parse_json_list(m.get("outcomes", "[]"))
        outcome_prices = _parse_json_list(m.get("outcomePrices", "[]"))

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
    return rows
