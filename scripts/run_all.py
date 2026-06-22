"""Execute all Polymarket pipelines sequentially via direct Python execution."""

import sys
import time

sys.path.insert(0, "/home/src/default_repo")


def run_pipeline(name: str, fn):
    print(f"\n{'='*60}")
    print(f"  Starting pipeline: {name}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        fn()
        elapsed = time.time() - t0
        print(f"  Completed in {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  FAILED after {elapsed:.1f}s: {e}")
        raise


def run_ingestion_market_discovery():
    from data_loaders.load_active_markets import load_data_from_api as load_active
    from data_loaders.load_resolved_markets import load_data_from_api as load_resolved
    from transformers.merge_markets import transform_df
    from data_exporters.export_markets import export_data

    print("  Loading active markets...")
    active = load_active()
    print(f"    {len(active)} rows")
    print("  Loading resolved markets...")
    resolved = load_resolved()
    print(f"    {len(resolved)} rows")
    print("  Merging...")
    merged = transform_df(active, resolved)
    print(f"    {len(merged['events'])} events, {len(merged['markets'])} markets, {len(merged['outcomes'])} outcomes")
    print("  Exporting...")
    export_data(merged)


def run_ingestion_wallet_discovery():
    from data_loaders.load_holders_for_active_markets import load_data_from_api as load_holders
    from data_loaders.resolve_proxy_wallets import load_data_from_api as resolve_proxies
    from transformers.build_wallet_records import transform_df
    from data_exporters.export_wallets import export_data

    print("  Scanning markets for holder wallets...")
    holders = load_holders()
    print(f"    {len(holders)} holder wallets found")
    print("  Resolving proxy wallets...")
    resolved = resolve_proxies(holders)
    print(f"    {len(resolved)} proxy wallets resolved")
    print("  Building wallet records...")
    records = transform_df(holders, resolved)
    print(f"    {len(records)} wallet records")
    print("  Exporting wallets...")
    export_data(records)


def run_ingestion_position_sync():
    from data_loaders.load_tracked_wallets import load_data_from_api as load_wallets
    from data_loaders.load_positions import load_data_from_api as load_positions
    from transformers.merge_positions import transform_df
    from data_exporters.export_positions import export_data

    wallets = load_wallets()
    print(f"  {len(wallets)} tracked wallets")
    positions = load_positions(wallets)
    print(f"  {len(positions)} positions fetched")
    merged = transform_df(positions)
    export_data(merged)


def run_ingestion_trade_history():
    from data_loaders.load_tracked_wallets_for_trades import load_data_from_api as load_wallets
    from data_loaders.load_trades_for_wallet import load_data_from_api as load_trades
    from transformers.deduplicate_trades import transform_df
    from data_exporters.export_trades import export_data

    wallets = load_wallets()
    print(f"  {len(wallets)} tracked wallets")
    trades = load_trades(wallets)
    print(f"  {len(trades)} trades fetched")
    deduped = transform_df(trades)
    print(f"  {len(deduped)} trades after dedup")
    export_data(deduped)


def run_analytics():
    from data_loaders.load_recent_activity import load_data_from_api as load_recent
    from data_loaders.load_positions_data import load_data_from_api as load_positions
    from data_loaders.load_trades_data import load_data_from_api as load_trades
    from transformers.compute_wallet_metrics import transform_df
    from data_exporters.export_analytics import export_data

    wallets = load_recent()
    print(f"  {len(wallets)} recently active wallets")
    positions = load_positions(wallets)
    trades = load_trades(wallets)
    metrics = transform_df(positions, trades)
    print(f"  {len(metrics)} wallets with computed metrics")
    export_data(metrics)


def run_ranking():
    from data_loaders.load_all_analytics import load_data_from_api as load_analytics
    from data_loaders.load_wallet_metadata import load_data_from_api as load_metadata
    from transformers.filter_eligible_wallets import transform_df as filter_eligible
    from transformers.compute_wallet_scores import transform_df as compute_scores
    from data_exporters.materialize_rankings import export_data

    analytics = load_analytics()
    metadata = load_metadata()
    print(f"  {len(analytics)} analytics rows, {len(metadata)} metadata rows")
    eligible = filter_eligible(analytics, metadata)
    print(f"  {len(eligible)} eligible wallets")
    rankings = compute_scores(eligible)
    print(f"  Rankings: {len(rankings.get('top_100', []))} top_100, {len(rankings.get('emerging', []))} emerging, {len(rankings.get('consistent', []))} consistent")
    export_data(rankings)


if __name__ == "__main__":
    pipelines = {
        "ingestion_market_discovery": run_ingestion_market_discovery,
        "ingestion_wallet_discovery": run_ingestion_wallet_discovery,
        "ingestion_position_sync": run_ingestion_position_sync,
        "ingestion_trade_history": run_ingestion_trade_history,
        "enrichment_analytics_computation": run_analytics,
        "enrichment_ranking_computation": run_ranking,
    }

    selected = sys.argv[1:] if len(sys.argv) > 1 else list(pipelines.keys())
    for name in selected:
        if name in pipelines:
            run_pipeline(name, pipelines[name])
        else:
            print(f"Unknown pipeline: {name}")
            print(f"Available: {', '.join(pipelines.keys())}")
