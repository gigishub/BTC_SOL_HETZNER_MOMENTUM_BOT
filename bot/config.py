"""Strategy settings per coin. No secrets here; API keys are loaded in exchange.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class StrategyParams:
    atr_length_sl: int = 5
    atr_length_vola: int = 5
    ema_trend_length: int = 240
    ema_is_bullish_length: int = 10
    lookback_high: int = 7
    atr_vol_multiplier: float = 1.6
    trail_lookback: int = 7
    caution_atr_mult: float = 0.2
    # Entry filter: no new trade if the coin's return over ret_lookback bars is below ret_min. None = off.
    ret_min: Optional[float] = None
    ret_lookback: int = 20
    # Position size at entry: min(1, size_target / ATR%), ATR over size_atr_length bars. None = full slot.
    size_target: Optional[float] = None
    size_atr_length: int = 14


@dataclass(frozen=True)
class SymbolConfig:
    symbol: str
    timeframe: str = "1day"
    params: StrategyParams = field(default_factory=StrategyParams)


SYMBOLS = [
    SymbolConfig("SOL-USDT", params=StrategyParams(size_target=0.05)),
    SymbolConfig("BTC-USDT", params=StrategyParams(ret_min=-0.03, size_target=0.05)),
]

LOOKBACK_BARS = 1500  # KuCoin max per request; enough to fully warm up EMA240
