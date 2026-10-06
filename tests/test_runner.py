"""Action table and dry-run behaviour of the runner, with a fake account and fake candles."""

from __future__ import annotations

import pandas as pd
import pytest

from bot import runner
from bot.config import SymbolConfig
from bot.signals import Decision


def decision(target: int, event: str, size: float = 1.0) -> Decision:
    return Decision(target, event, pd.Timestamp("2026-01-01", tz="UTC"), 1.0, float("nan"), "buy", True, size)


@pytest.mark.parametrize("target,event,holding,expected", [
    (1, "entry", False, runner.BUY),
    (1, "entry", True, runner.HOLD),
    (1, "hold", True, runner.HOLD),
    (1, "hold", False, runner.MISSED),   # failed/manual buy: do not chase
    (0, "exit", True, runner.SELL),
    (0, "exit", False, runner.NOTHING),
    (0, "flat", True, runner.SELL),      # leftover coins after a failed sell get cleaned up
    (0, "flat", False, runner.NOTHING),
])
def test_choose_action(target, event, holding, expected):
    assert runner.choose_action(decision(target, event), holding) == expected


class FakeAccount:
    def __init__(self, holding: bool):
        self.holding = holding
        self.orders = []

    def is_holding(self, symbol):
        return self.holding

    def buy_amount(self, symbol, all_symbols, size=1.0):
        return size

    def sell_amount(self, symbol):
        return 1.0

    def market_buy(self, symbol, amount):
        self.orders.append(("buy", symbol, amount))

    def market_sell(self, symbol, amount):
        self.orders.append(("sell", symbol, amount))


@pytest.mark.parametrize("dry_run,holding,target,event,expected_orders", [
    (True, False, 1, "entry", []),
    (True, True, 0, "exit", []),
    (False, False, 1, "entry", [("buy", "BTC-USDT", 1.0)]),
    (False, True, 0, "exit", [("sell", "BTC-USDT", 1.0)]),
])
def test_run_symbol_places_orders_only_when_live(monkeypatch, dry_run, holding, target, event, expected_orders):
    monkeypatch.setattr(runner, "closed_candles", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(runner, "decide_today", lambda *a, **k: decision(target, event))
    acct = FakeAccount(holding)
    runner.run_symbol(SymbolConfig("BTC-USDT"), acct, ["SOL-USDT", "BTC-USDT"], dry_run=dry_run)
    assert acct.orders == expected_orders


def test_run_symbol_buys_the_decided_size(monkeypatch):
    monkeypatch.setattr(runner, "closed_candles", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(runner, "decide_today", lambda *a, **k: decision(1, "entry", size=0.4))
    acct = FakeAccount(False)
    runner.run_symbol(SymbolConfig("BTC-USDT"), acct, ["SOL-USDT", "BTC-USDT"], dry_run=False)
    assert acct.orders == [("buy", "BTC-USDT", 0.4)]
