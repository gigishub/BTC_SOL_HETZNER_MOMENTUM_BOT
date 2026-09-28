#!/usr/bin/env bash
# Dry run of the redesigned bot: logs what it would do, places no orders.
# Cron (after the live run): 15 0 * * * /root/projects/trading_bot/run_dry.sh >> /root/projects/trading_bot/dry_run.log 2>&1
set -euo pipefail

PROJECT_DIR="/root/projects/trading_bot"
VENV_ACTIVATE="/root/.venv/bin/activate"
LOCK_FILE="/tmp/trading_bot_dry.lock"

cd "$PROJECT_DIR"
source "$VENV_ACTIVATE"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') - Previous dry run still active, skipping."
  exit 0
fi

timeout 30m python -m bot.runner --dry-run
