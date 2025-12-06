# 📊 SPY Live Data API - Deployment Guide

This guide walks you through deploying a Lambda-based API that serves live SPY price data from your S3 bucket.

## 🎯 Overview

**Architecture:**
```
S3 Bucket (market_data_normalized.parquet)
    ↓
Lambda Function (spy-data-fetcher)
    ↓
API Gateway (/api/spy-data)
    ↓
Frontend (React)
```

**What it does:**
- Reads SPY price data from S3 parquet file
- Calculates current price, change, 52-week high/low, volume metrics
- Generates 3-month chart data
- Returns JSON response via REST API

## 📦 Prerequisites

- AWS CLI configured with appropriate credentials
- S3 bucket: `mdaie-prml-spy-bucket`
- Parquet file: `market_data_normalized.parquet` in the bucket
- API Gateway ID: `0qoytg0cfg` (or set `API_GATEWAY_ID` env var)

## 🚀 Quick Start (3 Steps)

### Step 1: Create Lambda Function
```bash
bash scripts/08-deploy_market_data_lambda.sh
```

**What this does:**
- Creates Lambda function `spy-data-fetcher`
- Installs dependencies (boto3, pyarrow, pandas)
- Sets up IAM role with S3 read permissions
- Configures environment variables for S3 bucket/file
- Tests the function

**Expected output:**
```
✓ Lambda Function Created Successfully!
Function Name: spy-data-fetcher
```

### Step 2: Add API Gateway Endpoint
```bash
# Set your API Gateway ID (if different)
export API_GATEWAY_ID=0qoytg0cfg

bash scripts/add_spy_data_api_endpoint.sh
```

**What this does:**
- Creates `/api/spy-data` endpoint in API Gateway
- Configures GET method with Lambda proxy integration
- Enables CORS for frontend access
- Deploys to `prod` stage

**Expected output:**
```
✓ API Endpoint Created Successfully!
SPY Data Endpoint: https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/spy-data
```

### Step 3: Test the API
```bash
bash scripts/test_market_data_api.sh
```

**What this does:**
- Runs 4 automated tests
- Validates data structure
- Checks chart data
- Measures performance

**Expected output:**
```
✓ Test 1 PASSED
✓ Test 2 PASSED
✓ Test 3 PASSED
✓ Test 4 PASSED
```

## 📝 Manual Testing

### Using cURL
```bash
# Basic request
curl https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/spy-data | jq .

# Pretty-print specific fields
curl -s https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/spy-data | \
  jq '{price: .currentPrice, change: .change, percent: .changePercent}'
```

### Using Python
```python
import requests

url = "https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/spy-data"
response = requests.get(url)
data = response.json()

print(f"SPY Price: ${data['currentPrice']}")
print(f"Change: ${data['change']} ({data['changePercent']}%)")
print(f"Last Updated: {data['lastUpdated']}")
```

### Using JavaScript/React
```javascript
const fetchSPYData = async () => {
  const url = 'https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/spy-data';
  const response = await fetch(url);
  const data = await response.json();
  
  console.log(`SPY Price: $${data.currentPrice}`);
  console.log(`Change: $${data.change} (${data.changePercent}%)`);
  return data;
};
```

## 📊 API Response Format

```json
{
  "currentPrice": 659.03,
  "change": 6.50,
  "changePercent": 1.00,
  "previousClose": 652.53,
  "open": 655.05,
  "dayHigh": 664.55,
  "dayLow": 650.85,
  "volume": 115617357,
  "avgVolume": 79021570,
  "fiftyTwoWeekHigh": 689.70,
  "fiftyTwoWeekLow": 481.80,
  "lastUpdated": "November 21 at 4:00 PM",
  "chartData": [
    {"date": "Aug 21", "price": 625.32},
    {"date": "Aug 22", "price": 627.15},
    ...
  ],
  "dataSource": "S3",
  "lastDataDate": "2024-11-21"
}
```

## 🔧 Configuration

### Environment Variables

**Lambda Function:**
- `S3_BUCKET_NAME`: S3 bucket containing parquet file (default: `mdaie-prml-spy-bucket`)
- `S3_FILE_KEY`: Parquet file name (default: `market_data_normalized.parquet`)

**Frontend:**
- `REACT_APP_API_URL`: Base API Gateway URL (auto-configured during build)

