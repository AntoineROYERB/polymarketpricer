#!/usr/bin/env bash
set -euo pipefail

error() { echo "[ERROR] $*" >&2; }
info()  { echo "[INFO] $*"; }

check_docker() {
  if ! docker compose ps 2>/dev/null | grep -q "Up"; then
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
    "market_discovery"
    "wallet_discovery"
    "position_sync"
    "trade_history"
    "analytics_computation"
    "ranking_computation"
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
