import pandas as pd
import numpy as np
import boto3
from datetime import datetime, timedelta
import os

# Configuration
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'mdaie-prml-spy-bucket')
S3_KEY = 'market-data/latest.parquet'

def create_dummy_data():
    print("Creating dummy SPY data...")
    
    # Create date range for last 3 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    
    # Create dummy price data
    np.random.seed(42)
    prices = 450 + np.cumsum(np.random.randn(len(dates)))
    
    # Create DataFrame with MultiIndex columns (Ticker, OHLCV)
    # Structure: Level 0 = Ticker, Level 1 = OHLCV
    
    # Create data for SPY
    data = {
        ('SPY', 'Open'): prices + np.random.randn(len(dates)),
        ('SPY', 'High'): prices + 2 + np.random.randn(len(dates)),
        ('SPY', 'Low'): prices - 2 + np.random.randn(len(dates)),
        ('SPY', 'Close'): prices,
        ('SPY', 'Volume'): np.random.randint(50000000, 100000000, len(dates))
    }
    
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    
    print(f"Created {len(df)} rows of dummy data")
    return df

def upload_to_s3(df):
    print(f"Uploading to s3://{BUCKET_NAME}/{S3_KEY}...")
    
    # Save to parquet buffer
    buffer = pd.DataFrame.to_parquet(df)
    
    # Upload
    s3 = boto3.client('s3')
    # Use BytesIO if to_parquet returns bytes (it doesn't, it writes to file or buffer)
    # Actually df.to_parquet() with no path returns bytes if engine='pyarrow'
    # But let's use a temporary file to be safe
    
    df.to_parquet('/tmp/dummy.parquet')
    
    s3.upload_file('/tmp/dummy.parquet', BUCKET_NAME, S3_KEY)
    print("Upload complete!")

if __name__ == "__main__":
    df = create_dummy_data()
    upload_to_s3(df)
