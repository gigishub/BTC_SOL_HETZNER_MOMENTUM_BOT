#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/root/projects/trading_bot"
VENV_ACTIVATE="/root/.venv/bin/activate"
LOCK_FILE="/tmp/trading_bot_daily.lock"

cd "$PROJECT_DIR"
source "$VENV_ACTIVATE"

# Prevent overlapping runs if a previous run is still active.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') - Previous run still active, skipping."
  exit 0
fi

timeout 30m python -c "from trade_BTC_SOL import trade_SOL, trade_BTC; trade_SOL(False, wait_for_candle=True); trade_BTC(False, wait_for_candle=True)"
