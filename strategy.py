"""
Trading strategy implementation.
Handles data fetching, indicator calculation, signal generation, and trade management.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
import datetime
import requests
import logging
import time
from exchange_client import ExchangeClient
from config import LOOKBACK_BARS

# Configure logging with handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    Implements a trend-following trading strategy with volatility filters.
    Uses EMAs for trend detection and ATR for stop-loss management.
    """
    
    def __init__(self, symbol: str, timeframe: str):
        """
        Initialize the trading strategy.
        
        Args:
            symbol: Trading pair (e.g., 'BTC-USDT')
            timeframe: Candle timeframe (e.g., '1day', '1hour', '15min')
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.df = None
        self.exchange_client = ExchangeClient()
    
    def update_til_now(self, lookback_bars: int = LOOKBACK_BARS) -> pd.DataFrame:
        """
        Fetch and process historical candle data up to now.
        
        Args:
            lookback_bars: Number of historical bars to fetch
            
        Returns:
            DataFrame with processed candle data
        """
        end_time = datetime.datetime.now(datetime.timezone.utc)
        start_time = self._calculate_start_time_in_bars(lookback_bars)
        raw_data = self._get_historic_candles(start_time=start_time, end_time=end_time)
        return self._transform_candle_data(raw_data)
    
    def _get_historic_candles(self, market_type: str = "spot", 
                             start_time: datetime.datetime = None, 
                             end_time: datetime.datetime = None) -> list:
        """
        Fetch historical candle data from KuCoin API.
        
        Args:
            market_type: 'spot' or 'futures'
            start_time: Start datetime for data fetch
            end_time: End datetime for data fetch
            
        Returns:
            Raw candle data from API
        """
        base_url = "https://api.kucoin.com" if market_type.lower() == "spot" else "https://api-futures.kucoin.com"
        url = base_url + "/api/v1/market/candles"
        params = {"type": self.timeframe, "symbol": self.symbol.upper()}
        
        if start_time:
            params["startAt"] = int(start_time.timestamp())
        if end_time:
            params["endAt"] = int(end_time.timestamp())
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") != "200000":
            raise Exception(f"KuCoin API error: {data}")
        
        return data["data"]
    
    def _transform_candle_data(self, raw_data: list) -> pd.DataFrame:
        """
        Transform raw API data into a clean DataFrame.
        
        Args:
            raw_data: Raw candle data from API
            
        Returns:
            Processed DataFrame with OHLC data
        """
        df = pd.DataFrame(raw_data)
        df[['timestamp', 'open', 'close', 'high', 'low']] = df[[0, 1, 2, 3, 4]]
        df.drop(columns=[0, 1, 2, 3, 4, 5, 6], inplace=True)
        
        df['timestamp'] = pd.to_numeric(df['timestamp'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        df[['open', 'close', 'high', 'low']] = df[['open', 'close', 'high', 'low']].astype(float)
        
        self.df = df
        return df
    
    def _calculate_start_time_in_bars(self, bars: int) -> datetime.datetime:
        """
        Calculate the start time for fetching historical data based on bars.
        
        Args:
            bars: Number of bars to look back
            
        Returns:
            Start datetime
        """
        if self.timeframe.endswith('min'):
            delta = datetime.timedelta(minutes=int(self.timeframe[:-3]))
        elif self.timeframe.endswith('hour'):
            delta = datetime.timedelta(hours=int(self.timeframe[:-4]))
        elif self.timeframe.endswith('day'):
            delta = datetime.timedelta(days=int(self.timeframe[:-3]))
        else:
            raise ValueError("Unsupported timeframe")
        
        return datetime.datetime.now(datetime.timezone.utc) - (bars * delta)
    
    def calculate_indicators(self, atr_length_sl: int = 14, atr_length_vola: int = 20, 
                           ema_trend_length: int = 20, ema_is_bullish_length: int = 10):
        """
        Calculate technical indicators for the strategy.
        
        Args:
            atr_length_sl: ATR period for stop-loss calculation
            atr_length_vola: ATR period for volatility measurement
            ema_trend_length: EMA period for trend identification
            ema_is_bullish_length: EMA period for bullish confirmation
        """
        # Calculate ATR manually for compatibility with pandas 3.0
        # True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        high_low = self.df['high'] - self.df['low']
        high_close = np.abs(self.df['high'] - self.df['close'].shift())
        low_close = np.abs(self.df['low'] - self.df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.df['atr_sl'] = true_range.rolling(window=atr_length_sl).mean()
        self.df['atr_vola'] = true_range.rolling(window=atr_length_vola).mean()
        
        # Calculate EMAs using pandas ewm method
        self.df['ema_trend'] = self.df['close'].ewm(span=ema_trend_length, adjust=False).mean()
        self.df['ema_is_bullish'] = self.df['close'].ewm(span=ema_is_bullish_length, adjust=False).mean()
    
    def get_signal(self, lookback_high: int = 7, atr_vol_multiplier: float = 1.5):
        """
        Generate trading signals based on indicators.
        
        Args:
            lookback_high: Bars to look back for high calculation
            atr_vol_multiplier: Multiplier for volatility threshold
        """
        is_ready = (self.df['atr_sl'].notna() & 
                   self.df['atr_vola'].notna() & 
                   self.df['ema_trend'].notna())
        
        is_bullish = ((self.df['close'] > self.df['ema_trend']) & 
                     (self.df['close'] > self.df['ema_is_bullish']) & 
                     is_ready)
        
        rolling_high = self.df['high'].rolling(lookback_high).max()
        is_bearish_vola = (rolling_high - self.df['low']) > (self.df['atr_vola'] * atr_vol_multiplier)
        
        self.df['r_high'] = rolling_high
        self.df['is_bearish_vola'] = is_bearish_vola
        self.df['is_bullish'] = is_bullish
        
        self.df['signal'] = np.select(
            [is_bullish & ~is_bearish_vola, 
             is_bullish & (is_bearish_vola | (self.df['close'] < self.df['ema_trend']))],
            ['buy', 'caution'],
            default='no_signal'
        )
        self.df['signal'] = self.df['signal'].shift(1)
        
        # Initialize trade management columns
        self.df['in_trade'] = 0
        self.df['trail_sl'] = np.nan
        self.df['sl_hit'] = False
        self.df['update_tsl'] = False
        self.df['trail_source'] = self.df['low'].rolling(7).max()
    
    def set_in_trade(self, i: int):
        """
        Enter a new trade if buy signal is present.
        
        Args:
            i: Current bar index
        """
        if self.df['signal'].iloc[i] == 'buy' and self.df['in_trade'].iloc[i-1] == 0:
            self.df.loc[self.df.index[i], 'in_trade'] = 1
            self.df.loc[self.df.index[i], 'trail_sl'] = (
                self.df['trail_source'].iloc[i] - self.df['atr_sl'].iloc[i]
            )
    
    def update_trail_sl(self, i: int):
        """
        Update trailing stop-loss for active trades.
        
        Args:
            i: Current bar index
        """
        if self.df['in_trade'].iloc[i] == 1:
            # Copy previous stop-loss by default
            if pd.notna(self.df['trail_sl'].iloc[i-1]):
                self.df.loc[self.df.index[i], 'trail_sl'] = self.df['trail_sl'].iloc[i-1]
            
            # Calculate potential new stop-loss based on signal
            if self.df['signal'].iloc[i] == 'buy':
                new_sl = self.df['trail_source'].iloc[i] - self.df['atr_sl'].iloc[i]
            elif self.df['signal'].iloc[i] == 'caution':
                new_sl = self.df['trail_source'].iloc[i] - (self.df['atr_sl'].iloc[i] * 0.2)
            else:
                new_sl = self.df['trail_sl'].iloc[i]
            
            # Update only if new stop-loss is higher (trailing up)
            if pd.notna(new_sl) and pd.notna(self.df['trail_sl'].iloc[i]):
                self.df.loc[self.df.index[i], 'trail_sl'] = max(new_sl, self.df['trail_sl'].iloc[i])
    
    def check_sl(self, i: int):
        """
        Check if stop-loss was hit.
        
        Args:
            i: Current bar index
        """
        if (self.df['in_trade'].iloc[i-1] == 1 and 
            pd.notna(self.df['trail_sl'].iloc[i-1]) and 
            self.df['close'].iloc[i-1] < self.df['trail_sl'].iloc[i-1]):
            
            self.df.loc[self.df.index[i], 'in_trade'] = 0
            self.df.loc[self.df.index[i], 'trail_sl'] = np.nan
            self.df.loc[self.df.index[i], 'sl_hit'] = True
            
        elif self.df['in_trade'].iloc[i-1] == 1:
            self.df.loc[self.df.index[i], 'in_trade'] = 1
    
    def handle_signal(self, i: int):
        """
        Handle signal updates for active trades.
        
        Args:
            i: Current bar index
        """
        if self.df['signal'].iloc[i] == 'buy' and self.df['in_trade'].iloc[i-1] == 1:
            self.df.loc[self.df.index[i], 'in_trade'] = 1
            new_sl = self.df['trail_source'].iloc[i] - self.df['atr_sl'].iloc[i]
            
            if pd.notna(self.df['trail_sl'].iloc[i-1]):
                new_sl = max(new_sl, self.df['trail_sl'].iloc[i-1])
            self.df.loc[self.df.index[i], 'trail_sl'] = new_sl
            
        elif self.df['signal'].iloc[i] == 'caution' and self.df['in_trade'].iloc[i-1] == 1:
            self.df.loc[self.df.index[i], 'in_trade'] = 1
            new_sl = self.df['trail_source'].iloc[i] - (self.df['atr_sl'].iloc[i] * 0.2)
            
            if pd.notna(self.df['trail_sl'].iloc[i-1]):
                new_sl = max(new_sl, self.df['trail_sl'].iloc[i-1])
            self.df.loc[self.df.index[i], 'trail_sl'] = new_sl
    
    def wait_for_candle_completion(self) -> bool:
        """
        Wait until a candle for the current period timestamp is present.
        For daily bars, this means the new 00:00 UTC candle exists, so the
        previous day candle is finalized and safe to act on.
        """
        counter = 0
        logger.info(f"Waiting for {self.timeframe} candle completion for {self.symbol}...")
        
        while counter < 10:
            try:
                self.update_til_now(lookback_bars=LOOKBACK_BARS)
                now = datetime.datetime.now(datetime.timezone.utc)
                
                # Determine timeframe in minutes
                if self.timeframe.endswith('min'):
                    timeframe_minutes = int(self.timeframe[:-3])
                elif self.timeframe.endswith('hour'):
                    timeframe_minutes = int(self.timeframe[:-4]) * 60
                elif self.timeframe.endswith('day'):
                    timeframe_minutes = int(self.timeframe[:-3]) * 1440
                else:
                    raise ValueError("Unsupported timeframe")

                # Floor current UTC time to timeframe period via epoch math.
                timeframe_seconds = timeframe_minutes * 60
                current_period_epoch = int(now.timestamp()) // timeframe_seconds * timeframe_seconds
                current_period = datetime.datetime.fromtimestamp(current_period_epoch, tz=datetime.timezone.utc)
                
                last_candle_time = self.df.index[-1]
                
                if last_candle_time == current_period:
                    logger.info(f"Candle is complete. Proceeding with strategy... (Current: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}, Last Candle: {last_candle_time})")
                    return True
                else:
                    logger.info(f"Still waiting for candle... (Attempt {counter+1}/10) Current: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}, Last Candle: {last_candle_time}")
                    time.sleep(10)
                    
                counter += 1
                
            except Exception as e:
                logger.error(f"Error while checking candle completion: {e}")
                counter += 1
                time.sleep(10)

        logger.warning("Timed out waiting for current period candle. Skipping this run.")
        return False
    
    def log_account_status(self):
        """
        Log current account balances and market prices for visibility.
        """
        try:
            balance = self.exchange_client.exchange.fetch_balance()
            basecoin = self.symbol.split('-')[0]
            
            usdt_balance = balance['USDT']['free']
            coin_balance = balance[basecoin]['free']
            
            ticker = self.exchange_client.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            logger.info(f"USDT Total balance: {usdt_balance}")
            logger.info(f"{basecoin} balance: {coin_balance}")
            logger.info(f"Current price of {self.symbol}: {current_price}")
            
            # Log other asset status for position sizing context
            if basecoin == 'SOL':
                btc_balance = balance['BTC']['free']
                btc_market = self.exchange_client.exchange.market('BTC-USDT')
                min_btc = btc_market['limits']['amount']['min']
                if btc_balance <= min_btc:
                    logger.info('BTC is not in trade, will use 50% of balance if SOL trade entered')
                else:
                    logger.info('BTC is in trade, will use 100% of balance if SOL trade entered')
            elif basecoin == 'BTC':
                sol_balance = balance['SOL']['free']
                sol_market = self.exchange_client.exchange.market('SOL-USDT')
                min_sol = sol_market['limits']['amount']['min']
                if sol_balance <= min_sol:
                    logger.info('SOL is not in trade, will use 50% of balance if BTC trade entered')
                else:
                    logger.info('SOL is in trade, will use 100% of balance if BTC trade entered')
                    
        except Exception as e:
            logger.warning(f"Could not fetch account status: {e}")
    
    def execute_trades(self, testing: bool = False):
        """
        Execute trades based on current signals.
        
        Args:
            testing: If True, use minimum order sizes for testing
        """
        # Log recent signals
        logger.info(f"\n{self.df[['signal', 'open', 'close', 'trail_sl', 'sl_hit', 'in_trade']].tail(15)}")
        
        if self.df['sl_hit'].iloc[-1]:
            # Stop-loss hit - exit trade
            try:
                sell_amount = self.exchange_client.calculate_order_size_sell(self.symbol, 1.0)
                sell_order = self.exchange_client.create_market_sell_order(self.symbol, sell_amount)
                logger.info("Trade was stopped out.")
                logger.info(sell_order)
            except Exception as e:
                logger.error(f'Failed to sell: {e}')
                
        elif self.df['signal'].iloc[-1] == 'buy' and self.df['in_trade'].iloc[-2] == 0:
            # New buy signal - enter trade
            try:
                if testing:
                    buy_amount = self.exchange_client.get_minimum_order_amount(self.symbol)
                else:
                    buy_amount = self.exchange_client.calculate_order_size_buy(self.symbol)
                    
                buy_order = self.exchange_client.create_market_buy_order(self.symbol, buy_amount)
                logger.info("Trade was entered.")
                logger.info(buy_order)
            except Exception as e:
                logger.error(f'Failed to buy: {e}')
                
        elif self.df['in_trade'].iloc[-1] == 1:
            logger.info("Trade is still active. No action.")
        else:
            logger.info("No action.")
        
        logger.info('=========================================================================================\n')
