"""Fetch resolved market data from Polymarket CLOB API."""

import time

import requests

CLOB_API = "https://clob.polymarket.com"
PAGE_SIZE = 1000


def fetch_resolved_markets(max_pages: int = 20) -> dict:
    """Fetch all resolved markets from CLOB API.

    Returns dict with two keys:
      - "by_condition": {condition_id: {outcome_label: {token_id, winner, price}}}
      - "by_token": {token_id: {outcome_label, winner, price, condition_id}}
    """
    by_condition: dict = {}
    by_token: dict = {}
    seen_cond_ids: set[str] = set()
    cursor = None
    page = 0
    for page in range(max_pages):
        params: dict = {"limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(f"{CLOB_API}/markets", params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  CLOB API request failed on page {page}: {e}")
            break
        data = resp.json()
        markets = data.get("data", [])
        if not markets:
            break
        new_cond_ids: set[str] = set()
        for m in markets:
            cond_id = m.get("condition_id", "")
            if not cond_id:
                continue
            if cond_id in seen_cond_ids:
                continue
            new_cond_ids.add(cond_id)
            tokens = m.get("tokens", [])
            is_resolved = any(t.get("winner") for t in tokens)
            if not is_resolved:
                continue
            outcome_map = {}
            for t in tokens:
                token_id = t.get("token_id", "")
                label = t.get("outcome", "")
                if not label:
                    continue
                winner = t.get("winner", False)
                price = float(t.get("price", 0))
                outcome_map[label] = {
                    "token_id": token_id,
                    "winner": winner,
                    "price": price,
                }
                if token_id:
                    by_token[token_id] = {
                        "outcome_label": label,
                        "winner": winner,
                        "price": price,
                        "condition_id": cond_id,
                    }
            if outcome_map:
                by_condition[cond_id] = outcome_map
        if not new_cond_ids:
            print(f"  page {page}: no new condition_ids — stopping (dedup)")
            break
        seen_cond_ids.update(new_cond_ids)
        cursor = data.get("next_cursor")
        if not cursor:
            break
        if page % 3 == 2:
            print(f"  Fetched page {page + 1}: {len(by_condition)} resolved markets so far")
        time.sleep(0.05)
    print(f"CLOB resolver: fetched {len(by_condition)} resolved markets, {len(by_token)} tokens")
    return {"by_condition": by_condition, "by_token": by_token}
