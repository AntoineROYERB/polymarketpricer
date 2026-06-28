from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from sqlalchemy import create_engine, text

from default_repo.utils.clob_resolver import fetch_resolved_markets
from default_repo.utils.db_helpers import DATABASE_URL


@data_loader
def load_data(*args, **kwargs) -> DataFrame:
    clob_data = fetch_resolved_markets()
    by_condition = clob_data["by_condition"]
    by_token = clob_data["by_token"]

    engine = create_engine(DATABASE_URL)

    # Load Gamma-sourced winners from DB (outcomes where winner is set)
    with engine.connect() as conn:
        gamma_rows = conn.execute(
            text("""
                SELECT m.condition_id, o.label, o.winner
                FROM outcomes o
                JOIN markets m ON m.id = o.market_id
                WHERE o.winner IS NOT NULL
            """),
        ).mappings().all()

    # Build Gamma winner lookup: {condition_id: {label: bool}}
    gamma_winner_map: dict[str, dict[str, bool]] = {}
    for r in gamma_rows:
        cond_id = r["condition_id"]
        if not cond_id:
            continue
        gamma_winner_map.setdefault(cond_id, {})[r["label"]] = r["winner"]
    print(f"Gamma winners: {len(gamma_winner_map)} markets from DB")

    # Merge Gamma winners into CLOB data — Gamma winner overrides CLOB
    for cond_id, labels in gamma_winner_map.items():
        if cond_id in by_condition:
            for label, winner in labels.items():
                if label in by_condition[cond_id]:
                    by_condition[cond_id][label]["winner"] = winner
                    by_condition[cond_id][label]["_source"] = "gamma"
        else:
            by_condition[cond_id] = {}
            for label, winner in labels.items():
                by_condition[cond_id][label] = {
                    "token_id": None,
                    "winner": winner,
                    "price": 1.0 if winner else 0.0,
                    "_source": "gamma",
                }

    cond_ids = list(by_condition.keys())
    if not cond_ids:
        print("No resolved markets found via CLOB API or Gamma")
        engine.dispose()
        return DataFrame(columns=["outcome_id", "market_id", "outcome", "winner"])

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id AS market_id, condition_id FROM markets WHERE condition_id = ANY(:ids)"),
            {"ids": cond_ids},
        ).mappings().all()
    engine.dispose()

    cond_to_market = {r["condition_id"]: r["market_id"] for r in rows}

    outcome_rows = []
    for cond_id, tokens in by_condition.items():
        market_id = cond_to_market.get(cond_id)
        if market_id is None:
            continue
        for label, tok in tokens.items():
            token_id = tok.get("token_id")
            outcome_rows.append({
                "outcome_id": token_id or f"{market_id}_{label}",
                "market_id": market_id,
                "outcome": label,
                "winner": tok["winner"],
                "_source": tok.get("_source", "clob"),
            })

    df = DataFrame(outcome_rows) if outcome_rows else DataFrame(
        columns=["outcome_id", "market_id", "outcome", "winner"]
    )
    gamma_count = sum(1 for r in outcome_rows if r["_source"] == "gamma")
    clob_count = len(outcome_rows) - gamma_count
    print(f"Loaded {len(df)} outcomes ({gamma_count} Gamma, {clob_count} CLOB)")
    if "_source" in df.columns:
        df = df.drop(columns=["_source"])
    return df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "market_id" in df.columns
        assert "winner" in df.columns
