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

REPO="/home/src/default_repo"

if [ $# -eq 0 ]; then
  info "Running full ETL orchestration..."
  docker compose exec -T mage mage run "$REPO" orchestration
else
  for p in "$@"; do
    info "Running pipeline: $p"
    docker compose exec -T mage mage run "$REPO" "$p"
    echo ""
  done
fi

echo ""
echo "============================================"
echo " Done."
echo "============================================"
