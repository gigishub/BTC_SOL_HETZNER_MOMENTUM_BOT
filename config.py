"""
Configuration file for trading bot parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# ====================================================================================
# EXCHANGE API CREDENTIALS
# ====================================================================================
API_KEY = os.getenv('KUCOIN_API_KEY')
API_SECRET = os.getenv('KUCOIN_API_SECRET')
API_PASSPHRASE = os.getenv('KUCOIN_API_PASSPHRASE')

# Validate that credentials are loaded
if not all([API_KEY, API_SECRET, API_PASSPHRASE]):
    raise ValueError(
        "Missing API credentials! Please ensure .env file exists with:\n"
        "KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE"
    )

# ====================================================================================
# STRATEGY PARAMETERS FOR BTC
# ====================================================================================
BTC_CONFIG = {
    'symbol': 'BTC-USDT',
    'timeframe': '1day',
    'atr_length_sl': 5,
    'atr_length_vola': 5,
    'ema_trend_length': 240,
    'ema_is_bullish_length': 10,
    'lookback_high': 7,
    'atr_vol_multiplier': 1.6
}

# ====================================================================================
# STRATEGY PARAMETERS FOR SOL
# ====================================================================================
SOL_CONFIG = {
    'symbol': 'SOL-USDT',
    'timeframe': '1day',
    'atr_length_sl': 5,
    'atr_length_vola': 5,
    'ema_trend_length': 240,
    'ema_is_bullish_length': 10,
    'lookback_high': 7,
    'atr_vol_multiplier': 1.6
}

# ====================================================================================
# GENERAL SETTINGS
# ====================================================================================
LOOKBACK_BARS = 700
