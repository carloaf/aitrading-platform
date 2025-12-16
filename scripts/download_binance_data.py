#!/usr/bin/env python3
"""
Download historical klines data from Binance public data repository.
This uses the public data files which are much faster than API calls.

Usage:
    python download_binance_data.py --symbol BTCUSDT --interval 1h --start 2021-01-01 --end 2024-12-31
"""

import os
import sys
import argparse
import requests
import zipfile
import io
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import time

# Binance public data URL
BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"

def download_month(symbol: str, interval: str, year: int, month: int, output_dir: Path) -> pd.DataFrame:
    """Download one month of klines data from Binance public repository."""
    
    month_str = f"{year}-{month:02d}"
    filename = f"{symbol}-{interval}-{month_str}.zip"
    url = f"{BASE_URL}/{symbol}/{interval}/{filename}"
    
    csv_file = output_dir / f"{symbol}-{interval}-{month_str}.csv"
    
    # Check if already downloaded
    if csv_file.exists():
        print(f"  📁 {month_str}: Already exists, loading from cache...")
        return pd.read_csv(csv_file)
    
    print(f"  ⬇️  {month_str}: Downloading...", end=" ", flush=True)
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 404:
            print("⚠️  Not available yet")
            return pd.DataFrame()
        
        response.raise_for_status()
        
        # Extract ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                df = pd.read_csv(f, header=None)
        
        # Save to cache
        df.to_csv(csv_file, index=False)
        
        print(f"✅ {len(df)} candles")
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return pd.DataFrame()

def process_klines(df: pd.DataFrame) -> pd.DataFrame:
    """Process raw Binance klines data into standard OHLCV format."""
    
    if df.empty:
        return df
    
    # Binance klines columns:
    # 0: Open time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume
    # 6: Close time, 7: Quote asset volume, 8: Number of trades
    # 9: Taker buy base volume, 10: Taker buy quote volume, 11: Ignore
    
    columns = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
               'close_time', 'quote_volume', 'trades', 'taker_buy_base',
               'taker_buy_quote', 'ignore']
    
    if len(df.columns) >= len(columns):
        df.columns = columns[:len(df.columns)]
    else:
        df.columns = columns[:len(df.columns)]
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Set timestamp as index
    df.set_index('timestamp', inplace=True)
    
    # Keep only OHLCV
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    
    # Convert to float
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

def download_historical_data(symbol: str, interval: str, start_date: str, end_date: str, output_dir: str = "data/historical"):
    """Download historical data for a date range."""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    print(f"\n{'='*60}")
    print(f"📊 BINANCE HISTORICAL DATA DOWNLOADER")
    print(f"{'='*60}")
    print(f"Symbol: {symbol}")
    print(f"Interval: {interval}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Output: {output_path}")
    print(f"{'='*60}\n")
    
    all_data = []
    
    # Iterate through months
    current = start.replace(day=1)
    total_months = 0
    
    while current <= end:
        total_months += 1
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    current = start.replace(day=1)
    month_count = 0
    
    while current <= end:
        month_count += 1
        print(f"[{month_count}/{total_months}]", end=" ")
        
        df = download_month(symbol, interval, current.year, current.month, output_path)
        
        if not df.empty:
            processed = process_klines(df)
            if not processed.empty:
                all_data.append(processed)
        
        # Rate limiting (be nice to Binance servers)
        time.sleep(0.1)
        
        # Next month
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    if not all_data:
        print("\n❌ No data downloaded!")
        return None
    
    # Combine all data
    print(f"\n📦 Combining {len(all_data)} months of data...")
    combined = pd.concat(all_data, axis=0)
    combined = combined[~combined.index.duplicated(keep='first')]
    combined = combined.sort_index()
    
    # Filter to exact date range
    combined = combined[(combined.index >= start) & (combined.index <= end + timedelta(days=1))]
    
    # Save combined file
    combined_file = output_path / f"{symbol}_{interval}_{start_date}_to_{end_date}.csv"
    combined.to_csv(combined_file)
    
    print(f"\n{'='*60}")
    print(f"✅ DOWNLOAD COMPLETE!")
    print(f"{'='*60}")
    print(f"Total candles: {len(combined):,}")
    print(f"Date range: {combined.index.min()} to {combined.index.max()}")
    print(f"File saved: {combined_file}")
    print(f"File size: {combined_file.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"{'='*60}\n")
    
    return combined

def main():
    parser = argparse.ArgumentParser(description="Download Binance historical klines data")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair (default: BTCUSDT)")
    parser.add_argument("--interval", default="1h", help="Kline interval (default: 1h)")
    parser.add_argument("--start", default="2021-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default="data/historical", help="Output directory")
    
    args = parser.parse_args()
    
    download_historical_data(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start,
        end_date=args.end,
        output_dir=args.output
    )

if __name__ == "__main__":
    main()