### S3 Bucket Requirements

**Data Format:**
The parquet file should contain SPY OHLCV data with either:

1. **MultiIndex columns** (preferred):
   - Level 0: Ticker (e.g., "SPY")
   - Level 1: OHLCV fields ("Open", "High", "Low", "Close", "Volume")

2. **Flat columns**:
   - "Open", "High", "Low", "Close", "Volume"

**Index:**
- DatetimeIndex with timezone-naive dates
- No duplicate dates
- Sorted ascending

**Example structure:**
```
                  SPY                        
                 Open    High     Low   Close     Volume
Date                                                    
2024-08-21  625.32  628.40  624.10  625.80  75000000
2024-08-22  626.50  629.80  625.20  627.15  68000000
...
```

## 🔄 Updating the Data

To update the S3 data with fresh market data:

```bash
# Run the normalization script
cd scripts
python normalize_and_upload_s3.py

# This will:
# 1. Download latest data from yfinance
# 2. Normalize format (timezone-naive, consistent tickers)
# 3. Upload to S3 bucket
```

## 🚨 Troubleshooting

### Issue: "Bucket not found"
**Solution:** Check bucket name and ensure it exists
```bash
aws s3 ls s3://mdaie-prml-spy-bucket/
```

### Issue: "Access Denied"
**Solution:** Verify IAM role has S3 read permissions
```bash
aws iam get-role-policy --role-name lambda-spy-data-role --policy-name inline-s3-read
```

### Issue: "No data returned"
**Solution:** Check Lambda logs
```bash
aws logs tail /aws/lambda/spy-data-fetcher --follow
```

### Issue: "CORS error in browser"
**Solution:** Redeploy API Gateway
```bash
bash scripts/add_spy_data_api_endpoint.sh
```

## 📈 Performance

**Lambda specs:**
- Runtime: Python 3.11
- Memory: 512 MB
- Timeout: 30 seconds

**Typical performance:**
- Cold start: ~2-3 seconds
- Warm start: ~500-800ms
- Data size: ~2-5 MB parquet file

**Cost estimate (monthly):**
- Lambda invocations (10k/month): ~$0.20
- Data transfer (S3 → Lambda): ~$0.01
- API Gateway requests: ~$0.035
- **Total: ~$0.25/month**

## 🔐 Security

**IAM Permissions:**
- Lambda execution role has minimal S3 read-only access
- API Gateway endpoint is public (CORS enabled)
- No authentication required (add if needed)

**To add authentication:**
1. Enable API Gateway API key
2. Or use Cognito User Pools
3. Or use Lambda authorizer

## 🎨 Frontend Integration

The SPYPriceWidget component automatically uses this API when deployed:

```typescript
// In frontend/src/components/SPYPriceWidget.tsx
const API_URL = process.env.REACT_APP_API_URL.replace('/predict', '/api/spy-data');
const response = await fetch(API_URL);
const data = await response.json();
```

**Fallback behavior:**
- If API is unavailable → uses mock data
- Auto-refresh every 5 minutes
- Collapsible UI (starts collapsed)

## 📚 Additional Resources

**AWS Documentation:**
- [Lambda Python](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
- [API Gateway](https://docs.aws.amazon.com/apigateway/)
- [S3 with Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3.html)

**Related Scripts:**
- `scripts/normalize_and_upload_s3.py` - Update S3 data
- `scripts/MASTER_DEPLOY.sh` - Full deployment
- `ml_source/test_model.py --s3` - Test S3 data loading

## ✅ Verification Checklist

- [ ] Lambda function deployed and active
- [ ] API Gateway endpoint created and deployed
- [ ] Test script passes all 4 tests
- [ ] cURL request returns valid JSON
- [ ] Frontend widget shows real data (not mock)
- [ ] Auto-refresh works (check every 5 minutes)
- [ ] Chart displays correctly
- [ ] No CORS errors in browser console

## 🎯 Next Steps

1. **Update data regularly** - Set up CloudWatch Events to trigger data updates
2. **Add caching** - Use API Gateway caching to reduce Lambda invocations
3. **Monitor** - Set up CloudWatch alarms for errors
4. **Enhance** - Add more tickers (QQQ, DIA, etc.)

---

**Need help?** Check the test script output or Lambda CloudWatch logs for detailed error messages.

