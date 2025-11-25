# End-to-End Trading System

A professional-grade algorithmic trading system built for backtesting and live trading with Alpaca Markets. Features modular architecture, multiple trading strategies, risk management, and comprehensive portfolio tracking.

## Features

- **Backtesting Engine**: Simulate trading strategies on historical data with realistic order execution
- **Multiple Strategies**: Pre-built momentum, mean reversion, RSI, Bollinger Bands, MACD, and more
- **Signal Aggregation**: Combine multiple strategies with weighted voting system
- **Risk Management**: Position limits, capital checks, order rate limiting
- **Portfolio Management**: Track positions, P&L, average prices, and portfolio value
- **Price Manager**: Calculate technical indicators (SMA, EMA, RSI, ATR, Bollinger Bands, MACD)
- **Order Simulation**: Realistic fill simulation with partial fills and rejections
- **Alpaca Integration**: Fetch historical data and ready for live trading
- **Extensive Logging**: Track all orders, signals, and execution events


1. **Clone the repository**:
```bash
git clone https://github.com/sverrirhakonar/End_to_End_Trading_System.git
cd End_to_End_Trading_System
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

Required packages:
- `alpaca-py` - Alpaca Markets API
- `pandas` - Data manipulation
- `numpy` - Numerical computing
- `yfinance` - Alternative market data source

## Quick Start

### 1. Fetch Market Data from Alpaca

```bash
python src/data_handling/alpaca_data_loader.py
```

This downloads 20 days of 1-minute bars for META and saves to `data/META-alpaca-YYYY-MM-DD.csv`.

**Note**: Update API keys in `alpaca_data_loader.py` with your Alpaca credentials.

### 2. Run a Backtest

```bash
python run_backtest.py
```

This will:
- Load historical data from CSV
- Run configured strategies
- Simulate order execution
- Generate performance metrics and charts
- Save logs to `logs/` directory

### 3. Multi-Symbol Demo

```bash
python multi_symbol_demo.py
```

Demonstrates multi-ticker data streaming from the gateway.

### 4. Run a sensitivity report on your backtest

```bash
python run_sensitivity_report_backtester.py
```

Runs many backtests in parallel to generate what-if analysis tables.
It varies execution settings, strategy weights, and strategy parameters, runs each configuration as a separate job, and collects the Sharpe ratios into structured sensitivity tables.
All results are printed.
## Configuration

Configuration files are in `src/settings/`:

- **`market_data_config.json`**: Data file paths per symbol
- **`strategy_config.json`**: Strategy selection and parameters
- **`execution_settings.json`**: Position sizing and risk limits
- **`initial_positions.json`**: Starting cash and positions

### Example Strategy Configuration

```json
{
  "META": [
    {
      "class": "MomentumStrategy",
      "weight": 1.0,
      "params": {"period": 20, "threshold": 0.02}
    },
    {
      "class": "RsiReversionStrategy",
      "weight": 0.8,
      "params": {"period": 14, "oversold": 30, "overbought": 70}
    }
  ]
}
```

## Available Strategies

- **MomentumStrategy**: Rate of change momentum
- **MovingAverageCrossoverStrategy**: Fast/slow SMA crossover
- **MeanReversionStrategy**: Price deviation from SMA
- **BollingerReversionStrategy**: Bollinger Band touches
- **DonchianBreakoutStrategy**: Channel breakouts
- **AtrBreakoutStrategy**: ATR-based volatility breakouts
- **RsiReversionStrategy**: RSI overbought/oversold
- **TrendRsiConfirmationStrategy**: Trend + RSI confirmation
- **MacdTrendStrategy**: MACD crossovers
- **RegimeSwitchingStrategy**: Adaptive strategy based on volatility

## Architecture

### Signal Flow

```
DataGateway → PriceManager → [Strategies] → Signals → SignalBundle
    ↓
ExecutionManager → Orders → OrderManager (validate) → MatchingEngine
    ↓
Fills → PositionManager (update P&L)
```

### Key Components

- **PriceManager**: Maintains price history, calculates indicators
- **Strategies**: Generate buy/sell signals based on indicators
- **SignalBundle**: Aggregates signals from multiple strategies
- **ExecutionManager**: Determines position sizes and generates orders
- **OrderManager**: Validates orders against risk limits
- **SimulatedMatchingEngine**: Simulates realistic order fills
- **PositionManager**: Tracks positions, cash, and P&L

## Live Trading (Coming Soon)

The system is designed for easy transition to live trading:
- Replace `HistoricalDataGateway` with `AlpacaDataGateway` (websocket)
- Replace `SimulatedMatchingEngine` with `AlpacaBrokerGateway` (REST API)
- All strategy and risk management code remains unchanged

## Logs

Logs are saved to `logs/` directory:
- **Order logs**: All order events (submitted, filled, rejected)
- **Signal logs**: Strategy signals with timestamps
- CSV format for easy analysis

## Development

### Adding a New Strategy

1. Create a class inheriting from `Strategy` in `strategies.py`
2. Implement `generate_signals()` method
3. Add to `strategy_config.json`

Example:
```python
class MyStrategy(Strategy):
    def __init__(self, price_manager, symbol, my_param=10):
        self.pm = price_manager
        self.symbol = symbol
        self.my_param = my_param
    
    def generate_signals(self, tick) -> List[Signal]:
        price = self.pm.get_latest_price(self.symbol)
        # Your logic here
        if condition:
            return [Signal(self.symbol, "BUY", 1.0, self.__class__.__name__)]
        return []
```

### References

The development of this project was supported primarily by:

- Course lecture slides and class materials  
- GPT-5.1 for coding assistance and explanation  
- Claude Sonnet 4.5 for coding assistance and explanation  


