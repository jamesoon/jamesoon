import json
import os
import boto3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta

# Try to use awswrangler (from AWS Data Wrangler layer) or fallback to pyarrow
try:
    import awswrangler as wr
    USE_AWSWRANGLER = True
except ImportError:
    try:
        import pyarrow.parquet as pq
        USE_AWSWRANGLER = False
    except ImportError:
        raise ImportError("Neither awswrangler nor pyarrow available")

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Lambda function to fetch SPY price data from S3
    Returns current price, historical data, and key metrics
    """
    
    # Get bucket and file info from environment or defaults
    bucket_name = os.environ.get('S3_BUCKET_NAME', 'mdaie-prml-spy-bucket')
    file_key = os.environ.get('S3_FILE_KEY', 'market_data_normalized.parquet')
    
    try:
        # Handle CORS preflight
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'CORS preflight'})
            }
        
        # Download parquet file from S3
        print(f"Fetching data from s3://{bucket_name}/{file_key}")
        
        if USE_AWSWRANGLER:
            # Use awswrangler (from AWS Data Wrangler layer)
            print("Using awswrangler to read parquet")
            df = wr.s3.read_parquet(path=f"s3://{bucket_name}/{file_key}")
        else:
            # Fallback to pyarrow
            print("Using pyarrow to read parquet")
            response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
            parquet_data = response['Body'].read()
            parquet_file = pq.read_table(BytesIO(parquet_data))
            df = parquet_file.to_pandas()
        
        print(f"Data shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Index: {df.index}")
        
        # Extract SPY data
        spy_data = extract_spy_data(df)
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(spy_data, default=str)
        }
        
    except s3_client.exceptions.NoSuchBucket:
        return error_response(404, f'Bucket {bucket_name} not found')
    except s3_client.exceptions.NoSuchKey:
        return error_response(404, f'File {file_key} not found in bucket {bucket_name}')
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f'Error processing data: {str(e)}')


def extract_spy_data(df):
    """
    Extract SPY price data and calculate metrics
    """
    # Handle MultiIndex columns (ticker, OHLCV)
    if isinstance(df.columns, pd.MultiIndex):
        # Try to get SPY data from MultiIndex
        if 'SPY' in df.columns.get_level_values(0):
            spy_df = df['SPY'].copy()
        else:
            raise ValueError("SPY data not found in MultiIndex columns")
    else:
        # Flat columns - assume it's already SPY data or similar structure
        spy_df = df.copy()
    
    # Ensure index is datetime
    if not isinstance(spy_df.index, pd.DatetimeIndex):
        spy_df.index = pd.to_datetime(spy_df.index)
    
    # Sort by date
    spy_df = spy_df.sort_index()
    
    # Get latest data (most recent trading day)
    latest_date = spy_df.index[-1]
    latest_data = spy_df.iloc[-1]
    
    # Get previous day data
    if len(spy_df) > 1:
        prev_data = spy_df.iloc[-2]
        previous_close = float(prev_data['Close']) if 'Close' in prev_data else float(prev_data.get('close', 0))
    else:
        previous_close = float(latest_data.get('Open', latest_data.get('open', 0)))
    
    # Current price (latest close)
    current_price = float(latest_data.get('Close', latest_data.get('close', 0)))
    
    # Calculate change
    change = current_price - previous_close
    change_percent = (change / previous_close * 100) if previous_close > 0 else 0
    
    # Helper to safely get float
    def get_float(val, default=0.0):
        try:
            return float(val) if pd.notna(val) else default
        except:
            return default

    # Helper to safely get int
    def get_int(val, default=0):
        try:
            return int(val) if pd.notna(val) else default
        except:
            return default

    # Get OHLCV data
    open_price = get_float(latest_data.get('Open', latest_data.get('open', current_price)))
    high_price = get_float(latest_data.get('High', latest_data.get('high', current_price)))
    low_price = get_float(latest_data.get('Low', latest_data.get('low', current_price)))
    volume = get_int(latest_data.get('Volume', latest_data.get('volume', 0)))
    
    # Calculate 52-week high/low (using last 252 trading days)
    lookback_days = min(252, len(spy_df))
    recent_data = spy_df.tail(lookback_days)
    
    week_52_high = get_float(recent_data['High'].max() if 'High' in recent_data else recent_data.get('high', current_price).max())
    week_52_low = get_float(recent_data['Low'].min() if 'Low' in recent_data else recent_data.get('low', current_price).min())
    
    # Average volume (last 20 days)
    avg_volume = get_int(recent_data.tail(20)['Volume'].mean() if 'Volume' in recent_data else recent_data.tail(20).get('volume', volume).mean())
    
    # Generate chart data (last 3 months ~ 63 trading days)
    chart_lookback = min(63, len(spy_df))
    chart_data_df = spy_df.tail(chart_lookback)
    
    chart_data = []
    for idx, row in chart_data_df.iterrows():
        chart_data.append({
            'date': idx.strftime('%b %d'),
            'price': float(row.get('Close', row.get('close', 0)))
        })
    
    # Build response
    result = {
        'currentPrice': round(current_price, 2),
        'change': round(change, 2),
        'changePercent': round(change_percent, 2),
        'previousClose': round(previous_close, 2),
        'open': round(open_price, 2),
        'dayHigh': round(high_price, 2),
        'dayLow': round(low_price, 2),
        'volume': volume,
        'avgVolume': avg_volume,
        'fiftyTwoWeekHigh': round(week_52_high, 2),
        'fiftyTwoWeekLow': round(week_52_low, 2),
        'lastUpdated': latest_date.strftime('%B %d at %I:%M %p'),
        'chartData': chart_data,
        'dataSource': 'S3',
        'lastDataDate': latest_date.strftime('%Y-%m-%d')
    }
    
    return result


def get_cors_headers():
    """Return CORS headers for API Gateway"""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }


def error_response(status_code, message):
    """Return formatted error response"""
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps({
            'error': message,
            'statusCode': status_code
        })
    }


# pandas is imported at the top

