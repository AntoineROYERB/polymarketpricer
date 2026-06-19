"""Orchestrateur ETL avec parallélisation et timeouts SLA.

Usage:
    python /home/src/scripts/run_all.py                     # Run all phases
    python /home/src/scripts/run_all.py analytics_computation  # Single pipeline

Phases (automatique si aucun argument):
    Phase 1 — market_discovery           (séquentiel, 120s SLA)
    Phase 2 — wallet_discovery            (séquentiel, 120s SLA)
    Phase 3 — position_sync + trade_history (parallèle, 120s SLA)
    Phase 4 — analytics_computation       (séquentiel, 60s SLA)
    Phase 5 — ranking_computation         (séquentiel, 30s SLA)
    Phase 6 — verify_etl_output           (séquentiel, 30s SLA)

Objectif SLA total: < 300s (5 minutes)
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, "/home/src/default_repo")

# ── Timeouts (seconds) ───────────────────────────────────────────────
SLA = {
    "market_discovery": 120,
    "wallet_discovery": 120,
    "position_sync": 120,
    "trade_history": 120,
    "analytics_computation": 60,
    "ranking_computation": 30,
    "category_analytics": 120,
    "verify_etl_output": 30,
}
SLA_TOTAL = 420  # 7 minutes global (with category_analytics)


def elapsed() -> str:
    return f"[{time.time() - t0:.0f}s]"


def run_pipeline(name: str, fn):
    print(f"\n{'=' * 60}")
    print(f"  {elapsed()} Starting: {name}")
    print(f"{'=' * 60}")
    t_start = time.time()
    try:
        fn()
        duration = time.time() - t_start
        limit = SLA.get(name, 120)
        status = "✓" if duration <= limit else "⚠"
        print(f"  {elapsed()} {status} {name} done in {duration:.1f}s (SLA: {limit}s)")
    except Exception as e:
        duration = time.time() - t_start
        print(f"  {elapsed()} ✗ {name} FAILED after {duration:.1f}s: {e}")
        raise


def get_runner(phase: str):
    """Retourne la fonction runner correspondant au nom de pipeline."""
    runners = {
        "market_discovery": run_market_discovery,
        "wallet_discovery": run_wallet_discovery,
        "position_sync": run_position_sync,
        "trade_history": run_trade_history,
        "analytics_computation": run_analytics,
        "ranking_computation": run_ranking,
        "category_analytics": run_category_analytics,
        "verify_etl_output": run_verification,
    }
    return runners[phase]


# ── Pipeline runners ─────────────────────────────────────────────────

def run_market_discovery():
    from data_loaders.load_active_markets import load_data_from_api as load_active
    from data_loaders.load_resolved_markets import load_data_from_api as load_resolved
    from transformers.merge_markets import transform_df
    from data_exporters.export_markets import export_data

    active = load_active()
    resolved = load_resolved()
    merged = transform_df(active, resolved)
    export_data(merged)


def run_wallet_discovery():
    from data_loaders.load_holders_for_active_markets import load_data_from_api as load_holders
    from data_loaders.resolve_proxy_wallets import load_data_from_api as resolve_proxies
    from transformers.build_wallet_records import transform_df
    from data_exporters.export_wallets import export_data

    holders = load_holders()
    resolved = resolve_proxies(holders)
    records = transform_df(holders, resolved)
    export_data(records)


def run_position_sync():
    from data_loaders.load_tracked_wallets import load_data_from_api as load_wallets
    from data_loaders.load_positions import load_data_from_api as load_positions
    from transformers.merge_positions import transform_df
    from data_exporters.export_positions import export_data

    wallets = load_wallets()
    positions = load_positions(wallets)
    merged = transform_df(positions)
    export_data(merged)


def run_trade_history():
    from data_loaders.load_tracked_wallets_for_trades import load_data_from_api as load_wallets
    from data_loaders.load_trades_for_wallet import load_data_from_api as load_trades
    from transformers.deduplicate_trades import transform_df
    from data_exporters.export_trades import export_data

    wallets = load_wallets()
    trades = load_trades(wallets)
    deduped = transform_df(trades)
    export_data(deduped)


def run_analytics():
    from data_loaders.load_recent_activity import load_data_from_api as load_recent
    from data_loaders.load_positions_data import load_data_from_api as load_positions
    from data_loaders.load_trades_data import load_data_from_api as load_trades
    from transformers.compute_wallet_metrics import transform_df
    from data_exporters.export_analytics import export_data

    wallets = load_recent()
    positions = load_positions(wallets)
    trades = load_trades(wallets)
    metrics = transform_df(positions, trades)
    export_data(metrics)


def run_ranking():
    from data_loaders.load_all_analytics import load_data_from_api as load_analytics
    from data_loaders.load_wallet_metadata import load_data_from_api as load_metadata
    from transformers.filter_eligible_wallets import transform_df as filter_eligible
    from transformers.compute_wallet_scores import transform_df as compute_scores
    from data_exporters.materialize_rankings import export_data

    analytics = load_analytics()
    metadata = load_metadata()
    eligible = filter_eligible(analytics, metadata)
    rankings = compute_scores(eligible)
    export_data(rankings)


def run_category_analytics():
    from data_loaders.load_recent_activity import load_data_from_api as load_wallets
    from data_loaders.load_positions_data import load_data_from_api as load_positions
    from data_loaders.load_trades_data import load_data_from_api as load_trades
    from data_loaders.load_market_categories import load_data_from_api as load_categories
    from transformers.compute_category_metrics import transform_df
    from data_exporters.export_category_analytics import export_data

    wallets = load_wallets()
    positions = load_positions(wallets)
    trades = load_trades(wallets)
    categories = load_categories()
    result = transform_df(positions, trades, categories)
    export_data(result)


def run_verification():
    from data_loaders.verify_etl_output import load_data_from_api as verify

    verify()


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    t0 = time.time()

    selected = sys.argv[1:]
    if selected:
        # Mode single-pipeline
        for name in selected:
            runner = get_runner(name)
            run_pipeline(name, runner)
        sys.exit(0)

    # ── Mode orchestrateur complet ───────────────────────────────────
    print(f"=== Polymarket ETL Orchestrator ===")
    print(f"SLA global: {SLA_TOTAL}s")

    # Phase 1: market_discovery
    run_pipeline("market_discovery", run_market_discovery)

    # Phase 2: wallet_discovery
    run_pipeline("wallet_discovery", run_wallet_discovery)

    # Phase 3: position_sync + trade_history en parallèle
    print(f"\n  {elapsed()} Phase 3: position_sync + trade_history (parallèle)")
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_map = {
            pool.submit(run_pipeline, "position_sync", run_position_sync): "position_sync",
            pool.submit(run_pipeline, "trade_history", run_trade_history): "trade_history",
        }
        for fut in as_completed(fut_map):
            fut.result()

    # Phase 4: analytics_computation
    run_pipeline("analytics_computation", run_analytics)

    # Phase 5: ranking_computation
    run_pipeline("ranking_computation", run_ranking)

    # Phase 6: category_analytics
    run_pipeline("category_analytics", run_category_analytics)

    # Phase 7: verification
    run_pipeline("verify_etl_output", run_verification)

    # Bilan SLA global
    total = time.time() - t0
    status = "✓" if total <= SLA_TOTAL else "⚠"
    print(f"\n{'=' * 60}")
    print(f"  {status} ETL cycle completed in {total:.1f}s (SLA: {SLA_TOTAL}s)")
    print(f"{'=' * 60}")

    if total > SLA_TOTAL:
        sys.exit(1)
