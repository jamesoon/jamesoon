#!/usr/bin/env python3
"""
Initial script to load historical market data into S3.
Run this once to populate S3 with historical data.
"""

import boto3
import pandas as pd
import yfinance as yf
from datetime import datetime
from io import BytesIO
import sys
import os

# Define TICKERS and download_price_data locally to avoid importing model.pkl
# This prevents numpy version conflicts when model.pkl was created with different numpy version

TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GLD",
    "OIL": "USO",
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",  # US Dollar Index on Yahoo
}


def download_price_data(tickers_dict, start_date="2015-01-01", end_date=None, auto_adjust=True, retries=3):
    """
    Download daily OHLCV data for all tickers using yfinance.
    Downloads tickers individually with retry logic for better reliability.
    """
    import time
    
    all_data = {}
    failed_tickers = []
    
    print(f"Downloading data for {len(tickers_dict)} tickers...")
    
    for name, ticker in tickers_dict.items():
        print(f"  Downloading {name} ({ticker})...", end=" ", flush=True)
        
        for attempt in range(retries):
            try:
                # Download individual ticker
                ticker_obj = yf.Ticker(ticker)
                
                # Handle different yfinance API versions
                # The API signature changed - try multiple approaches
                hist = None
                
                # Method 1: Try with auto_adjust (newer yfinance)
                try:
                    hist = ticker_obj.history(start=start_date, end=end_date, auto_adjust=auto_adjust)
                except TypeError:
                    # Method 2: Try without auto_adjust (some versions don't support it in history())
                    try:
                        hist = ticker_obj.history(start=start_date, end=end_date)
                    except TypeError:
                        # Method 3: Use period='max' and filter manually
                        try:
                            hist = ticker_obj.history(period='max')
                            if start_date:
                                hist = hist[hist.index >= pd.to_datetime(start_date)]
                            if end_date:
                                hist = hist[hist.index <= pd.to_datetime(end_date)]
                        except Exception:
                            # Method 4: Use yf.download() as fallback
                            temp_data = yf.download(
                                ticker, 
                                start=start_date, 
                                end=end_date, 
                                progress=False,
                                auto_adjust=auto_adjust if auto_adjust else False
                            )
                            if temp_data.empty:
                                raise ValueError("No data returned")
                            # Convert to single-level DataFrame if MultiIndex
                            if isinstance(temp_data.columns, pd.MultiIndex):
                                hist = temp_data
                            else:
                                hist = temp_data
                
                if hist is None or hist.empty:
                    raise ValueError("No data returned")
                
                if hist.empty:
                    print(f"⚠ No data")
                    failed_tickers.append((name, ticker, "No data returned"))
                    break
                
                # Store with MultiIndex format
                all_data[name] = hist
                print(f"✓ {len(hist)} rows")
                break
                
            except Exception as e:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                    print(f"⚠ Retry {attempt + 1}/{retries} in {wait_time}s...", end=" ", flush=True)
                    time.sleep(wait_time)
                else:
                    error_msg = str(e)[:50]  # Truncate long error messages
                    print(f"✗ Failed: {error_msg}")
                    failed_tickers.append((name, ticker, str(e)))
    
    if not all_data:
        raise ValueError(
            f"Failed to download data for any tickers. "
            f"Failed: {[name for name, _, _ in failed_tickers]}. "
            f"This might be due to Yahoo Finance API issues or network problems. "
            f"Try again later or check your internet connection."
        )
    
    if failed_tickers:
        print(f"\n⚠ Warning: {len(failed_tickers)} ticker(s) failed:")
        for name, ticker, error in failed_tickers:
            print(f"  - {name} ({ticker}): {error[:60]}")
    
    # Combine all tickers into MultiIndex DataFrame
    if len(all_data) == 1:
        # Single ticker case
        name = list(all_data.keys())[0]
        prices = pd.concat({name: all_data[name]}, axis=1)
    else:
        # Multiple tickers - align by date and combine
        prices = pd.concat(all_data, axis=1)
    
    # Sort columns for consistency
    prices = prices.sort_index(axis=1)
    
    return prices

# Configuration
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'your-market-data-bucket')
S3_KEY = 'market-data/latest.parquet'

s3 = boto3.client('s3')


def save_to_s3(df, bucket, key):
    """Save DataFrame to S3 as Parquet."""
    buffer = BytesIO()
    df.to_parquet(buffer, index=True, compression='snappy')
    buffer.seek(0)
    
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer.getvalue(),
        ContentType='application/parquet'
    )
    print(f"✓ Saved {len(df)} rows to s3://{bucket}/{key}")


def main():
    print("="*60)
    print("Initial S3 Data Load")
    print("="*60)
    print(f"Bucket: {BUCKET_NAME}")
    print(f"Key: {S3_KEY}")
    print(f"Start date: 2015-01-01")
    print(f"End date: Today")
    print()
    
    # Check if bucket exists
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"✓ Bucket exists: {BUCKET_NAME}")
    except:
        print(f"✗ Bucket does not exist: {BUCKET_NAME}")
        print(f"  Create it with: aws s3 mb s3://{BUCKET_NAME}")
        return
    
    # Download historical data
    print("\nDownloading historical market data...")
    print("This may take a few minutes...")
    
    try:
        raw_prices = download_price_data(
            TICKERS,
            start_date='2015-01-01',
            end_date=None,
            auto_adjust=True,
            retries=3
        )
        
        if raw_prices.empty or len(raw_prices) == 0:
            print(f"\n✗ Error: No data downloaded. Cannot proceed.")
            print(f"  This might be due to:")
            print(f"  1. Yahoo Finance API issues (try again in a few minutes)")
            print(f"  2. Network connectivity problems")
            print(f"  3. Rate limiting (wait 5-10 minutes and try again)")
            print(f"  4. Invalid ticker symbols")
            return 1
        
        print(f"\n✓ Downloaded {len(raw_prices)} rows")
        if len(raw_prices) > 0:
            print(f"  Date range: {raw_prices.index[0]} to {raw_prices.index[-1]}")
            print(f"  Columns: {len(raw_prices.columns)}")
        
        # Save to S3
        print(f"\nSaving to S3...")
        save_to_s3(raw_prices, BUCKET_NAME, S3_KEY)
        
        print("\n" + "="*60)
        print("✓ Initial data load complete!")
        print("="*60)
        print(f"\nNext steps:")
        print(f"1. Set up EventBridge schedule for daily updates")
        print(f"2. Deploy Lambda updater function")
        print(f"3. Update EKS service to use S3 data")
        
    except ValueError as e:
        # User-friendly error messages
        print(f"\n✗ Error: {str(e)}")
        print(f"\nTroubleshooting:")
        print(f"1. Check internet connection")
        print(f"2. Wait 5-10 minutes and try again (Yahoo Finance rate limiting)")
        print(f"3. Verify ticker symbols are correct")
        print(f"4. Try downloading fewer tickers at once")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())

