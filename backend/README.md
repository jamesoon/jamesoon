# Market Data Lambda Backend

AWS Lambda function for fetching real-time market data from Yahoo Finance, fronted by API Gateway.

## Architecture

```
Frontend (React) → API Gateway → Lambda Function → Yahoo Finance API
```

## Features

- **Real-time market data** for DOW, NASDAQ, S&P 500, and Russell 2000
- **3-month historical** OHLC (candlestick) data
- **Serverless architecture** with AWS Lambda
- **API Gateway integration** with CORS support
- **Automatic error handling** with fallback to simulated data in frontend

## Files

- `lambda_market_data.py` - Main Lambda function code
- `requirements.txt` - Python dependencies
- `../scripts/07_deploy_market_data_lambda.sh` - Deployment script

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- AWS IAM permissions for Lambda, API Gateway, and IAM role management
- Python 3.9+ (for Lambda runtime)

### Deploy to AWS

```bash
cd /path/to/project
./scripts/07_deploy_market_data_lambda.sh
```

This script will:
1. Create/update IAM role for Lambda
2. Package Python dependencies
3. Deploy Lambda function
4. Create/update API Gateway
5. Configure CORS
6. Output the API endpoint URL

### Post-Deployment

After deployment, update your frontend environment variable:

```bash
# In frontend/.env
REACT_APP_MARKET_DATA_API=https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices
```

## API Endpoints

### Get Market Indices

**Endpoint:** `GET /api/market-indices`

**Response:**
```json
[
  {
    "name": "DOW",
    "symbol": "^DJI",
    "current": 46245.4,
    "change": 493.15,
    "changePercent": 1.08,
    "color": "#4caf50",
    "chartData": [
      {
        "date": "Aug 21",
        "open": 43250.12,
        "high": 43350.45,
        "low": 43100.23,
        "close": 43280.67,
        "openClose": [43250.12, 43280.67]
      }
      // ... more days
    ]
  }
  // ... more indices
]
```

### Health Check

**Endpoint:** `GET /api/health`

**Response:**
```json
{
  "status": "ok",
  "message": "SUTD Trading Market Data API",
  "timestamp": "2024-11-22T10:30:00.000Z"
}
```

## Lambda Configuration

- **Runtime:** Python 3.9
- **Memory:** 512 MB
- **Timeout:** 60 seconds
- **Handler:** `lambda_market_data.lambda_handler`

## Dependencies

- `yfinance` - Yahoo Finance API client
- `boto3` - AWS SDK for Python
- `pandas` - Data manipulation
- `numpy` - Numerical operations

## Error Handling

The Lambda function includes comprehensive error handling:

1. **API Errors:** Returns 500 status with error message
2. **Individual Index Failures:** Continues with other indices
3. **Network Issues:** Logged and returned as errors
4. **Frontend Fallback:** Frontend automatically uses simulated data if API fails

## Cost Optimization

- **Lambda Free Tier:** 1M requests/month, 400,000 GB-seconds/month
- **API Gateway Free Tier:** 1M API calls/month for 12 months
- **Typical Cost:** $0-5/month for moderate usage

## Testing

Test the deployed API:

```bash
# Health check
curl https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod/api/health

# Get market data
curl https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices
```

## Monitoring

View Lambda logs in CloudWatch:

```bash
aws logs tail /aws/lambda/market-data-fetcher --follow
```

## Troubleshooting

### Lambda Timeout
- Increase timeout in deployment script (current: 60s)
- Check network connectivity to Yahoo Finance

### CORS Errors
- Verify API Gateway CORS configuration
- Check browser console for specific errors

### No Data Returned
- Check CloudWatch logs for errors
- Verify yfinance package is working
- Test individual ticker symbols

## Update Lambda Function

To update after code changes:

```bash
./scripts/07_deploy_market_data_lambda.sh
```

The script automatically detects existing functions and updates them.

## Cleanup

To remove the Lambda and API Gateway:

```bash
# Delete Lambda function
aws lambda delete-function --function-name market-data-fetcher

# Delete API Gateway (get REST API ID first)
aws apigateway delete-rest-api --rest-api-id YOUR_API_ID
```

## Integration with Main Project

This backend integrates with the existing SUTD MDAI-E PRML Project:

- **ML Model API:** Prediction endpoint for stock forecasting
- **Market Data API:** Real-time data for portfolio dashboard
- **Frontend:** React application consuming both APIs

## Development

For local testing (requires modification):

```python
# Add to lambda_market_data.py
if __name__ == "__main__":
    event = {"httpMethod": "GET", "path": "/api/market-indices"}
    result = lambda_handler(event, None)
    print(json.dumps(result, indent=2))
```

Run:
```bash
python backend/lambda_market_data.py
```

## Security

- API Gateway with CORS enabled (origin: *)
- No API keys required (can be added if needed)
- Lambda execution role with minimal permissions
- No sensitive data in environment variables

## Future Enhancements

- [ ] Add caching layer (DynamoDB/ElastiCache)
- [ ] Implement API key authentication
- [ ] Add more indices (international markets)
- [ ] WebSocket support for real-time updates
- [ ] Historical data for custom date ranges
