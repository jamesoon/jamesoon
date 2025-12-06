# AWS Deployment Guide: S3-Based Market Data Storage

## Quick Start

### 1. Create S3 Bucket

```bash
aws s3 mb s3://your-market-data-bucket
aws s3api put-bucket-versioning \
    --bucket your-market-data-bucket \
    --versioning-configuration Status=Enabled
```

### 2. Initial Data Load

```bash
# Set environment variable
export S3_BUCKET_NAME=your-market-data-bucket

# Run initial load script
cd scripts
python 03-initial_s3_data_load.py
```

### 3. Deploy Lambda Updater

Use the automated script to deploy the updater lambda:

```bash
cd scripts
./12-deploy_updater_lambda_container.sh
```

Alternatively, to deploy manually:

```bash
cd lambda_data_updater

# Create deployment package
pip install -r requirements.txt -t .
zip -r lambda_data_updater.zip .

# Create Lambda function
aws lambda create-function \
    --function-name market-data-updater \
    --runtime python3.11 \
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-s3-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://lambda_data_updater.zip \
    --timeout 300 \
    --environment Variables="{S3_BUCKET_NAME=your-market-data-bucket}"

# Create EventBridge rule (daily at 4:30 PM EST = 9:30 PM UTC)
aws events put-rule \
    --name market-data-daily-update \
    --schedule-expression "cron(30 21 ? * MON-FRI *)" \
    --description "Update market data after market close"

# Add Lambda permission
aws lambda add-permission \
    --function-name market-data-updater \
    --statement-id eventbridge-invoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:REGION:ACCOUNT:rule/market-data-daily-update

# Add Lambda as target
aws events put-targets \
    --rule market-data-daily-update \
    --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:market-data-updater"
```

### 4. Update EKS Service

```bash
# Update Dockerfile to use app.py (standardized)
# app.py now contains the S3 logic (formerly app_s3.py)

# Update requirements.txt
cp ml_source/requirements_s3.txt ml_source/requirements.txt

# Set environment variables in Kubernetes deployment
kubectl set env deployment/ml-api \
    S3_BUCKET_NAME=your-market-data-bucket \
    USE_S3=true

# Ensure EKS service role has S3 read permissions
```

### 5. IAM Roles & Permissions

#### Lambda Role (for data updater)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::your-market-data-bucket/*"
    }
  ]
}
```

#### EKS Service Role (for inference)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-market-data-bucket/*"
    }
  ]
}
```

## Architecture

```
┌─────────────┐
│ API Gateway │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Lambda    │ (Proxy)
└──────┬──────┘
       │
       ▼
┌─────────────┐      ┌──────────────┐
│     EKS     │─────▶│  S3 Bucket   │
│  (Flask)    │◀─────│ (Parquet)    │
└─────────────┘      └──────────────┘
       │                    ▲
       │                    │
       │              ┌─────┴─────┐
       │              │  Lambda   │
       │              │  Updater  │
       │              └─────┬─────┘
       │                    │
       │              ┌─────┴─────┐
       │              │EventBridge│
       │              │ (Daily)   │
       │              └───────────┘
       │
       ▼
┌─────────────┐
│   Model     │
│  (model.pkl)│
└─────────────┘
```

## Monitoring

### CloudWatch Metrics
- Lambda invocations (updater)
- S3 object size
- EKS API latency
- Cache hit rate

### Alarms
- Lambda failures
- S3 update failures
- EKS service health

## Troubleshooting

### Lambda fails to update
- Check CloudWatch logs
- Verify IAM permissions
- Check yfinance API status

### EKS can't read from S3
- Verify IAM role attached to pod
- Check bucket policy
- Verify S3 key path

### Stale data
- Check EventBridge rule status
- Verify Lambda execution logs
- Manually trigger Lambda for testing

## Cost Optimization

1. **S3 Lifecycle Policies**: Archive old data to Glacier
2. **VPC Endpoint**: Reduce data transfer costs
3. **Cache TTL**: Adjust cache refresh interval
4. **Parquet Compression**: Already using snappy

## Testing

```bash
# Test Lambda updater manually
aws lambda invoke \
    --function-name market-data-updater \
    --payload '{}' \
    response.json

# Test EKS service
curl -X POST https://your-api-gateway-url/predict \
    -H "Content-Type: application/json" \
    -d '{"ticker": "SPY"}'
```

