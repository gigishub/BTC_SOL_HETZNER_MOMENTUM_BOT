"""Volatility sizing: the size factor from closed candles, and the order amount from account value."""

from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd
import pytest

from bot.config import StrategyParams
from bot.exchange import KucoinAccount
from bot.signals import compute_state, decide_today, position_size

DAY = pd.Timedelta(days=1)
sys.modules.setdefault("ccxt", types.SimpleNamespace(NetworkError=type("NetworkError", (Exception,), {})))  # local runs without ccxt


def candles(n=400, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.04, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"open": close * (1 + rng.normal(0, 0.01, n)), "high": close * 1.03,
                         "low": close * 0.97, "close": close}, index=idx)


@pytest.mark.parametrize("atr,target,expected", [
    (0.10, 0.05, 0.5), (0.02, 0.05, 1.0), (0.05, 0.05, 1.0),
    (0.10, None, 1.0), (float("nan"), 0.05, 1.0), (0.0, 0.05, 1.0),
])
def test_position_size(atr, target, expected):
    assert position_size(atr, target) == pytest.approx(expected)


def test_decision_size_uses_atr14_at_last_close():
    df = candles()
    p = StrategyParams(size_target=0.05)
    tr = pd.concat([df.high - df.low, (df.high - df.close.shift()).abs(), (df.low - df.close.shift()).abs()], axis=1).max(axis=1)
    atr_pct = (tr.rolling(14).mean() / df.close).iloc[-1]
    assert decide_today(df, p, DAY).size == pytest.approx(min(1.0, 0.05 / atr_pct))
    assert decide_today(df, StrategyParams(), DAY).size == 1.0


def test_sizing_does_not_change_trades():
    df = candles(seed=3)
    a = compute_state(df, StrategyParams())
    b = compute_state(df, StrategyParams(size_target=0.03, size_atr_length=7))
    assert (a.in_trade == b.in_trade).all() and a.trail_sl.equals(b.trail_sl)


class FakeExchange:
    def __init__(self, free, prices):
        self._free, self._prices = free, prices

    def fetch_balance(self):
        return {k: {"free": v} for k, v in self._free.items()}

    def fetch_ticker(self, symbol):
        return {"last": self._prices[symbol]}

    def market(self, symbol):
        return {"precision": {"amount": 1e-8}, "limits": {"amount": {"min": 1e-5}}}


def account(free, prices):
    acct = KucoinAccount.__new__(KucoinAccount)
    acct.exchange = FakeExchange(free, prices)
    return acct


SYMS = ["SOL-USDT", "BTC-USDT"]
PRICES = {"SOL-USDT": 100.0, "BTC-USDT": 50_000.0}


def test_both_flat_full_size_is_half_the_account():
    amt = account({"USDT": 1000.0}, PRICES).buy_amount("BTC-USDT", SYMS, 1.0)
    assert amt * 50_000 == pytest.approx(500.0)


def test_sized_entry_buys_fraction_of_the_slot():
    amt = account({"USDT": 1000.0}, PRICES).buy_amount("SOL-USDT", SYMS, 0.4)
    assert amt * 100 == pytest.approx(200.0)


def test_second_coin_gets_its_slot_not_the_other_coins_unused_cash():
    # SOL entered at 0.4 of a 500 slot: 200 in SOL, 800 USDT left. BTC full size gets 500, not 800.
    amt = account({"USDT": 800.0, "SOL": 2.0}, PRICES).buy_amount("BTC-USDT", SYMS, 1.0)
    assert amt * 50_000 == pytest.approx(500.0)


def test_slot_is_capped_at_free_usdt():
    # SOL position grew to 900: account 1300, slot 650, but only 400 USDT free.
    amt = account({"USDT": 400.0, "SOL": 9.0}, PRICES).buy_amount("BTC-USDT", SYMS, 1.0)
    assert amt * 50_000 == pytest.approx(400.0)
