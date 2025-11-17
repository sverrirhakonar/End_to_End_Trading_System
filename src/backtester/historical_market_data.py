import yfinance as yf
from datetime import datetime

def get_and_save_historical_data(tickers, period='7d', interval='1m'):
    data = yf.download(tickers=tickers, period=period, interval=interval)
    newest_date = data.index[-1].strftime('%Y-%m-%d')
    filename = f"{tickers}-{period}-{interval}-{newest_date}.csv"
    data.to_csv(filename)
    print(f"Data saved to: {filename}")
    
    return data, filename


def main():
    # Example usage
    data, filename = get_and_save_historical_data(tickers='META', period='7d', interval='1m')
    print(f"\nData shape: {data.shape}")
    print(f"\nFirst few rows:")
    print(data.head())
    print(f"\nLast few rows:")
    print(data.tail())


if __name__ == '__main__':
    main()