"""
download_benchmarks.py — Download historical daily data for QQQ and SPY from Yahoo Finance.
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "daily"

def download_benchmark(ticker: str, filename: str, days: int = 1825):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    print(f"Downloading {ticker} from Yahoo Finance...")
    try:
        df = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
        if df.empty:
            print(f"Error: No data returned for {ticker}")
            return
            
        # Reset index to get Date column
        df = df.reset_index()
        
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
            
        # Rename columns to lowercase
        df.columns = [col.lower() for col in df.columns]
        
        # yfinance returns 'adj close' and 'close'. We want to use 'adj close' as the 'close' price
        # because it includes dividends/splits, which is proper for equity curves.
        if "adj close" in df.columns:
            df = df.rename(columns={"adj close": "close"})
            
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        
        # Ensure directories exist
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        filepath = DATA_DIR / f"{filename}.csv"
        df.to_csv(filepath, index=False)
        print(f"Successfully saved {ticker} data to {filepath}")
    except Exception as e:
        print(f"Failed to download {ticker}: {e}")

def main():
    # Download 5 years of SPY and QQQ
    download_benchmark("SPY", "SPY", days=1825)
    download_benchmark("QQQ", "QQQ", days=1825)

if __name__ == "__main__":
    main()
