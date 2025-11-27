# Market Data API - Deployment Guide

Complete guide for deploying the real-time market data Lambda function and API Gateway.

## Quick Start

```bash
# From project root
./scripts/07_deploy_market_data_lambda.sh
```

## Architecture Overview

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐      ┌──────────────┐
│   React     │─────→│  API Gateway │─────→│   Lambda    │─────→│    Yahoo     │
│  Frontend   │      │              │      │   Function  │      │   Finance    │
└─────────────┘      └──────────────┘      └─────────────┘      └──────────────┘
                            ↓                      ↓
                     CORS Enabled           Python 3.9
                     REST API               yfinance lib
```

## Prerequisites

### 1. AWS CLI Configuration

```bash
# Check if AWS CLI is configured
aws sts get-caller-identity

# If not configured:
aws configure
# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: ap-southeast-1
# - Output format: json
```

### 2. Required Permissions

Your AWS IAM user/role needs:
- `lambda:*` - Lambda function management
- `apigateway:*` - API Gateway management
- `iam:CreateRole` - Create Lambda execution role
- `iam:AttachRolePolicy` - Attach policies to roles
- `iam:GetRole` - Read role information

### 3. Python Dependencies

```bash
# Check Python version (3.9+ required)
python3 --version

# Install pip packages locally (for testing)
pip3 install -r backend/requirements.txt
```

## Step-by-Step Deployment

### Step 1: Navigate to Project Root

```bash
cd /path/to/SUTD/MSTR-DAIE/MLOPS/Project
```

### Step 2: Review Backend Code

```bash
# Check Lambda function
cat backend/lambda_market_data.py

# Check dependencies
cat backend/requirements.txt
```

### Step 3: Run Deployment Script

```bash
chmod +x scripts/07_deploy_market_data_lambda.sh
./scripts/07_deploy_market_data_lambda.sh
```

### Step 4: Note the API Endpoint

The script will output:
```
======================================
✅ Deployment Complete!
======================================

Market Data API Endpoint:
https://abc123xyz.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices

Test the endpoint:
curl https://abc123xyz.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices

Update your frontend .env file with:
REACT_APP_MARKET_DATA_API=https://abc123xyz.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices
```

### Step 5: Update Frontend Configuration

```bash
cd frontend

# Create .env file if it doesn't exist
cat > .env <<EOF
REACT_APP_MARKET_DATA_API=https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices
EOF
```

### Step 6: Test the API

```bash
# Health check
curl https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/prod/api/health

# Get market data
curl https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices
```

### Step 7: Start Frontend

```bash
cd frontend
npm start
```

## What the Script Does

1. **Creates/Updates IAM Role**
   - Role name: `ml-api-lambda-role`
   - Attaches `AWSLambdaBasicExecutionRole` policy
   - Allows Lambda to write CloudWatch logs

2. **Packages Lambda Function**
   - Installs Python dependencies
   - Creates deployment ZIP package
   - Includes `yfinance`, `pandas`, `boto3`

3. **Deploys Lambda Function**
   - Function name: `market-data-fetcher`
   - Runtime: Python 3.9
   - Memory: 512 MB
   - Timeout: 60 seconds

4. **Creates API Gateway**
   - API name: `MarketDataAPI`
   - Endpoint: `/api/market-indices`
   - Methods: GET, OPTIONS (CORS)
   - Stage: `prod`

5. **Configures CORS**
   - Allows all origins (`*`)
   - Headers: Content-Type, Authorization
   - Methods: GET, OPTIONS

6. **Grants Permissions**
   - Allows API Gateway to invoke Lambda
   - Creates execution permissions

## Verification

### Check Lambda Function

```bash
aws lambda get-function --function-name market-data-fetcher
```

### Check API Gateway

```bash
aws apigateway get-rest-apis --query "items[?name=='MarketDataAPI']"
```

### View Lambda Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/market-data-fetcher --follow

# Last 10 minutes
aws logs tail /aws/lambda/market-data-fetcher --since 10m
```

## Updating the Lambda

After making changes to `lambda_market_data.py`:

