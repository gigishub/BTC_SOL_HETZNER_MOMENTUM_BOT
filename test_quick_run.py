#!/usr/bin/env python3
"""
Quick test run of the trading strategy without waiting for candle completion.
This is useful for testing the bot's logic immediately.
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


def quick_test_strategy(symbol_config, testing=True):
    """Run strategy without waiting for candle completion."""
    config = symbol_config
    symbol = config['symbol']
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing {symbol} Strategy")
    logger.info(f"{'='*70}")
    
    try:
        # Initialize strategy
        strategy = TradingStrategy(config['symbol'], config['timeframe'])
        logger.info(f"✓ Strategy initialized for {symbol}")
        
        # Fetch data (without waiting for candle completion)
        logger.info(f"Fetching recent data for {symbol}...")
        strategy.update_til_now(lookback_bars=100)
        logger.info(f"✓ Retrieved {len(strategy.df)} candles")
        
        # Calculate indicators
        strategy.calculate_indicators(
            atr_length_sl=config['atr_length_sl'],
            atr_length_vola=config['atr_length_vola'],
            ema_trend_length=config['ema_trend_length'],
            ema_is_bullish_length=config['ema_is_bullish_length']
        )
        logger.info(f"✓ Indicators calculated")
        
        # Generate signals
        strategy.get_signal(
            lookback_high=config['lookback_high'],
            atr_vol_multiplier=config['atr_vol_multiplier']
        )
        logger.info(f"✓ Signals generated")
        
        # Process all historical bars
        for i in range(1, len(strategy.df)):
            strategy.check_sl(i)
            if not strategy.df['sl_hit'].iloc[i]:
                strategy.handle_signal(i)
                strategy.update_trail_sl(i)
                strategy.set_in_trade(i)
        
        logger.info(f"✓ Trade management logic processed")
        
        # Show recent data
        logger.info(f"\nRecent 10 candles:")
        recent_data = strategy.df[['open', 'close', 'signal', 'in_trade', 'trail_sl']].tail(10)
        print(recent_data.to_string())
        
        # Current status
        logger.info(f"\n{'='*70}")
        logger.info(f"CURRENT STATUS for {symbol}:")
        logger.info(f"{'='*70}")
        logger.info(f"Latest Signal: {strategy.df['signal'].iloc[-1]}")
        logger.info(f"In Trade: {strategy.df['in_trade'].iloc[-1]}")
        logger.info(f"Current Price: ${strategy.df['close'].iloc[-1]:,.2f}")
        
        if strategy.df['in_trade'].iloc[-1] == 1:
            logger.info(f"Trail Stop-Loss: ${strategy.df['trail_sl'].iloc[-1]:,.2f}")
            distance = strategy.df['close'].iloc[-1] - strategy.df['trail_sl'].iloc[-1]
            percent = (distance / strategy.df['close'].iloc[-1]) * 100
            logger.info(f"Distance to SL: ${distance:,.2f} ({percent:.2f}%)")
        
        logger.info(f"{'='*70}\n")
        
        # Show what action would be taken
        if strategy.df['sl_hit'].iloc[-1]:
            logger.info(f"⚠️  ACTION: Would SELL {symbol} (Stop-loss hit)")
        elif strategy.df['signal'].iloc[-1] == 'buy' and strategy.df['in_trade'].iloc[-2] == 0:
            logger.info(f"🟢 ACTION: Would BUY {symbol} (New signal)")
        elif strategy.df['in_trade'].iloc[-1] == 1:
            logger.info(f"⏸️  ACTION: Hold {symbol} (Trade active)")
        else:
            logger.info(f"⏹️  ACTION: No action for {symbol}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run quick tests for both trading pairs."""
    logger.info("\n" + "="*70)
    logger.info("TRADING BOT QUICK TEST (No actual trading)")
    logger.info("="*70)
    
    # Test SOL
    quick_test_strategy(SOL_CONFIG, testing=True)
    
    # Test BTC
    quick_test_strategy(BTC_CONFIG, testing=True)
    
    logger.info("\n" + "="*70)
    logger.info("✅ QUICK TEST COMPLETE")
    logger.info("="*70)
    logger.info("\nNote: This was a dry-run. No actual trades were executed.")
    logger.info("To run the bot live, use: python trading_main.py")


if __name__ == "__main__":
    main()
