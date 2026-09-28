"""Fetch daily candles from KuCoin and keep only closed bars."""

from __future__ import annotations

import logging
import time
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

KUCOIN_URL = "https://api.kucoin.com/api/v1/market/candles"


def bar_length(timeframe: str) -> pd.Timedelta:
    for suffix, unit in (("min", "min"), ("hour", "h"), ("day", "D"), ("week", "W")):
        if timeframe.endswith(suffix):
            return pd.Timedelta(int(timeframe[: -len(suffix)]), unit=unit)
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def fetch_candles(symbol: str, timeframe: str, bars: int, now: pd.Timestamp) -> pd.DataFrame:
    """One request to KuCoin (max 1500 bars). Includes the unfinished current bar if KuCoin has it."""
    start = now - bar_length(timeframe) * bars
    params = {"type": timeframe, "symbol": symbol, "startAt": int(start.timestamp()), "endAt": int(now.timestamp())}
    resp = requests.get(KUCOIN_URL, params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != "200000":
        raise RuntimeError(f"KuCoin API error: {payload}")
    df = pd.DataFrame(payload["data"], columns=["time", "open", "close", "high", "low", "volume", "turnover"])
    df.index = pd.to_datetime(df.pop("time").astype(int), unit="s", utc=True)
    return df[["open", "high", "low", "close", "volume"]].astype(float).sort_index()


def closed_candles(symbol: str, timeframe: str, bars: int, now: Optional[pd.Timestamp] = None,
                   attempts: int = 10, wait_s: float = 10.0) -> pd.DataFrame:
    """Closed bars only, up to and including the most recently finished bar.

    Retries until the exchange has published the last finished bar, then raises if it never does.
    """
    now = now or pd.Timestamp.now(tz="UTC")
    bar = bar_length(timeframe)
    current_start = now.floor(bar) if bar <= pd.Timedelta(days=1) else now.normalize()
    expected_last = current_start - bar
    for attempt in range(1, attempts + 1):
        try:
            df = fetch_candles(symbol, timeframe, bars, now)
            closed = df[df.index + bar <= now]
            if len(closed) and closed.index[-1] == expected_last:
                return closed
            logger.info("%s: last closed bar %s, waiting for %s (attempt %d/%d)", symbol,
                        closed.index[-1] if len(closed) else None, expected_last, attempt, attempts)
        except Exception as exc:  # network hiccups are retried
            logger.warning("%s: fetch failed (attempt %d/%d): %s", symbol, attempt, attempts, exc)
        time.sleep(wait_s)
    raise RuntimeError(f"{symbol}: bar {expected_last} not available after {attempts} attempts")
