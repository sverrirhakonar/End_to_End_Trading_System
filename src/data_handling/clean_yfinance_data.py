import pandas as pd
import os

def clean_and_organize_yfinance_data(filename):
    # Load and clean the data
    current_dir = os.path.dirname(__file__)
    csv_path = os.path.join(current_dir, "..", "..", "data", filename)
    df = pd.read_csv(os.path.abspath(csv_path))
    print(df.head())
    df = df.rename(columns={"Price": "Datetime"})
    df = df.iloc[2:]
    df = df.rename(columns={"Price": "Datetime"})
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df.set_index('Datetime', inplace=True)
    df.sort_index(inplace=True)
    df.dropna(inplace=True)
    df.drop_duplicates(inplace=True)
    df = df.astype(float)

    # Add derived features
    df['Returns'] = df['Close'].pct_change()
    df['Price_Change'] = df['Close'].diff()
    
    df['MA_5'] = df['Close'].rolling(window=5, min_periods=1).mean()
    df['MA_10'] = df['Close'].rolling(window=10, min_periods=1).mean()
    df['MA_20'] = df['Close'].rolling(window=20, min_periods=1).mean()
    df['MA_50'] = df['Close'].rolling(window=50, min_periods=1).mean()
    df['MA_100'] = df['Close'].rolling(window=100, min_periods=1).mean()
    df['MA_200'] = df['Close'].rolling(window=200, min_periods=1).mean()

    df['Vol_5'] = df['Returns'].rolling(window=5, min_periods=1).std()
    df['Vol_10'] = df['Returns'].rolling(window=10,min_periods=1).std()
    df['Vol_20'] = df['Returns'].rolling(window=20,min_periods=1).std()
    df['Vol_50'] = df['Returns'].rolling(window=50,min_periods=1).std()
    df['Vol_100'] = df['Returns'].rolling(window=100,min_periods=1).std()
    df['Vol_200'] = df['Returns'].rolling(window=200,min_periods=1).std()
    df.dropna(inplace=True)

    return df

def save_cleaned_data(df, filename):
    current_dir = os.path.dirname(__file__)
    csv_path = os.path.join(current_dir, "..", "..", "data", filename)
    df.to_csv(os.path.abspath(csv_path))
    print(f"Data saved to CSV: {filename}")

def main():
    filename = 'META-7d-1m-2025-11-17.csv'
    df = clean_and_organize_yfinance_data(filename)
    print(df.head())
    save_cleaned_data(df, 'market_data.csv')


if __name__ == '__main__':
    main()