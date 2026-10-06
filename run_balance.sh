#!/usr/bin/env bash
# Hourly account value snapshot into balance.csv (read-only exchange calls).
# Cron: 30 * * * * /root/projects/trading_bot/run_balance.sh >> /root/projects/trading_bot/balance.log 2>&1
set -euo pipefail
cd /root/projects/trading_bot
source /root/.venv/bin/activate
timeout 5m python -m bot.balance