```bash
./scripts/07_deploy_market_data_lambda.sh
```

The script automatically detects and updates existing resources.

## Troubleshooting

### Issue: "Role not found"

**Solution:** Wait 10-15 seconds after role creation
```bash
# The script includes a sleep, but if needed:
sleep 15
./scripts/07_deploy_market_data_lambda.sh
```

### Issue: "Package too large"

**Solution:** Lambda packages must be < 250 MB unzipped
```bash
# Check package size
du -h lambda_market_data.zip

# If too large, reduce dependencies in requirements.txt
```

### Issue: "API Gateway 403 Forbidden"

**Solution:** Check CORS configuration
```bash
# Redeploy API Gateway
aws apigateway create-deployment \
  --rest-api-id YOUR_API_ID \
  --stage-name prod
```

### Issue: "Lambda timeout"

**Solution:** Increase timeout or optimize code
```bash
# Update timeout
aws lambda update-function-configuration \
  --function-name market-data-fetcher \
  --timeout 90
```

### Issue: "No data returned"

**Check CloudWatch logs:**
```bash
aws logs tail /aws/lambda/market-data-fetcher --follow
```

**Common causes:**
- Yahoo Finance rate limiting
- Network connectivity issues
- Invalid ticker symbols

## Cost Estimation

### AWS Free Tier (12 months)
- **Lambda:** 1M requests/month, 400,000 GB-seconds
- **API Gateway:** 1M API calls/month
- **CloudWatch Logs:** 5 GB

### Beyond Free Tier
- **Lambda:** $0.20 per 1M requests + $0.0000166667 per GB-second
- **API Gateway:** $3.50 per million requests
- **Data Transfer:** First 1 GB free, then $0.09/GB

### Example Monthly Cost (moderate usage)
- 100,000 API calls
- Average 3-second execution
- 512 MB memory
- **Estimated cost:** $0.50 - $2.00/month

## Security Best Practices

### 1. Restrict CORS (Production)

Edit `lambda_market_data.py`:
```python
'Access-Control-Allow-Origin': 'https://your-domain.com'
```

### 2. Add API Key (Optional)

```bash
# Create API key
aws apigateway create-api-key \
  --name MarketDataAPIKey \
  --enabled

# Create usage plan and associate
```

### 3. Enable CloudWatch Alarms

```bash
# Create alarm for errors
aws cloudwatch put-metric-alarm \
  --alarm-name market-data-errors \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10
```

## Integration with Main Project

This Lambda function complements the existing ML prediction API:

```
Project Structure:
├── ML Model API (Prediction)
│   └── POST /predict
├── Market Data API (New)
│   └── GET /api/market-indices
└── Frontend
    ├── Prediction Page → ML Model API
    └── Portfolio Page → Market Data API
```

## Monitoring & Maintenance

### Daily Checks
- Monitor CloudWatch dashboard
- Check error rates
- Verify data freshness

### Weekly Tasks
- Review Lambda execution duration
- Check API Gateway throttling
- Analyze cost reports

### Monthly Tasks
- Update dependencies
- Review security settings
- Optimize performance

## Cleanup

To remove all resources:

```bash
# Delete Lambda function
aws lambda delete-function --function-name market-data-fetcher

# Delete API Gateway
REST_API_ID=$(aws apigateway get-rest-apis --query "items[?name=='MarketDataAPI'].id" --output text)
aws apigateway delete-rest-api --rest-api-id $REST_API_ID

# Delete IAM role (if not used by other Lambdas)
aws iam detach-role-policy \
  --role-name ml-api-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name ml-api-lambda-role
```

## Support

For issues or questions:
1. Check CloudWatch logs first
2. Review this guide's troubleshooting section
3. Test API endpoints manually with `curl`
4. Verify AWS permissions

## Next Steps

After successful deployment:
1. ✅ Test API endpoint with `curl`
2. ✅ Update frontend `.env` file
3. ✅ Restart frontend development server
4. ✅ Verify portfolio page shows live data
5. ✅ Monitor CloudWatch for any errors

