import pandas as pd
from src.gateways.base_gateway import BaseDataGateway

# (A) We "inherit" from BaseDataGateway, promising to follow its "contract".
class HistoricalDataGateway(BaseDataGateway):

    def __init__(self, csv_filepath: str):

        try:
            # (B) Load the *entire* cleaned data file into memory.
            self.market_data = pd.read_csv(
                csv_filepath, 
                index_col='Datetime', 
                parse_dates=True
            ).sort_index()
            
            if self.market_data.empty:
                raise ValueError(f"No data found in {csv_filepath}")
            
            # (C) This is the "magic" for incremental feeding:
            # We create an "iterator" that can be called
            # one row at a time. This is like cueing up the movie.
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
        """
        Pulls the *next* row from the loaded CSV data.
        
        This is the "play next frame" button.
        
        It fulfills the "contract" from BaseDataGateway.
        
        Returns:
            - A pandas Series with the row's OHLCV data.
            - None when the file has no more rows.
        """
        # (D) This is the standard way to use an iterator in Python.
        try:
            # (E) Ask the iterator for the next item.
            timestamp, tick_data = next(self._data_stream)
            
            # (F) Return the row data (a pandas Series) to the strategy.
            return tick_data
        
        # (G) This "error" is just Python's way of saying
        # the iterator is empty (the "movie is over").
        except StopIteration:
            # The data stream is finished.
            print("HistoricalDataGateway: End of data stream.")
            return None
        except Exception as e:
            print(f"Error streaming next tick: {e}")
            return None