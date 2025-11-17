import yfinance as yf
from datetime import datetime
import os
def get_and_save_historical_data(tickers, period='7d', interval='1m'):
    data = yf.download(tickers=tickers, period=period, interval=interval)
    newest_date = data.index[-1].strftime('%Y-%m-%d')
    filename = f"{tickers}-{period}-{interval}-{newest_date}.csv"
    data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", filename)
    data.to_csv(os.path.abspath(data_path))
    print(f"Data saved to CSV: {filename}")
    return data


def main():
    get_and_save_historical_data(tickers='META', period='7d', interval='1m')


if __name__ == '__main__':
    main()