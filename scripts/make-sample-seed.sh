#!/usr/bin/env bash
# Build docker/initdb/seed.sql.gz — a small, FK-consistent sample of the local
# database so `docker compose up` and CI start with real (but lightweight) data.
#
# Sample shape: the 200 highest-scoring wallets from the latest analytics
# snapshot (plus any followed wallet), their 120 most recent trades each, and
# every event / market / outcome those trades reference.
#
# Requires the local stack to be running with a populated database:
#   docker compose up -d && ./scripts/run-all-pipelines.sh
set -euo pipefail

cd "$(dirname "$0")/.."

OUT=docker/initdb/seed.sql.gz
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

PSQL=(docker compose exec -T postgres psql -U app -d polymarket)

echo "→ dumping schema ..."
docker compose exec -T postgres pg_dump -U app -d polymarket \
  --schema-only --no-owner --no-acl \
  | grep -v '^\\restrict\|^\\unrestrict' > "$TMP/schema.sql"

echo "→ sampling data ..."
"${PSQL[@]}" -q -X > "$TMP/data.sql" <<'SQL'
\set ON_ERROR_STOP on
\pset footer off

CREATE TEMP TABLE s_wallets AS
SELECT DISTINCT wallet FROM (
    (SELECT wallet FROM wallet_analytics
     WHERE snapshot_date = (SELECT max(snapshot_date) FROM wallet_analytics)
     ORDER BY wallet_score DESC NULLS LAST
     LIMIT 200)
    UNION
    (SELECT wallet FROM wallet_follows)
) q;

CREATE TEMP TABLE s_trades AS
SELECT t.* FROM (
    SELECT t.*, row_number() OVER (PARTITION BY t.wallet ORDER BY t.timestamp DESC) AS rn
    FROM trades t JOIN s_wallets w ON w.wallet = t.wallet
) t WHERE t.rn <= 120;

CREATE TEMP TABLE s_markets AS SELECT DISTINCT market_id AS id FROM s_trades;

CREATE TEMP TABLE s_events AS
SELECT DISTINCT m.event_id AS id FROM markets m JOIN s_markets s ON s.id = m.id
WHERE m.event_id IS NOT NULL;

\echo 'SET search_path = public;'
\echo 'SET session_replication_role = replica;'
\echo ''

