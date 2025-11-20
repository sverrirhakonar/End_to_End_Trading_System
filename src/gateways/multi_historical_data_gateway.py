# src/gateways/multi_historical_data_gateway.py

import json
from typing import Dict, Tuple, Optional, Any

from src.gateways.base_gateway import BaseDataGateway
from src.gateways.historical_data_gateway import HistoricalDataGateway


class MultiHistoricalDataGateway(BaseDataGateway):
    """
    Streams one bar per ticker on each call.

    Assumes all CSV files use the same timestamps.
    """

    def __init__(self, config_path: str = "settings/market_data_config.json"):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            if not config:
                raise ValueError(
                    f"No tickers defined in {config_path}"
                )

            self._gateways: Dict[str, HistoricalDataGateway] = {}
            self._active_tickers = set()

            for entry in config:
                ticker = entry["ticker"]
                filepath = entry["filepath"]

                gateway = HistoricalDataGateway(filepath)
                self._gateways[ticker] = gateway
                self._active_tickers.add(ticker)

            print(
                f"MultiHistoricalDataGateway: Loaded "
                f"{len(self._gateways)} tickers from {config_path}"
            )

        except FileNotFoundError as e:
            print(
                f"Error: Config or data file not found: {e}"
            )
            raise
        except Exception as e:
            print(
                f"Error initializing MultiHistoricalDataGateway: {e}"
            )
            raise

    def get_next_tick(self) -> Optional[
        Dict[str, Tuple[Any, Any]]
    ]:
        """
        Returns:
          {
            "AAPL": (timestamp, row),
            "MSFT": (timestamp, row)
          }
        Or None if all streams ended.
        """
        if not self._active_tickers:
            print(
                "MultiHistoricalDataGateway: End of data stream."
            )
            return None

        ticks = {}
        finished = []

        for ticker in list(self._active_tickers):
            gateway = self._gateways[ticker]
            tick = gateway.get_next_tick()

            if tick is None:
                finished.append(ticker)
            else:
                ticks[ticker] = tick

        for ticker in finished:
            self._active_tickers.remove(ticker)

        if not ticks:
            print(
                "MultiHistoricalDataGateway: End of data stream."
            )
            return None

        return ticks

    def has_data(self) -> bool:
        return bool(self._active_tickers)
