"""Pure strategy logic: closed candles in, trade state and today's decision out. No I/O."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import StrategyParams

BUY, CAUTION, NONE = "buy", "caution", "no_signal"


def indicators(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    """Add indicator and raw (unshifted) signal columns. Row t uses data up to the close of t."""
    out = df.copy()
    c = out["close"]
    tr = pd.concat([out["high"] - out["low"], (out["high"] - c.shift()).abs(), (out["low"] - c.shift()).abs()],
                   axis=1).max(axis=1)
    out["atr_sl"] = tr.rolling(p.atr_length_sl).mean()
    out["atr_vola"] = tr.rolling(p.atr_length_vola).mean()
    out["ema_trend"] = c.ewm(span=p.ema_trend_length, adjust=False).mean()
    out["ema_is_bullish"] = c.ewm(span=p.ema_is_bullish_length, adjust=False).mean()
    out["trail_source"] = out["low"].rolling(p.trail_lookback).max()
    out["atr_size_pct"] = tr.rolling(p.size_atr_length).mean() / c

    ready = out["atr_sl"].notna() & out["atr_vola"].notna() & out["ema_trend"].notna()
    bullish = (c > out["ema_trend"]) & (c > out["ema_is_bullish"]) & ready
    vola_spike = (out["high"].rolling(p.lookback_high).max() - out["low"]) > out["atr_vola"] * p.atr_vol_multiplier
    out["raw_signal"] = np.select([bullish & ~vola_spike, bullish & vola_spike], [BUY, CAUTION], default=NONE)

    if p.ret_min is None:
        out["raw_entry_ok"] = True
    else:
        out["raw_entry_ok"] = (c / c.shift(p.ret_lookback) - 1) >= p.ret_min
    return out


def compute_state(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    """Replay the strategy over all bars.

    Row i describes the position held during bar i (bought/sold at open of i), decided with data
    up to the close of bar i-1.
    """
    x = indicators(df, p)
    signal = x["raw_signal"].shift(1).to_numpy()
    entry_ok = x["raw_entry_ok"].shift(1, fill_value=False).to_numpy(dtype=bool)
    close = x["close"].to_numpy()
    ts = x["trail_source"].to_numpy()
    atr = x["atr_sl"].to_numpy()
    n = len(x)
    in_trade = np.zeros(n, dtype=int)
    trail = np.full(n, np.nan)
    sl_hit = np.zeros(n, dtype=bool)

    for i in range(1, n):
        was_in = in_trade[i - 1] == 1
        if was_in and not np.isnan(trail[i - 1]) and close[i - 1] < trail[i - 1]:
            sl_hit[i] = True  # stop broken on the previous close: out at this open, no re-entry this bar
            continue
        if was_in:
            in_trade[i] = 1
            if signal[i] in (BUY, CAUTION):
                mult = 1.0 if signal[i] == BUY else p.caution_atr_mult
                new_sl = ts[i] - atr[i] * mult
                trail[i] = np.fmax(new_sl, trail[i - 1])  # stop only moves up; ignores a missing value
            else:
                trail[i] = trail[i - 1]
        elif signal[i] == BUY and entry_ok[i]:
            in_trade[i] = 1
            trail[i] = ts[i] - atr[i]

    x["signal"] = signal
    x["entry_ok"] = entry_ok
    x["in_trade"] = in_trade
    x["trail_sl"] = trail
    x["sl_hit"] = sl_hit
    return x


@dataclass(frozen=True)
class Decision:
    target: int          # 1 = should hold the coin today, 0 = should not
    event: str           # "entry", "exit", "hold", or "flat"
    last_close_time: pd.Timestamp
    last_close: float
    stop: float          # trailing stop as of the last close (nan when flat)
    signal: str          # signal from the last close
    entry_ok: bool       # entry filter result from the last close
    size: float = 1.0    # fraction of the coin's slot to buy on entry


def decide_today(closed: pd.DataFrame, p: StrategyParams, bar: pd.Timedelta) -> Decision:
    """Decision for the bar that opens right after the last closed bar."""
    nxt = closed.index[-1] + bar
    padded = pd.concat([closed, pd.DataFrame(index=pd.DatetimeIndex([nxt]), columns=closed.columns, dtype=float)])
    s = compute_state(padded, p)
    now, prev = s.iloc[-1], s.iloc[-2]
    if now["sl_hit"]:
        event = "exit"
    elif now["in_trade"] and not prev["in_trade"]:
        event = "entry"
    elif now["in_trade"]:
        event = "hold"
    else:
        event = "flat"
    return Decision(int(now["in_trade"]), event, closed.index[-1], float(prev["close"]),
                    float(prev["trail_sl"]), str(now["signal"]), bool(now["entry_ok"]),
                    position_size(prev["atr_size_pct"], p.size_target))


def position_size(atr_pct: float, target: float | None) -> float:
    """min(1, target / ATR%); full size when sizing is off or ATR is unknown."""
    if target is None or not np.isfinite(atr_pct) or atr_pct <= 0:
        return 1.0
    return min(1.0, target / atr_pct)
