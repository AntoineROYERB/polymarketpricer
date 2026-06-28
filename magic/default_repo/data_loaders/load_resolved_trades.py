from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.clob_resolver import fetch_resolved_markets
from default_repo.utils.db_helpers import DATABASE_URL


TRADES_QUERY_BY_COND_IDS = """
SELECT
    t.id AS trade_id,
    t.wallet,
    t.market_id,
    t.outcome_id,
    t.side AS type,
    t.price,
    t.shares AS size,
    t.amount_usd,
    t.timestamp AS created_at,
    m.question AS market_question
FROM trades t
JOIN markets m ON m.id = t.market_id
WHERE m.condition_id = ANY(:cond_ids)
  AND t.timestamp >= '2024-01-01'
ORDER BY t.wallet, t.market_id, t.outcome_id, t.timestamp ASC
"""

TRADES_QUERY_RESOLVED = """
SELECT
    t.id AS trade_id,
    t.wallet,
    t.market_id,
    t.outcome_id,
    t.side AS type,
    t.price,
    t.shares AS size,
    t.amount_usd,
    t.timestamp AS created_at,
    m.question AS market_question
FROM trades t
JOIN markets m ON m.id = t.market_id
WHERE m.id IN (
    SELECT DISTINCT o.market_id
    FROM outcomes o
    WHERE o.winner IS NOT NULL
)
  AND t.timestamp >= '2024-01-01'
ORDER BY t.wallet, t.market_id, t.outcome_id, t.timestamp ASC
"""

OUTCOME_RESOLUTION_QUERY = """
SELECT
    o.market_id,
    o.id AS outcome_id,
    o.label AS outcome_label,
    o.winner
FROM outcomes o
WHERE o.winner IS NOT NULL
  AND o.market_id = ANY(:market_ids)
"""


@data_loader
def load_data(*args, **kwargs) -> DataFrame:
    engine = create_engine(DATABASE_URL)

    # 1. Gamma path: load trades from markets with Gamma-resolved outcomes
    with engine.connect() as conn:
        gamma_trades = conn.execute(
            text(TRADES_QUERY_RESOLVED)
        ).mappings().all()

    gamma_market_ids = list({r["market_id"] for r in gamma_trades})

    # Load Gamma resolution from DB outcomes
    gamma_resolution: dict[str, dict[str, dict]] = {}
    if gamma_market_ids:
        with engine.connect() as conn:
            outcome_rows = conn.execute(
                text(OUTCOME_RESOLUTION_QUERY),
                {"market_ids": gamma_market_ids},
            ).mappings().all()
        for r in outcome_rows:
            mid = str(r["market_id"])
            oid = str(r["outcome_id"])
            gamma_resolution.setdefault(mid, {})[oid] = {
                "price": 1.0 if r["winner"] else 0.0,
                "winner": r["winner"],
            }
        print(f"Gamma resolution: {len(gamma_market_ids)} markets, {len(outcome_rows)} outcomes")

    # 2. CLOB path: load CLOB data as fallback
    clob_data = fetch_resolved_markets()
    by_condition = clob_data["by_condition"]
    by_token = clob_data["by_token"]

    clob_cond_ids = list(by_condition.keys())
    clob_trades = []
    if clob_cond_ids:
        with engine.connect() as conn:
            clob_trades = conn.execute(
                text(TRADES_QUERY_BY_COND_IDS), {"cond_ids": clob_cond_ids}
            ).mappings().all()
        print(f"CLOB resolution: {len(clob_cond_ids)} markets, {len(clob_trades)} trades")
    else:
        print("CLOB resolution: no resolved markets found")

    engine.dispose()

    if not gamma_trades and not clob_trades:
        print("No trades found on resolved markets")
        return DataFrame(columns=[
            "trade_id", "wallet", "market_id", "outcome_id", "type",
            "price", "size", "amount_usd", "created_at",
            "market_question", "resolution_price", "outcome_winner",
        ])

    # 3. Build combined resolution lookup: CLOB data as base, Gamma overrides
    all_resolution: dict[str, dict[str, dict]] = {}
    # CLOB: token_id -> {price, winner}
    for token_id, tok in by_token.items():
        all_resolution.setdefault("_by_token", {})[token_id] = {
            "price": tok.get("price", 0.0),
            "winner": tok.get("winner", False),
        }
    # Gamma overrides at (market_id, outcome_id) level — but outcome_id format differs
    # Gamma outcomes have id = "{market_id}_{index}", trades use CLOB token_id
    # So we keep CLOB resolution for token-based lookup and add Gamma for market-based fallback
    all_resolution["_by_market"] = gamma_resolution

    # 4. Process trades: prefer Gamma, fallback to CLOB
    processed_trades = []
    already_seen_trade_ids: set[str] = set()

    # Process Gamma trades first (preferred)
    for row in gamma_trades:
        tid = str(row["trade_id"])
        if tid in already_seen_trade_ids:
            continue
        already_seen_trade_ids.add(tid)
        mid = str(row["market_id"])
        oid = str(row["outcome_id"])

        # Try CLOB token lookup first (most precise)
        tok_res = all_resolution.get("_by_token", {}).get(oid)
        if tok_res is not None:
            res_price, winner = tok_res["price"], tok_res["winner"]
        else:
            # Fallback to Gamma market-level resolution
            market_res = all_resolution.get("_by_market", {}).get(mid, {})
            # Gamma outcome_id = "{market_id}_{index}" but trade.oid is token_id
            # Try to match by searching all outcomes for this market
            matching = [v for v in market_res.values() if v["winner"] is not None]
            if matching:
                winner = any(v["winner"] for v in matching if v["winner"] is True)
                res_price = 1.0 if winner else 0.0
            else:
                res_price, winner = 0.0, False

        processed_trades.append({
            "trade_id": row["trade_id"],
            "wallet": row["wallet"],
            "market_id": row["market_id"],
            "outcome_id": row["outcome_id"],
            "type": row["type"],
            "price": row["price"],
            "size": row["size"],
            "amount_usd": row["amount_usd"],
            "created_at": row["created_at"],
            "market_question": row["market_question"],
            "resolution_price": res_price,
            "outcome_winner": winner,
        })

    # Process CLOB-only trades (not already included via Gamma)
    for row in clob_trades:
        tid = str(row["trade_id"])
        if tid in already_seen_trade_ids:
            continue
        already_seen_trade_ids.add(tid)
        token_id = str(row.get("outcome_id", ""))
        tok = all_resolution.get("_by_token", {}).get(token_id, {})
        res_price = tok.get("price", 0.0)
        winner = tok.get("winner", False)
        processed_trades.append({
            "trade_id": row["trade_id"],
            "wallet": row["wallet"],
            "market_id": row["market_id"],
            "outcome_id": row["outcome_id"],
            "type": row["type"],
            "price": row["price"],
            "size": row["size"],
            "amount_usd": row["amount_usd"],
            "created_at": row["created_at"],
            "market_question": row["market_question"],
            "resolution_price": res_price,
            "outcome_winner": winner,
        })

    df = DataFrame(processed_trades)
    resolved = df[df["outcome_winner"]].shape[0]
    gamma_count = len(gamma_trades)
    print(f"Loaded {len(df)} trades on resolved markets "
          f"({gamma_count} Gamma-source, {len(df) - gamma_count} CLOB-only, "
          f"{resolved} winner trades)")
    return df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "wallet" in df.columns
        assert "market_id" in df.columns
        assert "type" in df.columns
        assert "price" in df.columns
