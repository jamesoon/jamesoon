# AWS Deployment Architecture for SPY Prediction Model

## Current Requirements Analysis

### Data Dependencies
- **8 Tickers**: SPY, QQQ, GLD, USO, TLT, SHY, VIX, DXY
- **Historical Data**: From 2015-01-01 (or minimum ~70 days for rolling windows)
- **Rolling Windows**: 
  - 20-day: MA, volume z-score, correlations
  - 60-day: Risk-off proxy (VIX + DXY z-scores)
- **Lagged Features**: 1, 2, 5 days
- **Minimum History Needed**: ~70 trading days (~3 months)

### Current Architecture
```
API Gateway → Lambda (Proxy) → EKS (Flask App) → yfinance (on-demand download)
```

### Problems with Current Approach
1. **Latency**: Downloading 10+ years of data on every request (5-10 seconds)
2. **Rate Limits**: Yahoo Finance may throttle requests
3. **Cost**: Repeated downloads of same data
4. **Reliability**: External API dependency
5. **Lambda Timeout**: Risk of exceeding 15-minute limit

---

## Recommended Architecture Options

### **Option 1: S3 + Lambda Pre-computation (RECOMMENDED)**

**Architecture:**
```
API Gateway → Lambda → EKS
                    ↓
            S3 (Historical Data)
                    ↓
        EventBridge (Daily Update)
```

**Implementation:**
- **S3 Bucket**: Store historical OHLCV data as Parquet files
  - Structure: `s3://bucket/market-data/{ticker}/{year}/{month}.parquet`
  - Or single file: `s3://bucket/market-data/latest.parquet`
- **Lambda Function** (Daily Update):
  - Triggered by EventBridge at market close (4:30 PM EST)
  - Downloads only new data (last 1-2 days)
  - Updates S3 Parquet files
  - Updates latest features cache
- **EKS Service**:
  - Loads data from S3 on startup (or cache in memory)
  - Appends new data daily
  - Computes features from cached data

**Pros:**
- ✅ Fast inference (< 1 second)
- ✅ No external API calls during inference
- ✅ Cost-effective (S3 storage ~$0.023/GB/month)
- ✅ Reliable (no rate limits)
- ✅ Scalable (multiple EKS pods can share S3)

**Cons:**
- ⚠️ Requires daily update job
- ⚠️ Slight delay (up to 1 day) if update fails

**Cost Estimate:**
- S3 Storage: ~50MB data × $0.023/GB = $0.001/month
- Lambda (daily): 1 execution × $0.20/1M requests = negligible
- Data Transfer: Minimal (within AWS)

---

## **RECOMMENDED SOLUTION: Option 1 (S3 + Lambda Pre-computation)**

### Implementation Plan

#### 1. **S3 Data Structure**
```
s3://your-bucket/market-data/
├── latest.parquet          # Latest full dataset (all tickers, all dates)
├── latest_features.parquet # Pre-computed latest features (optional)
└── archive/
    ├── 2024/
    │   ├── 01.parquet
    │   └── 02.parquet
    └── ...
```

#### 2. **Lambda Update Function** (Daily at 4:30 PM EST)
```python
# lambda_data_updater/lambda_function.py
import boto3
import pandas as pd
import yfinance as yf
from datetime import datetime

s3 = boto3.client('s3')
BUCKET = 'your-market-data-bucket'

def lambda_handler(event, context):
    # Download latest data
    tickers = ['SPY', 'QQQ', 'GLD', 'USO', 'TLT', 'SHY', '^VIX', 'DX-Y.NYB']
    data = yf.download(' '.join(tickers), period='5d', auto_adjust=True)
    
    # Load existing data from S3
    try:
        existing = pd.read_parquet(f's3://{BUCKET}/market-data/latest.parquet')
        # Append new data
        combined = pd.concat([existing, data]).drop_duplicates().sort_index()
    except:
        combined = data
    
    # Save to S3
    combined.to_parquet(f's3://{BUCKET}/market-data/latest.parquet')
    
    return {'statusCode': 200, 'body': 'Data updated successfully'}
```

#### 3. **EKS Service Update** (app.py)
```python
import boto3
import pandas as pd
from io import BytesIO

s3 = boto3.client('s3')
BUCKET = 'your-market-data-bucket'

# Load data on startup (or cache)
def load_market_data():
    obj = s3.get_object(Bucket=BUCKET, Key='market-data/latest.parquet')
    return pd.read_parquet(BytesIO(obj['Body'].read()))

# Initialize on startup
raw_prices = load_market_data()

def run_inference(ticker=None, date=None):
    # Use cached data instead of downloading
    recent_raw = raw_prices.copy()
    
    if date:
        recent_raw = recent_raw[recent_raw.index <= date]
    
    # Rest of inference logic...
```

#### 4. **EventBridge Schedule**
```json
{
  "ScheduleExpression": "cron(30 21 ? * MON-FRI *)",
  "Description": "Update market data after market close (4:30 PM EST)"
}
```

---

## Migration Steps

1. **Create S3 Bucket**
   ```bash
   aws s3 mb s3://your-market-data-bucket
   ```

2. **Initial Data Load**
   - Run script to download historical data
   - Upload to S3 as Parquet

3. **Deploy Lambda Updater**
   - Create Lambda function with daily schedule
   - Test with manual invocation

4. **Update EKS Service**
   - Modify app.py to load from S3
   - Add boto3 to requirements.txt
   - Deploy updated container

5. **Monitor & Validate**
   - Check Lambda logs
   - Verify S3 updates
   - Test inference latency

---

## Cost Comparison

| Option | Monthly Cost | Latency | Complexity |
|-------|-------------|---------|------------|
| **Current (yfinance)** | $0 | 5-10s | Low |
| **S3 + Lambda** | ~$0.01 | <1s | Medium |

---

## Security Considerations

1. **S3 Bucket Policy**: Restrict access to EKS service role
2. **IAM Roles**: Least privilege for Lambda and EKS
3. **Encryption**: Enable S3 server-side encryption
4. **VPC**: Consider VPC endpoint for S3 (reduces data transfer costs)

---

## Next Steps

1. Choose architecture option (recommend Option 1)
2. Create S3 bucket and initial data load script
3. Implement Lambda updater function
4. Update EKS service to use S3
5. Set up EventBridge schedule
6. Test end-to-end
7. Monitor and optimize

