import pandas as pd
from src.gateways.base_gateway import BaseDataGateway

class HistoricalDataGateway(BaseDataGateway):
    def __init__(self, csv_filepath: str):

        try:
            self.market_data = pd.read_csv(
                csv_filepath, 
                index_col='Datetime', 
                parse_dates=True
            ).sort_index()
            
            if self.market_data.empty:
                raise ValueError(f"No data found in {csv_filepath}")
            
            self._data_stream = self.market_data.iterrows()
            
            print(f"HistoricalDataGateway: Loaded {len(self.market_data)} historical bars.")
            
        except FileNotFoundError:
            print(f"Error: Data file not found at {csv_filepath}")
            print("Please run 'python src/data_handling/data_manager.py' first!")
            raise
        except Exception as e:
            print(f"Error loading historical data: {e}")
            raise

    def get_next_tick(self):
        """ Pulls the *next* row from the loaded CSV data. """
        try:
            tick_data = next(self._data_stream)
            return tick_data
        
        except StopIteration:
            print("HistoricalDataGateway: End of data stream.")
            return None
        except Exception as e:
            print(f"Error streaming next tick: {e}")
            return None