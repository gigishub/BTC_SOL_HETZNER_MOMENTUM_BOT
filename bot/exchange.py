"""KuCoin spot account via ccxt: holdings, order sizing, market orders."""

from __future__ import annotations

import logging
import math
import os
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

    def free(self, asset: str) -> float:
        return float(self.exchange.fetch_balance().get(asset, {}).get("free") or 0.0)

    def is_holding(self, symbol: str) -> bool:
        """True if the free base-coin balance is above the exchange minimum order size."""
        base = symbol.split("-")[0]
        min_amount = self.exchange.market(symbol)["limits"]["amount"]["min"] or 0.0
        return self.free(base) > min_amount

    def buy_amount(self, symbol: str, all_symbols: Sequence[str]) -> float:
        """Split free USDT equally over the coins not currently held (this one included)."""
        not_held = [s for s in all_symbols if s == symbol or not self.is_holding(s)]
        usdt = self.free("USDT") / len(not_held)
        price = self.exchange.fetch_ticker(symbol)["last"]
        amount = _round_down(usdt / price, self.exchange.market(symbol)["precision"]["amount"])
        logger.info("%s: using %.2f USDT (1/%d of free) at %s -> %s", symbol, usdt, len(not_held), price, amount)
        return amount

    def sell_amount(self, symbol: str) -> float:
        base = symbol.split("-")[0]
        return _round_down(self.free(base), self.exchange.market(symbol)["precision"]["amount"])

    def market_buy(self, symbol: str, amount: float):
        return self.exchange.create_market_buy_order(symbol, amount)

    def market_sell(self, symbol: str, amount: float):
        return self.exchange.create_market_sell_order(symbol, amount)
