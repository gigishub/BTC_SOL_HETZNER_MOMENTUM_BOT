"""The redesigned signals must reproduce the old bot exactly, and the BTC filter must match the research."""

from __future__ import annotations

import glob
import importlib.util
import logging
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bot.config import LOOKBACK_BARS, StrategyParams
from bot.signals import compute_state, decide_today

BOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BOT_DIR.parent / "crypto_data" / "data"
DAY = pd.Timedelta(days=1)

pytestmark = pytest.mark.skipif(not glob.glob(str(DATA_DIR / "*" / "*_1d_start_*.parquet")),
                                reason="research candle data not downloaded")


def load_legacy_strategy():
    """Import the old strategy.py with its exchange/credential imports stubbed out."""
    stubs = {"config": types.SimpleNamespace(LOOKBACK_BARS=700),
             "exchange_client": types.SimpleNamespace(ExchangeClient=lambda: None),
             "pandas_ta": types.SimpleNamespace()}
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("legacy_strategy", BOT_DIR / "strategy.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    logging.disable(logging.CRITICAL)
    return mod.TradingStrategy


LegacyStrategy = load_legacy_strategy()


def legacy_state(df: pd.DataFrame, p: StrategyParams, entry_ok: pd.Series = None) -> pd.DataFrame:
    """Replay exactly as trade_BTC_SOL.py does, optionally gating new entries (as in the research)."""
    s = LegacyStrategy.__new__(LegacyStrategy)
    s.df = df[["open", "close", "high", "low"]].copy()
    s.calculate_indicators(p.atr_length_sl, p.atr_length_vola, p.ema_trend_length, p.ema_is_bullish_length)
    s.get_signal(p.lookback_high, p.atr_vol_multiplier)
    for i in range(1, len(s.df)):
        s.check_sl(i)
        if not s.df["sl_hit"].iloc[i]:
            s.handle_signal(i)
            s.update_trail_sl(i)
            if entry_ok is None or entry_ok.iloc[i]:
                s.set_in_trade(i)
    return s.df


def load(symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(sorted(glob.glob(str(DATA_DIR / symbol / f"{symbol}_1d_start_*.parquet")))[-1])
    df.columns = [c.lower() for c in df.columns]
    return df[df.index + DAY <= pd.Timestamp.now(tz="UTC")]


SYMBOLS = sorted(Path(p).parent.name for p in glob.glob(str(DATA_DIR / "*" / "*_1d_start_*.parquet")))


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_matches_old_bot_without_filter(symbol):
    df = load(symbol)
    p = StrategyParams()
    new, old = compute_state(df, p), legacy_state(df, p)
    assert (new["in_trade"].to_numpy() == old["in_trade"].to_numpy()).all()
    assert (new["sl_hit"].to_numpy() == old["sl_hit"].to_numpy()).all()
    np.testing.assert_allclose(new["trail_sl"].to_numpy(), old["trail_sl"].astype(float).to_numpy(), equal_nan=True)


@pytest.mark.parametrize("symbol", ["BTCUSDT", "SOLUSDT", "ETHUSDT"])
def test_filter_matches_research(symbol):
    df = load(symbol)
    p = StrategyParams(ret_min=-0.03)
    research_ok = (df["close"] / df["close"].shift(20) - 1).shift(1) >= -0.03
    new, old = compute_state(df, p), legacy_state(df, p, entry_ok=research_ok)
    assert (new["in_trade"].to_numpy() == old["in_trade"].to_numpy()).all()
    assert new["in_trade"].sum() < compute_state(df, StrategyParams())["in_trade"].sum()  # filter does something


@pytest.mark.parametrize("symbol,params", [("BTCUSDT", StrategyParams(ret_min=-0.03)), ("SOLUSDT", StrategyParams())])
def test_daily_decision_matches_full_replay(symbol, params):
    """Each day's live decision (from a LOOKBACK_BARS window) equals the full-history replay."""
    df = load(symbol)
    full = compute_state(df, params)
    for t in range(len(df) - 120, len(df)):
        window = df.iloc[max(0, t - LOOKBACK_BARS):t]  # closed bars before bar t
        d = decide_today(window, params, DAY)
        assert d.target == full["in_trade"].iloc[t], f"{symbol} {df.index[t].date()}"
        assert (d.event == "exit") == bool(full["sl_hit"].iloc[t])
