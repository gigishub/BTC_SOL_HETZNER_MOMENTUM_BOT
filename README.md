# Trading Bot - Refactored Structure

## Overview
This trading bot implements a trend-following strategy for BTC and SOL trading pairs on KuCoin exchange.

## Setup



### 2. Install Dependencies
```bash
cd /root/projects/trading_bot
pip install -r requirements.txt
```

### 3. Configure API Credentials
Copy the `.env.example` file to `.env` and add your KuCoin API credentials:
```bash
cp .env.example .env
# Edit .env with your actual API credentials
```

Your `.env` file should look like:
```
KUCOIN_API_KEY=your_api_key_here
KUCOIN_API_SECRET=your_api_secret_here
KUCOIN_API_PASSPHRASE=your_api_passphrase_here
```

**IMPORTANT**: Never commit `.env` to version control!

## Project Structure

```
trading_bot/
├── config.py              # Configuration and strategy parameters
├── exchange_client.py     # KuCoin exchange operations
├── strategy.py            # Core trading strategy logic
├── trade_BTC_SOL.py      # Trade execution functions
├── trading_main.py        # Main orchestration script
└── requirements.txt       # Python dependencies
```

## File Descriptions

### config.py
- Loads API credentials from `.env` file (secure)
- Strategy parameters for BTC and SOL
- General settings like lookback bars
- Validates credentials on import

### exchange_client.py
- `ExchangeClient` class handles all exchange operations:
  - Connection to KuCoin
  - Order size calculations
  - Buy/sell order execution
  - Balance management

### strategy.py
- `TradingStrategy` class implements the core logic:
  - Fetching historical candle data
  - Calculating technical indicators (ATR, EMA)
  - Generating buy/caution/no_signal states
  - Managing trailing stop-losses
  - Trade execution logic

### trade_BTC_SOL.py
- `trade_BTC()` - Execute BTC trading strategy
- `trade_SOL()` - Execute SOL trading strategy
Clean, simple functions that use the strategy class

### trading_main.py
- Main entry point
- Runs both trading functions in a loop
- Configurable runtime and testing mode

## Usage

### Running the bot:
```bash
cd /root/projects/trading_bot
source /root/trading_venv/bin/activate
python trading_main.py
```

### Configuration:
Edit `config.py` to adjust strategy parameters (ATR lengths, EMA periods, etc.) or directly modify:
- `.env` for API credentials (secure, not tracked in git)
- `config.py` for strategy parameters (BTC_CONFIG, SOL_CONFIG)

### Testing mode:
```python
# In trading_main.py
main(runtime=5, testing=True)  # Uses minimum order sizes
```

## Strategy Logic

1. **Trend Detection**: Uses EMAs to identify bullish trends
2. **Volatility Filter**: Checks if volatility is too high (bearish signal)
3. **Signal Generation**: 
   - `buy`: Bullish trend, low volatility
   - `caution`: Bullish but high volatility - tighter stop-loss
   - `no_signal`: No trade conditions met
4. **Trade Management**:
   - Enters position on buy signal
   - Trails stop-loss higher as price moves up
   - Exits when stop-loss is hit

## Safety Features

- Waits for candle completion before trading
- Uses trailing stop-losses
- Dynamic position sizing based on other asset status
- Comprehensive error logging

## Testing

Run the test suite to verify your setup:
```bash
cd /root/projects/trading_bot
source /root/trading_venv/bin/activate
python test_bot.py
```

This will test:
- All required imports
- Configuration and .env loading
- Exchange client initialization
- Strategy class functionality
- Trade function imports

## Installed Packages

The bot uses the following Python packages (Python 3.12 compatible):
- pandas >= 2.1.0
- pandas-ta >= 0.3.14b0
- numpy >= 1.26.0
- ccxt >= 4.1.0
- requests >= 2.31.0
- python-dotenv >= 1.0.0