\echo 'COPY events (id,title,slug,category,start_date,end_date,closed) FROM stdin;'
\copy (SELECT e.id,e.title,e.slug,e.category,e.start_date,e.end_date,e.closed FROM events e JOIN s_events s ON s.id=e.id) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY markets (id,question,category,event_id,event_slug,volume_usd,liquidity_usd,close_time,created_at,resolved_at,winning_outcome,mapped_category,condition_id) FROM stdin;'
\copy (SELECT m.id,m.question,m.category,m.event_id,m.event_slug,m.volume_usd,m.liquidity_usd,m.close_time,m.created_at,m.resolved_at,m.winning_outcome,m.mapped_category,m.condition_id FROM markets m JOIN s_markets s ON s.id=m.id) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY outcomes (id,market_id,label,price,winner) FROM stdin;'
\copy (SELECT o.id,o.market_id,o.label,o.price,o.winner FROM outcomes o JOIN s_markets s ON s.id=o.market_id) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY wallets (wallet,main_wallet,label,is_tracked,first_seen,last_seen,last_position_sync,last_trade_sync,tier) FROM stdin;'
\copy (SELECT w.wallet,w.main_wallet,w.label,w.is_tracked,w.first_seen,w.last_seen,w.last_position_sync,w.last_trade_sync,w.tier FROM wallets w JOIN s_wallets s ON s.wallet=w.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY categories (category,label) FROM stdin;'
\copy (SELECT category,label FROM categories) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY alert_rules (id,wallet,min_score,min_position_size,min_liquidity,cooldown_minutes,discord_webhook_url,active) FROM stdin;'
-- discord_webhook_url is blanked: the seed is committed to a public repo.
\copy (SELECT r.id,r.wallet,r.min_score,r.min_position_size,r.min_liquidity,r.cooldown_minutes,NULL::text,r.active FROM alert_rules r LEFT JOIN s_wallets s ON s.wallet=r.wallet WHERE r.wallet IS NULL OR s.wallet IS NOT NULL) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY trades (id,wallet,market_id,outcome_id,side,type,price,shares,amount_usd,fee_usd,timestamp,tx_hash) FROM stdin;'
\copy (SELECT id,wallet,market_id,outcome_id,side,type,price,shares,amount_usd,fee_usd,timestamp,tx_hash FROM s_trades) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY positions (wallet,market_id,outcome_id,side,status,avg_entry_price,shares,entry_time,exit_time,realized_pnl,unrealized_pnl,total_pnl) FROM stdin;'
\copy (SELECT p.wallet,p.market_id,p.outcome_id,p.side,p.status,p.avg_entry_price,p.shares,p.entry_time,p.exit_time,p.realized_pnl,p.unrealized_pnl,p.total_pnl FROM positions p JOIN s_wallets w ON w.wallet=p.wallet JOIN s_markets m ON m.id=p.market_id) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY wallet_analytics (wallet,snapshot_date,total_pnl,total_realized_pnl,total_unrealized_pnl,roi,total_volume,total_cost_basis,win_rate,num_trades,num_resolved_positions,profit_factor,sharpe_ratio,max_drawdown,avg_position_size,avg_holding_duration,consistency_score,experience_score,wallet_score,edge_score,follow_score,category_follow_scores) FROM stdin;'
\copy (SELECT a.* FROM wallet_analytics a JOIN s_wallets s ON s.wallet=a.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY ranking_snapshots (wallet,snapshot_date,list_type,rank,wallet_score,roi,win_rate,consistency_score,experience_score,risk_adj_return,total_pnl,num_trades,edge_score) FROM stdin;'
\copy (SELECT r.* FROM ranking_snapshots r JOIN s_wallets s ON s.wallet=r.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY category_analytics (wallet,category,snapshot_date,num_trades,total_volume,total_cost_basis,total_pnl,total_realized_pnl,total_unrealized_pnl,roi,win_rate,num_resolved_positions,profit_factor,avg_position_size,avg_holding_duration,is_specialist,category_rank) FROM stdin;'
\copy (SELECT c.* FROM category_analytics c JOIN s_wallets s ON s.wallet=c.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY category_rankings (wallet,category,snapshot_date,list_type,rank,wallet_score,roi,win_rate,total_pnl,num_trades,total_volume) FROM stdin;'
\copy (SELECT c.* FROM category_rankings c JOIN s_wallets s ON s.wallet=c.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY wallet_pnl_snapshots (wallet,snapshot_date,total_pnl,total_realized_pnl,total_unrealized_pnl,total_bought,total_sold,total_redeemed,total_merged,total_split,total_rebates,category_breakdown,num_activity_events,open_position_value,computed_at) FROM stdin;'
\copy (SELECT p.* FROM wallet_pnl_snapshots p JOIN s_wallets s ON s.wallet=p.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY wallet_edge_snapshots (wallet,snapshot_date,avg_edge,median_edge,edge_consistency,edge_volatility,edge_score,num_edge_trades,positive_edge_trades,negative_edge_trades,computed_at) FROM stdin;'
\copy (SELECT e.* FROM wallet_edge_snapshots e JOIN s_wallets s ON s.wallet=e.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY wallet_category_follow_scores (wallet,category,snapshot_date,follow_score,recommendation,roi_percentile,win_rate,is_specialist,volume_percentile,recency_days,reasons,global_follow_score) FROM stdin;'
\copy (SELECT f.* FROM wallet_category_follow_scores f JOIN s_wallets s ON s.wallet=f.wallet) TO STDOUT
\echo '\\.'
\echo ''

\echo 'COPY pipeline_run_log (pipeline_name,status,updated_at) FROM stdin;'
\copy (SELECT * FROM pipeline_run_log) TO STDOUT
\echo '\\.'
\echo ''

\echo 'SET session_replication_role = DEFAULT;'
SQL

VERSION=$("${PSQL[@]}" -At -c "select version_num from alembic_version;" | tr -d '\r')

{
  cat "$TMP/schema.sql"
  echo
  cat "$TMP/data.sql"
  echo
  echo "INSERT INTO public.alembic_version (version_num) VALUES ('${VERSION}') ON CONFLICT DO NOTHING;"
} | gzip -9 > "$OUT"

echo "→ wrote $OUT ($(du -h "$OUT" | cut -f1), alembic revision ${VERSION})"
