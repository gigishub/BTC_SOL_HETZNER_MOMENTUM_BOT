#!/root/venv/bin/python
"""
Trade execution functions for BTC and SOL trading pairs.
This module provides clean interfaces to run trading strategies for both assets.
"""

import logging
from strategy import TradingStrategy
from config import BTC_CONFIG, SOL_CONFIG

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.propagate = False


def trade_SOL(testing: bool = False, wait_for_candle: bool = True):
    """
    Execute SOL trading strategy.
    
    Args:
        testing: If True, use minimum order sizes for testing
        wait_for_candle: If True, wait until candle is complete before running
    """
    config = SOL_CONFIG
    
    # Initialize strategy with SOL configuration
    strategy = TradingStrategy(config['symbol'], config['timeframe'])
    
    # Wait for current period candle to ensure previous daily candle is finalized.
    if wait_for_candle:
        if not strategy.wait_for_candle_completion():
            logger.warning(f"Skip {config['symbol']} run: current period candle not available yet.")
            return
    else:
        strategy.update_til_now(lookback_bars=700)
    
    logger.info(f"Check {config['symbol']} for trade signal")
    
    # Log account status at the start of each run
    strategy.log_account_status()
    
    # Calculate indicators
    strategy.calculate_indicators(
        atr_length_sl=config['atr_length_sl'],
        atr_length_vola=config['atr_length_vola'],
        ema_trend_length=config['ema_trend_length'],
        ema_is_bullish_length=config['ema_is_bullish_length']
    )
    
    # Generate signals
    strategy.get_signal(
        lookback_high=config['lookback_high'],
        atr_vol_multiplier=config['atr_vol_multiplier']
    )
    
    # Process all historical bars to update trade state
    for i in range(1, len(strategy.df)):
        strategy.check_sl(i)
        
        if not strategy.df['sl_hit'].iloc[i]:
            strategy.handle_signal(i)
            strategy.update_trail_sl(i)
            strategy.set_in_trade(i)
    
    # Execute trades based on current signals
    strategy.execute_trades(testing)


def trade_BTC(testing: bool = False, wait_for_candle: bool = True):
    """
    Execute BTC trading strategy.
    
    Args:
        testing: If True, use minimum order sizes for testing
        wait_for_candle: If True, wait until candle is complete before running
    """
    config = BTC_CONFIG
    
    # Initialize strategy with BTC configuration
    strategy = TradingStrategy(config['symbol'], config['timeframe'])
    
    # Wait for current period candle to ensure previous daily candle is finalized.
    if wait_for_candle:
        if not strategy.wait_for_candle_completion():
            logger.warning(f"Skip {config['symbol']} run: current period candle not available yet.")
            return
    else:
        strategy.update_til_now(lookback_bars=700)
    
    logger.info(f"Check {config['symbol']} for trade signal")
    
    # Log account status at the start of each run
    strategy.log_account_status()
    
    # Calculate indicators
    strategy.calculate_indicators(
        atr_length_sl=config['atr_length_sl'],
        atr_length_vola=config['atr_length_vola'],
        ema_trend_length=config['ema_trend_length'],
        ema_is_bullish_length=config['ema_is_bullish_length']
    )
    
    # Generate signals
    strategy.get_signal(
        lookback_high=config['lookback_high'],
        atr_vol_multiplier=config['atr_vol_multiplier']
    )
    
    # Process all historical bars to update trade state
    for i in range(1, len(strategy.df)):
        strategy.check_sl(i)
        
        if not strategy.df['sl_hit'].iloc[i]:
            strategy.handle_signal(i)
            strategy.update_trail_sl(i)
            strategy.set_in_trade(i)
    
    # Execute trades based on current signals
    strategy.execute_trades(testing)


if __name__ == '__main__':
    # For testing individual functions
    # Execution is managed by trading_main.py
    pass
