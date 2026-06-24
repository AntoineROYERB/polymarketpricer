from datetime import date

import pandas as pd
from pandas import DataFrame, to_numeric

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


def normalize(series, default=0.5):
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(default, index=series.index)
    return (series - mn) / (mx - mn)


@transformer
def transform_df(df: DataFrame, *args, **kwargs) -> dict:
    if df.empty:
        return {
            "rankings": DataFrame(),
            "wallet_scores": DataFrame(columns=["wallet", "snapshot_date", "wallet_score"]),
        }

    df = df.copy()
    df["roi"] = to_numeric(df["roi"], errors="coerce").fillna(0)
    df["win_rate"] = to_numeric(df["win_rate"], errors="coerce").fillna(0)
    df["consistency_score"] = to_numeric(df["consistency_score"], errors="coerce").fillna(0)
    df["experience_score"] = to_numeric(df["experience_score"], errors="coerce").fillna(0)
    df["sharpe_ratio"] = to_numeric(df["sharpe_ratio"], errors="coerce").fillna(0)
    df["total_pnl"] = to_numeric(df["total_pnl"], errors="coerce").fillna(0)
    df["num_trades"] = to_numeric(df["num_trades"], errors="coerce").fillna(0)

    norm_roi = normalize(df["roi"])
    norm_winrate = normalize(df["win_rate"])
    norm_sharpe = normalize(df["sharpe_ratio"])

    df["wallet_score"] = (
        0.35 * norm_roi
        + 0.25 * norm_winrate
        + 0.15 * df["consistency_score"]
        + 0.15 * df["experience_score"]
        + 0.10 * norm_sharpe
    )

    today = date.today()

    top_100 = df.nlargest(100, "wallet_score").copy()
    top_100["list_type"] = "top_100"

    emerging_mask = (
        df["experience_score"].between(0.3, 0.6)
    )
    emerging = df[emerging_mask].nlargest(10, "wallet_score").copy()
    emerging["list_type"] = "emerging"

    consistent = df.nlargest(10, "consistency_score").copy()
    consistent["list_type"] = "consistent"

    all_lists = DataFrame()
    if not top_100.empty:
        all_lists = pd.concat([all_lists, top_100], ignore_index=True)
    if not emerging.empty:
        all_lists = pd.concat([all_lists, emerging], ignore_index=True)
    if not consistent.empty:
        all_lists = pd.concat([all_lists, consistent], ignore_index=True)

    if not all_lists.empty:
        all_lists = all_lists.drop_duplicates(subset=["wallet", "list_type"])
        all_lists["snapshot_date"] = today
        all_lists["rank"] = all_lists.groupby("list_type")["wallet_score"].rank(
            ascending=False, method="dense"
        ).astype(int)
        all_lists["risk_adj_return"] = to_numeric(
            all_lists.get("sharpe_ratio"), errors="coerce"
        )

    ranking_cols = [
        "wallet", "snapshot_date", "list_type", "rank", "wallet_score",
        "roi", "win_rate", "consistency_score", "experience_score",
        "risk_adj_return", "total_pnl", "num_trades",
    ]
    rankings = all_lists[[c for c in ranking_cols if c in all_lists.columns]].copy() if not all_lists.empty else DataFrame(columns=ranking_cols)

    wallet_scores = df[["wallet", "wallet_score"]].copy()
    wallet_scores["snapshot_date"] = today

    print(f"Rankings: {len(top_100)} top_100, {len(emerging)} emerging, {len(consistent)} consistent")
    return {"rankings": rankings, "wallet_scores": wallet_scores}


@test
def test_output(result) -> None:
    assert "rankings" in result, "Missing rankings"
    assert "wallet_scores" in result, "Missing wallet_scores"
