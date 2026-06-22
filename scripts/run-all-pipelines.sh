#!/usr/bin/env bash
set -euo pipefail

error() { echo "[ERROR] $*" >&2; }
info()  { echo "[INFO] $*"; }

check_docker() {
  local ps_out
  ps_out=$(docker compose ps 2>/dev/null)
  if ! echo "$ps_out" | grep -q "Up"; then
    error "Containers are not running. Start with: docker compose up -d"
    exit 1
  fi
  info "Containers are running."
}

echo "============================================"
echo " Polymarket Smart Money Tracker"
echo " Pipeline Runner"
echo "============================================"
echo ""

check_docker

PIPELINES=("$@")
if [ ${#PIPELINES[@]} -eq 0 ]; then
  PIPELINES=(
    "ingestion_market_discovery"
    "ingestion_wallet_discovery"
    "ingestion_position_sync"
    "ingestion_trade_history"
    "enrichment_analytics_computation"
    "enrichment_ranking_computation"
  )
fi

SCRIPT="/home/src/scripts/run_all.py"

for p in "${PIPELINES[@]}"; do
  info "Running pipeline: $p"
  docker compose exec -T mage python "$SCRIPT" "$p"
  echo ""
done

echo ""
echo "============================================"
echo " Done."
echo "============================================"
