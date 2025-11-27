#!/usr/bin/env python
"""
Script to download, normalize, and upload market data to S3.
This ensures consistent date formatting (timezone-naive, date-only, no duplicates).
"""

import boto3
import pandas as pd
import yfinance as yf
from datetime import datetime
from io import BytesIO
import sys
import os

# Configuration
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'mdaie-prml-spy-bucket')
S3_KEY = 'market_data_normalized.parquet'

TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GOLD",   # Using GOLD as the key name to match S3 data
    "OIL": "OIL",     # Using OIL as the key name to match S3 data
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "VIX",     # Using VIX without ^ for consistency
    "DXY": "DXY",     # Using DXY as the key name
}

# Mapping for yfinance downloads (what yfinance expects)
YFINANCE_MAPPING = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GLD",     # yfinance uses GLD
    "OIL": "USO",      # yfinance uses USO
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "^VIX",     # yfinance uses ^VIX
    "DXY": "DX-Y.NYB", # yfinance uses this symbol
}


def normalize_dataframe(df):
    """
    Normalize DataFrame to ensure:
    1. Timezone-naive DatetimeIndex
    2. Date-only index (no time component)
    3. No duplicate dates
    4. Sorted by date
    """
    # Convert index to timezone-naive if needed
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # Convert to date-only (remove time component)
    df.index = pd.DatetimeIndex(df.index.date)
    
    # Remove duplicates (keep last occurrence for each date)
    df = df[~df.index.duplicated(keep='last')]
    
    # Sort by date
    df = df.sort_index()
    
    return df


def download_and_normalize_ticker(ticker_name, yf_symbol, start_date='2015-01-01'):
    """Download and normalize data for a single ticker."""
    print(f"  Downloading {ticker_name} ({yf_symbol})...", end=" ", flush=True)
    
    try:
        # Download data
        data = yf.download(yf_symbol, start=start_date, progress=False, auto_adjust=True)
        
        if data.empty:
            print(f"⚠ No data")
            return None
        
        # Normalize the index
        data = normalize_dataframe(data)
        
        print(f"✓ {len(data)} rows")
        return data
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return None


def create_multiindex_dataframe(ticker_data_dict):
    """
    Create a MultiIndex DataFrame from individual ticker DataFrames.
    Format: (Ticker, Field) where Field is Open, High, Low, Close, Volume
    """
    if not ticker_data_dict:
        raise ValueError("No ticker data provided")
    
    # Get all unique dates across all tickers
    all_dates = pd.DatetimeIndex([])
    for df in ticker_data_dict.values():
        if df is not None:
            all_dates = all_dates.union(df.index)
    
    # Remove duplicates and sort
    all_dates = all_dates.unique().sort_values()
    
    # Create MultiIndex DataFrame
    multi_index_cols = []
    for ticker_name in sorted(ticker_data_dict.keys()):
        df = ticker_data_dict[ticker_name]
        if df is not None:
            for field in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if field in df.columns:
                    multi_index_cols.append((ticker_name, field))
    
    # Create empty DataFrame with MultiIndex columns
    result = pd.DataFrame(index=all_dates, columns=pd.MultiIndex.from_tuples(multi_index_cols))
    
    # Fill in data for each ticker
    for ticker_name, df in ticker_data_dict.items():
        if df is not None:
            for field in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if field in df.columns:
                    # Align data to common index
                    result[(ticker_name, field)] = df[field].reindex(all_dates)
    
    return result


def upload_to_s3(df, bucket, key):
    """Upload DataFrame to S3 as Parquet."""
    print(f"\nUploading to s3://{bucket}/{key}...")
    
    try:
        # Convert to Parquet
        buffer = BytesIO()
        df.to_parquet(buffer, engine='pyarrow', compression='snappy')
        buffer.seek(0)
        
        # Upload to S3
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=buffer.getvalue(),
            ContentType='application/octet-stream'
        )
        
        print(f"✓ Successfully uploaded {len(df)} rows to S3")
        print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  - Columns: {len(df.columns)}")
        print(f"  - File size: {len(buffer.getvalue()) / 1024 / 1024:.2f} MB")
        
    except Exception as e:
        print(f"✗ Error uploading to S3: {str(e)}")
        raise


def main():
    print("="*60)
    print("Market Data Normalization and S3 Upload")
    print("="*60)
    print(f"\nTarget: s3://{S3_BUCKET}/{S3_KEY}")
    print(f"Tickers: {', '.join(TICKERS.keys())}")
    print()
    
    # Download data for all tickers
    ticker_data = {}
    for ticker_name, yf_symbol in YFINANCE_MAPPING.items():
        data = download_and_normalize_ticker(ticker_name, yf_symbol)
        if data is not None:
            ticker_data[ticker_name] = data
    
    if not ticker_data:
        print("\n✗ No data downloaded. Exiting.")
        sys.exit(1)
    
    print(f"\n✓ Successfully downloaded {len(ticker_data)}/{len(TICKERS)} tickers")
    
    # Create MultiIndex DataFrame
    print("\nCreating MultiIndex DataFrame...")
    combined_df = create_multiindex_dataframe(ticker_data)
    
    print(f"✓ Created DataFrame:")
    print(f"  - Shape: {combined_df.shape}")
    print(f"  - Date range: {combined_df.index[0]} to {combined_df.index[-1]}")
    print(f"  - Index type: {type(combined_df.index)}")
    print(f"  - Has timezone: {combined_df.index.tz is not None}")
    print(f"  - Has duplicates: {combined_df.index.duplicated().any()}")
    print(f"  - Tickers: {sorted(set(combined_df.columns.get_level_values(0)))}")
    
    # Save locally first for testing
    local_path = 'ml_source/market_data_normalized.parquet'
    print(f"\nSaving to local file: {local_path}...")
    combined_df.to_parquet(local_path, engine='pyarrow', compression='snappy')
    print(f"✓ Saved locally")
    
    # Upload to S3 (if bucket exists)
    try:
        upload_to_s3(combined_df, S3_BUCKET, S3_KEY)
    except Exception as e:
        print(f"\n⚠ S3 upload failed (bucket may not exist): {str(e)}")
        print(f"  Data is available locally at: {local_path}")
    
    print("\n" + "="*60)
    print("✓ Data normalization complete!")
    print(f"  Local file: {local_path}")
    print("="*60)


if __name__ == "__main__":
    main()

