"""
Lambda function to update market data in S3 daily.
Triggered by EventBridge at market close (4:30 PM EST).
"""

import json
import os
import boto3
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
from io import BytesIO
import warnings

warnings.filterwarnings("ignore")

s3 = boto3.client('s3')

# Configuration
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'your-market-data-bucket')
S3_KEY_LATEST = 'market-data/latest.parquet'
S3_KEY_NORMALIZED = 'market_data_normalized.parquet'

TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GLD",
    "OIL": "USO",
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
}

# Mapping from Yahoo Symbol to Internal Name (for normalized file)
SYMBOL_TO_NAME = {v: k for k, v in TICKERS.items()}


def download_price_data(tickers_dict, start_date=None, end_date=None, period='5d'):
    """Download price data from Yahoo Finance."""
    yf_tickers = " ".join(tickers_dict.values())
    
    if start_date:
        data = yf.download(
            yf_tickers,
            start=start_date,
            end=end_date,
            auto_adjust=True,
            group_by="ticker",
            progress=False
        )
    else:
        # Use period for recent data
        data = yf.download(
            yf_tickers,
            period=period,
            auto_adjust=True,
            group_by="ticker",
            progress=False
        )
    
    # Ensure MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        return data.sort_index(axis=1)
    else:
        # If single ticker, yfinance might return single level
        # But we requested multiple tickers usually.
        # If only one ticker requested, handle it:
        symbol = list(tickers_dict.values())[0]
        return pd.concat({symbol: data}, axis=1).sort_index(axis=1)


def load_existing_data(bucket, key):
    """Load existing data from S3."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        df = pd.read_parquet(BytesIO(obj['Body'].read()))
        return df
    except s3.exceptions.NoSuchKey:
        print(f"No existing data found at s3://{bucket}/{key}")
        return None
    except Exception as e:
        print(f"Error loading existing data: {str(e)}")
        return None


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
    print(f"Saved {len(df)} rows to s3://{bucket}/{key}")


def create_normalized_dataset(df):
    """
    Convert the raw Yahoo Finance DataFrame (with Yahoo symbols)
    to the normalized format (with Internal Names) expected by the model training.
    """
    # 1. Copy to avoid modifying original
    norm_df = df.copy()
    
    # 2. Rename top-level columns (Yahoo Symbol -> Internal Name)
    # df.columns is MultiIndex (Ticker, Field)
    # We need to map the Ticker level
    new_columns = []
    for col in norm_df.columns:
        symbol = col[0]
        field = col[1]
        internal_name = SYMBOL_TO_NAME.get(symbol, symbol)
        new_columns.append((internal_name, field))
    
    norm_df.columns = pd.MultiIndex.from_tuples(new_columns)
    
    # 3. Ensure timezone-naive and date-only index
    if hasattr(norm_df.index, 'tz') and norm_df.index.tz is not None:
        norm_df.index = norm_df.index.tz_localize(None)
    
    norm_df.index = pd.DatetimeIndex(norm_df.index.date)
    
    # 4. Remove duplicates (keep last) and sort
    norm_df = norm_df[~norm_df.index.duplicated(keep='last')]
    norm_df = norm_df.sort_index()
    
    return norm_df


def lambda_handler(event, context):
    """
    Main Lambda handler.
    Downloads latest market data and updates S3.
    """
    try:
        print(f"Starting data update at {datetime.now().isoformat()}")
        
        # Download latest data (last 5 days to catch any missed days)
        print("Downloading latest market data...")
        new_data = download_price_data(TICKERS, period='5d')
        
        if new_data.empty:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No data downloaded'})
            }
        
        print(f"Downloaded {len(new_data)} rows")
        
        # Load existing data from S3 (latest.parquet)
        print(f"Loading existing data from s3://{BUCKET_NAME}/{S3_KEY_LATEST}...")
        existing_data = load_existing_data(BUCKET_NAME, S3_KEY_LATEST)
        
        if existing_data is not None:
            # Combine and deduplicate
            print(f"Existing data: {len(existing_data)} rows")
            combined = pd.concat([existing_data, new_data])
            
            # Remove duplicates (keep last occurrence)
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
            
            print(f"Combined data: {len(combined)} rows")
        else:
            # First run - download full history
            print("No existing data found. Downloading full history...")
            combined = download_price_data(
                TICKERS,
                start_date='2015-01-01',
                end_date=None
            )
            print(f"Full history: {len(combined)} rows")
        
        # Save 'latest.parquet' (Raw Yahoo Symbols)
        print(f"Saving to s3://{BUCKET_NAME}/{S3_KEY_LATEST}...")
        save_to_s3(combined, BUCKET_NAME, S3_KEY_LATEST)
        
        # Create and Save 'market_data_normalized.parquet' (Internal Names)
        print("Creating normalized dataset...")
        normalized_df = create_normalized_dataset(combined)
        
        print(f"Saving to s3://{BUCKET_NAME}/{S3_KEY_NORMALIZED}...")
        save_to_s3(normalized_df, BUCKET_NAME, S3_KEY_NORMALIZED)
        
        # Get date range
        date_range = {
            'start': str(combined.index[0]),
            'end': str(combined.index[-1]),
            'total_rows': len(combined)
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Data updated successfully (both files)',
                'date_range': date_range
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Failed to update data',
                'message': str(e)
            })
        }

