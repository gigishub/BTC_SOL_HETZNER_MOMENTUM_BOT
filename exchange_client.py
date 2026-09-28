"""
Exchange client for KuCoin operations.
Handles connection, balance retrieval, and order execution.
"""

import ccxt
import math
import logging
from decimal import Decimal
from config import API_KEY, API_SECRET, API_PASSPHRASE

logger = logging.getLogger(__name__)


class ExchangeClient:
    """Manages KuCoin exchange connection and operations."""
    
    def __init__(self):
        """Initialize KuCoin exchange connection."""
        self.exchange = ccxt.kucoin({
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "password": API_PASSPHRASE
        })
    
    def calculate_order_size_buy(self, symbol: str) -> float:
        """
        Calculate the order size for buying based on available USDT balance.
        Uses 50% of balance when the other asset is not in trade, 100% when it is.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USDT')
            
        Returns:
            Order size rounded down to exchange precision
        """
        balance = self.exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        logger.info(f'USDT Total balance: {usdt_balance}')

        basecoin = symbol.split('-')[0]
        basecoin_balance = Decimal(str(balance[basecoin]['free']))
        logger.info(f'{basecoin} balance: {basecoin_balance}')

        # Get market info for precision and pricing
        market = self.exchange.market(symbol)
        precision = market['precision']['amount']
        max_decimals = abs(Decimal(str(precision)).as_tuple().exponent)
        
        symbol_price = self.exchange.fetch_ticker(symbol)['last']
        logger.info(f'Current price of {symbol}: {symbol_price}')
        
        # Determine percentage of balance to use based on other asset's status
        percent_from_bal = self._get_balance_percentage(basecoin, balance)
        
        usdt_to_use = usdt_balance * percent_from_bal
        logger.info(f'USDT to use for {symbol}: {usdt_to_use}')
        
        # Calculate and round down order size
        order_size = usdt_to_use / symbol_price
        factor = 10 ** max_decimals
        rounded_order_size = math.floor(order_size * factor) / factor
        
        return rounded_order_size
    
    def _get_balance_percentage(self, basecoin: str, balance: dict) -> float:
        """
        Determine what percentage of USDT balance to use.
        Uses 50% if the other asset is not in trade, 100% if it is.
        
        Args:
            basecoin: The base coin (BTC or SOL)
            balance: Account balance dictionary
            
        Returns:
            Percentage of balance to use (0.5 or 1.0)
        """
        if basecoin == 'SOL':
            symbol_to_check = 'BTC-USDT'
            btc_market = self.exchange.market(symbol_to_check)
            min_order_size = Decimal(str(btc_market['limits']['amount']['min']))
            btc_balance = Decimal(str(balance['BTC']['free']))
            
            if btc_balance <= min_order_size:
                logger.info('BTC is not in trade, use 50% of balance to buy SOL if trade is entered')
                return 0.5
            else:
                logger.info('BTC is in trade, use 100% of balance to buy SOL if trade is entered')
                return 1.0
                
        elif basecoin == 'BTC':
            symbol_to_check = 'SOL-USDT'
            sol_market = self.exchange.market(symbol_to_check)
            min_order_size = Decimal(str(sol_market['limits']['amount']['min']))
            sol_balance = Decimal(str(balance['SOL']['free']))
            
            if sol_balance <= min_order_size:
                logger.info('SOL is not in trade, use 50% of balance to buy BTC if trade is entered')
                return 0.5
            else:
                logger.info('SOL is in trade, use 100% of balance to buy BTC if trade is entered')
                return 1.0
        
        return 0.5  # Default fallback
    
    def calculate_order_size_sell(self, symbol: str, percent_from_bal: float) -> float:
        """
        Calculate the order size for selling based on available coin balance.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USDT')
            percent_from_bal: Percentage of balance to sell (typically 1.0 for 100%)
            
        Returns:
            Order size rounded down to exchange precision
        """
        balance = self.exchange.fetch_balance()
        coin_balance = balance[symbol.split('-')[0]]['free']
        
        order_size = coin_balance * percent_from_bal
        
        # Get precision for rounding
        market = self.exchange.market(symbol)
        precision = market['precision']['amount']
        max_decimals = abs(Decimal(str(precision)).as_tuple().exponent)
        
        # Round down
        factor = 10 ** max_decimals
        rounded_order_size = math.floor(order_size * factor) / factor
        
        return rounded_order_size
    
    def create_market_buy_order(self, symbol: str, amount: float):
        """
        Execute a market buy order.
        
        Args:
            symbol: Trading pair symbol
            amount: Amount to buy
            
        Returns:
            Order response from exchange
        """
        return self.exchange.create_market_buy_order(symbol, amount)
    
    def create_market_sell_order(self, symbol: str, amount: float):
        """
        Execute a market sell order.
        
        Args:
            symbol: Trading pair symbol
            amount: Amount to sell
            
        Returns:
            Order response from exchange
        """
        return self.exchange.create_market_sell_order(symbol, amount)
    
    def get_minimum_order_amount(self, symbol: str) -> Decimal:
        """
        Get the minimum order amount for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Minimum order amount as Decimal
        """
        market = self.exchange.market(symbol)
        return Decimal(str(market['limits']['amount']['min']))
