from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from alpaca.trading.client import TradingClient
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.historical.corporate_actions import CorporateActionsClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.trading.stream import TradingStream
from alpaca.data.live.stock import StockDataStream

from alpaca.data.requests import (
    CorporateActionsRequest,
    StockBarsRequest,
    StockQuotesRequest,
    StockTradesRequest,
)
from alpaca.trading.requests import (
    ClosePositionRequest,
    GetAssetsRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopLossRequest,
    StopOrderRequest,
    TakeProfitRequest,
    TrailingStopOrderRequest,
)
from alpaca.trading.enums import (
    AssetExchange,
    AssetStatus,
    OrderClass,
    OrderSide,
    OrderType,
    QueryOrderStatus,
    TimeInForce,
)
api_key = 'PKJGBG7SFXOF52CAFA2W2B467V'
secret_key = 'FV98XpJC8mcBXAFbzvrASLef8r1R9m5b4QP7h4HFTe92'
data_api_url = "https://data.alpaca.markets/v2"

stock_historical_data_client = StockHistoricalDataClient(
    api_key,
    secret_key
)
symbol = 'META'



now = datetime.now(ZoneInfo("America/Chicago"))
req = StockBarsRequest(
    symbol_or_symbols = [symbol],
    timeframe=TimeFrame(amount = 1, unit = TimeFrameUnit.Minute), # specify timeframe
    start = now - timedelta(days = 20),                          # specify start datetime, default=the beginning of the current day.
    # end_date=None,                                        # specify end datetime, default=now
    limit = None,                                               # specify limit
)

bars = stock_historical_data_client.get_stock_bars(req).df

bars.rename(columns={"close": "Close", "open": "Open", "high": "High", "low": "Low", "volume": "Volume"}, inplace=True)

bars = bars.rename_axis(index={"timestamp": "Datetime"})


newest_date = bars.index.get_level_values("Datetime")[-1].strftime("%Y-%m-%d")
filename = f"{symbol}-alpaca-{newest_date}.csv"

data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", filename)
print("Saving CSV to: ", data_path)
bars.to_csv(os.path.abspath(data_path))

print(f"Saved CSV to: {data_path}")



# get historical trades by symbol
# req = StockTradesRequest(
#     symbol_or_symbols = [symbol],
#     start = now - timedelta(days = 1),                          # specify start datetime, default=the beginning of the current day.
#     # end=None,                                             # specify end datetime, default=now
#     limit = 2,                                                # specify limit
# )
# trades = stock_historical_data_client.get_stock_trades(req).df
# print(trades)

