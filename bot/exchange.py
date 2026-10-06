"""KuCoin spot account via ccxt: holdings, order sizing, market orders."""

from __future__ import annotations

import logging
import math
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)


def _round_down(amount: float, precision: float) -> float:
    decimals = abs(Decimal(str(precision)).as_tuple().exponent)
    factor = 10 ** decimals
    return math.floor(amount * factor) / factor


class KucoinAccount:
    def __init__(self):
        import ccxt
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        creds = {k: os.getenv(k) for k in ("KUCOIN_API_KEY", "KUCOIN_API_SECRET", "KUCOIN_API_PASSPHRASE")}
        missing = [k for k, v in creds.items() if not v]
        if missing:
            raise ValueError(f"Missing API credentials in .env: {', '.join(missing)}")
        self.exchange = ccxt.kucoin({"apiKey": creds["KUCOIN_API_KEY"], "secret": creds["KUCOIN_API_SECRET"],
                                     "password": creds["KUCOIN_API_PASSPHRASE"]})
        self.exchange.load_markets()

    @staticmethod
    def _retry(fn, attempts: int = 4, wait_s: float = 5.0):
        """Retry a read-only call on network or rate-limit errors. Never used for orders."""
        import ccxt
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except ccxt.NetworkError as exc:
                if attempt == attempts:
                    raise
                logger.warning("exchange read failed (attempt %d/%d): %s", attempt, attempts, exc)
                time.sleep(wait_s * attempt)

    def free(self, asset: str) -> float:
        balance = self._retry(self.exchange.fetch_balance)
        return float(balance.get(asset, {}).get("free") or 0.0)

    def is_holding(self, symbol: str) -> bool:
        """True if the free base-coin balance is above the exchange minimum order size."""
        base = symbol.split("-")[0]
        min_amount = self.exchange.market(symbol)["limits"]["amount"]["min"] or 0.0
        return self.free(base) > min_amount

    def snapshot(self, all_symbols: Sequence[str]) -> dict:
        """Free USDT, each coin's free amount, price and USDT value, and the account total."""
        balance = self._retry(self.exchange.fetch_balance)
        free = lambda asset: float(balance.get(asset, {}).get("free") or 0.0)
        coins = {}
        for s in all_symbols:
            price = self._retry(lambda s=s: self.exchange.fetch_ticker(s))["last"]
            qty = free(s.split("-")[0])
            coins[s] = {"qty": qty, "price": price, "value": qty * price}
        usdt = free("USDT")
        return {"usdt": usdt, "coins": coins, "total": usdt + sum(c["value"] for c in coins.values())}

    def buy_amount(self, symbol: str, all_symbols: Sequence[str], size: float = 1.0) -> float:
        """Slot = account value / number of coins, times size; capped at free USDT."""
        snap = self.snapshot(all_symbols)
        usdt = min(snap["usdt"], snap["total"] / len(all_symbols) * size)
        price = snap["coins"][symbol]["price"]
        amount = _round_down(usdt / price, self.exchange.market(symbol)["precision"]["amount"])
        logger.info("%s: using %.2f USDT (account %.2f / %d x size %.2f) at %s -> %s",
                    symbol, usdt, snap["total"], len(all_symbols), size, price, amount)
        return amount

    def sell_amount(self, symbol: str) -> float:
        base = symbol.split("-")[0]
        return _round_down(self.free(base), self.exchange.market(symbol)["precision"]["amount"])

    def market_buy(self, symbol: str, amount: float):
        return self.exchange.create_market_buy_order(symbol, amount)

    def market_sell(self, symbol: str, amount: float):
        return self.exchange.create_market_sell_order(symbol, amount)
