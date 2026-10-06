"""Daily run: for each coin, fetch closed candles, decide, compare with the real holding, act.

Usage: python -m bot.runner [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import LOOKBACK_BARS, SYMBOLS, SymbolConfig
from .data import bar_length, closed_candles
from .signals import Decision, decide_today

logger = logging.getLogger("bot")

BUY, SELL, HOLD, NOTHING, MISSED = "buy", "sell", "hold", "nothing", "missed_entry"


def choose_action(d: Decision, holding: bool) -> str:
    """Compare what the strategy wants with what the account actually holds."""
    if d.target == 0:
        return SELL if holding else NOTHING  # also sells a position left over from a failed sell
    if holding:
        return HOLD
    return BUY if d.event == "entry" else MISSED  # never chase a trade that started earlier


def run_symbol(cfg: SymbolConfig, account, all_symbols: list[str], dry_run: bool) -> str:
    closed = closed_candles(cfg.symbol, cfg.timeframe, LOOKBACK_BARS)
    d = decide_today(closed, cfg.params, bar_length(cfg.timeframe))
    holding = account.is_holding(cfg.symbol)
    action = choose_action(d, holding)
    logger.info("%s | last close %s = %.4f | signal=%s entry_ok=%s stop=%.4f size=%.2f | strategy=%s (%s) | holding=%s -> %s",
                cfg.symbol, d.last_close_time.date(), d.last_close, d.signal, d.entry_ok, d.stop, d.size,
                "IN" if d.target else "OUT", d.event, holding, action.upper())

    if action == MISSED:
        logger.warning("%s: strategy is in a trade but the account holds nothing (failed or manual order?). "
                       "Not buying mid-trade; will enter on the next entry signal.", cfg.symbol)
    elif action == SELL:
        amount = account.sell_amount(cfg.symbol)
        if dry_run:
            logger.info("%s: DRY RUN - would market SELL %s", cfg.symbol, amount)
        else:
            logger.info("%s: market SELL %s -> %s", cfg.symbol, amount, account.market_sell(cfg.symbol, amount))
    elif action == BUY:
        amount = account.buy_amount(cfg.symbol, all_symbols, d.size)
        if dry_run:
            logger.info("%s: DRY RUN - would market BUY %s", cfg.symbol, amount)
        else:
            logger.info("%s: market BUY %s -> %s", cfg.symbol, amount, account.market_buy(cfg.symbol, amount))
    return action


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="log intended orders without placing them")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    logger.info("=== run start%s ===", " (DRY RUN)" if args.dry_run else "")

    from .exchange import KucoinAccount
    account = KucoinAccount()
    symbols = [c.symbol for c in SYMBOLS]
    failed = False
    for cfg in SYMBOLS:
        try:
            run_symbol(cfg, account, symbols, args.dry_run)
        except Exception:
            logger.exception("%s: run failed", cfg.symbol)
            failed = True
    logger.info("=== run end ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
