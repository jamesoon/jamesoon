#!/bin/bash

# Exit on error
set -e

# Variables
AWS_REGION="ap-southeast-1"
LAMBDA_FUNCTION_NAME="market-data-fetcher"
LAMBDA_ROLE_NAME="ml-api-lambda-role"
API_GATEWAY_NAME="MarketDataAPI"

echo "======================================"
echo "Deploying Market Data Lambda & API Gateway"
echo "======================================"

# Get Lambda Role ARN (reuse existing role or create if needed)
LAMBDA_ROLE_ARN=$(aws iam get-role --role-name $LAMBDA_ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$LAMBDA_ROLE_ARN" ]; then
    echo "Creating IAM role for Lambda..."
    # Create role with trust policy
    cat > /tmp/lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
      --role-name $LAMBDA_ROLE_NAME \
      --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
      --region $AWS_REGION

    # Attach basic execution role
    aws iam attach-role-policy \
      --role-name $LAMBDA_ROLE_NAME \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
      --region $AWS_REGION

    # Wait for role to propagate
    echo "Waiting for IAM role to propagate..."
    sleep 10

    LAMBDA_ROLE_ARN=$(aws iam get-role --role-name $LAMBDA_ROLE_NAME --query 'Role.Arn' --output text)
fi

# Attach S3 access policy to Lambda role
echo "Attaching S3 access policy to Lambda role..."
aws iam put-role-policy \
    --role-name $LAMBDA_ROLE_NAME \
    --policy-name S3AccessPolicy \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    "arn:aws:s3:::mdaie-prml-spy-bucket",
                    "arn:aws:s3:::mdaie-prml-spy-bucket/*"
                ]
            }
        ]
    }' \
    --region $AWS_REGION


    echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"

# Attach DynamoDB access policy to Lambda role (New)
echo "Attaching DynamoDB access policy to Lambda role..."
TABLE_NAME="TradingApp"
# Get Table ARN
TABLE_ARN=$(aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" --query 'Table.TableArn' --output text 2>/dev/null || echo "")

if [ -n "$TABLE_ARN" ]; then
    aws iam put-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-name DynamoDBAccessPolicy \
        --policy-document "{
            \"Version\": \"2012-10-17\",
            \"Statement\": [
                {
                    \"Effect\": \"Allow\",
                    \"Action\": [
                        \"dynamodb:PutItem\",
                        \"dynamodb:GetItem\",
                        \"dynamodb:UpdateItem\"
                    ],
                    \"Resource\": \"$TABLE_ARN\"
                }
            ]
        }" \
        --region $AWS_REGION
else
    echo "⚠️  Warning: DynamoDB table '$TABLE_NAME' not found. Skipping DynamoDB policy attachment."
fi

# Package Lambda function
echo "Packaging Lambda function..."
rm -rf lambda_market_data_package lambda_market_data.zip

mkdir -p lambda_market_data_package

# Install dependencies with legacy resolver (more compatible)
echo "Installing Python dependencies..."

# Install dependencies with platform flags for AWS Lambda (Linux x86_64)
echo "Installing Python dependencies for Linux x86_64..."

python3 -m pip install \
    --platform manylinux2014_x86_64 \
    --target lambda_market_data_package \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    yfinance pandas requests pyarrow

echo "Checking if yfinance was installed..."
if [ -d "lambda_market_data_package/yfinance" ]; then
    echo "✓ yfinance installed successfully"
else
    echo "✗ yfinance installation failed!"
    echo "Listing what was installed:"
    ls -la lambda_market_data_package/ | head -20
    exit 1
fi

# Copy Lambda function
cp lambda_spy_data/lambda_function.py lambda_market_data_package/lambda_market_data.py

# Remove unnecessary files to reduce package size
echo "Removing unnecessary files to reduce package size..."
cd lambda_market_data_package

# Remove unnecessary files to reduce package size
echo "Cleaning up unnecessary files..."

# Remove __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove .pyc and .pyo files
find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true

# Remove test directories (large)
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
# find . -type d -name "*test*" -exec rm -rf {} + 2>/dev/null || true

# Remove documentation
find . -type d \( -name "docs" -o -name "doc" \) -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name "*.md" -o -name "*.rst" -o -name "*.txt" \) ! -name "*.py" -delete 2>/dev/null || true

# Remove data files (but keep yfinance data)
find . -type f \( -name "*.csv" -o -name "*.xml" \) -delete 2>/dev/null || true

# Remove unnecessary pandas/numpy files
# rm -rf pandas/tests 2>/dev/null || true
# rm -rf numpy/tests 2>/dev/null || true
# rm -rf scipy/tests 2>/dev/null || true
# rm -rf pandas/doc 2>/dev/null || true
# rm -rf numpy/doc 2>/dev/null || true

# Create zip with compression
echo "Creating deployment package..."
zip -r ../lambda_market_data.zip . -q

cd ..

PACKAGE_SIZE=$(du -m lambda_market_data.zip | cut -f1)
echo "Lambda package size: ${PACKAGE_SIZE}MB"

# Verify yfinance is in the package
echo "Verifying package contents..."
if unzip -l lambda_market_data.zip | grep -q "yfinance"; then
    echo "✓ yfinance found in package"
else
    echo "✗ ERROR: yfinance not found in package!"
    exit 1
fi

# Check if package is too large for direct upload (50MB limit)
if [ "$PACKAGE_SIZE" -gt 10 ]; then
    echo "⚠️  Warning: Package size (${PACKAGE_SIZE}MB) exceeds 50MB direct upload limit"
    echo "   Will use S3 for deployment..."
    USE_S3_DEPLOYMENT=true
else
    USE_S3_DEPLOYMENT=false
fi

# Check if Lambda function exists
LAMBDA_EXISTS=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION 2>/dev/null || echo "")

# Deploy to Lambda (use S3 if package is too large)
if [ "$USE_S3_DEPLOYMENT" = true ]; then
    echo "Uploading package to S3 for deployment..."
    S3_BUCKET_NAME="${LAMBDA_FUNCTION_NAME}-deployments"
    
    # Create S3 bucket if it doesn't exist
    aws s3 mb s3://$S3_BUCKET_NAME --region $AWS_REGION 2>/dev/null || echo "Bucket already exists or error creating"
    
    # Upload zip to S3
    S3_KEY="lambda-packages/${LAMBDA_FUNCTION_NAME}-$(date +%s).zip"
    aws s3 cp lambda_market_data.zip s3://$S3_BUCKET_NAME/$S3_KEY --region $AWS_REGION
    
    S3_OBJECT_URL="s3://$S3_BUCKET_NAME/$S3_KEY"
    echo "Package uploaded to: $S3_OBJECT_URL"
    
    if [ -z "$LAMBDA_EXISTS" ]; then
        echo "Creating Lambda function: $LAMBDA_FUNCTION_NAME..."
        aws lambda create-function \
          --function-name $LAMBDA_FUNCTION_NAME \
          --runtime python3.11 \
          --role $LAMBDA_ROLE_ARN \
          --handler lambda_market_data.lambda_handler \
          --code S3Bucket=$S3_BUCKET_NAME,S3Key=$S3_KEY \
          --timeout 60 \
          --memory-size 512 \
          --region $AWS_REGION \
          --environment "Variables={DYNAMODB_TABLE=$TABLE_NAME}" \
          --description "Fetches real-time market data from S3/Yahoo Finance and records to DB"
    else
        echo "Updating existing Lambda function: $LAMBDA_FUNCTION_NAME..."
        aws lambda update-function-code \
          --function-name $LAMBDA_FUNCTION_NAME \
          --s3-bucket $S3_BUCKET_NAME \
          --s3-key $S3_KEY \
          --region $AWS_REGION
          
        # Wait for update to complete
        aws lambda wait function-updated \
          --function-name $LAMBDA_FUNCTION_NAME \
          --region $AWS_REGION

        # Update config to include env var
        aws lambda update-function-configuration \
            --function-name $LAMBDA_FUNCTION_NAME \
            --environment "Variables={DYNAMODB_TABLE=$TABLE_NAME}" \
            --region $AWS_REGION

        # Wait for update to complete
        aws lambda wait function-updated \
          --function-name $LAMBDA_FUNCTION_NAME \
          --region $AWS_REGION
    fi
else
    # Direct upload (package < 50MB)
    if [ -z "$LAMBDA_EXISTS" ]; then
        echo "Creating Lambda function: $LAMBDA_FUNCTION_NAME..."
        aws lambda create-function \
          --function-name $LAMBDA_FUNCTION_NAME \
          --runtime python3.11 \
          --role $LAMBDA_ROLE_ARN \
          --handler lambda_market_data.lambda_handler \
          --zip-file fileb://lambda_market_data.zip \
          --timeout 60 \
          --memory-size 512 \
          --region $AWS_REGION \
          --environment "Variables={DYNAMODB_TABLE=$TABLE_NAME}" \
          --description "Fetches real-time market data from S3/Yahoo Finance and records to DB"
    else
        echo "Updating existing Lambda function: $LAMBDA_FUNCTION_NAME..."
        aws lambda update-function-code \
          --function-name $LAMBDA_FUNCTION_NAME \
          --zip-file fileb://lambda_market_data.zip \
          --region $AWS_REGION
          
        # Wait for update to complete
        aws lambda wait function-updated \
          --function-name $LAMBDA_FUNCTION_NAME \
          --region $AWS_REGION

        # Update config to include env var
        aws lambda update-function-configuration \
            --function-name $LAMBDA_FUNCTION_NAME \
            --environment "Variables={DYNAMODB_TABLE=$TABLE_NAME}" \
            --region $AWS_REGION

        # Wait for update to complete
        aws lambda wait function-updated \
          --function-name $LAMBDA_FUNCTION_NAME \
          --region $AWS_REGION
    fi
fi

# Add EventBridge Rule for Daily SPY recording (New)
echo "Setting up EventBridge Rule for Daily Execution..."
RULE_NAME="DailySPYRecord"
# Schedule: Daily at 22:00 UTC (after market close)
SCHEDULE_EXPRESSION="cron(0 22 * * ? *)"

aws events put-rule \
    --name $RULE_NAME \
    --schedule-expression "$SCHEDULE_EXPRESSION" \
    --state ENABLED \
    --description "Daily SPY price recording" \
    --region $AWS_REGION

# Add target
FUNCTION_ARN=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --query 'Configuration.FunctionArn' --output text --region $AWS_REGION)
aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id"="1","Arn"="$FUNCTION_ARN" \
    --region $AWS_REGION

# Permission for EventBridge to invoke Lambda
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id "AllowEventBridgeInvoke-$(date +%s)" \
    --action "lambda:InvokeFunction" \
    --principal "events.amazonaws.com" \
    --source-arn "$(aws events describe-rule --name $RULE_NAME --query 'Arn' --output text --region $AWS_REGION)" \
    --region $AWS_REGION 2>/dev/null || echo "EventBridge permission already exists"

echo "Lambda function deployed successfully!"

# Create or update API Gateway
echo "Setting up API Gateway: $API_GATEWAY_NAME..."

# Check if API Gateway exists
REST_API_ID=$(aws apigateway get-rest-apis \
  --query "items[?name=='$API_GATEWAY_NAME'].id" \
  --output text \
  --region $AWS_REGION)

if [ -z "$REST_API_ID" ]; then
    echo "Creating new REST API..."
    REST_API_ID=$(aws apigateway create-rest-api \
      --name $API_GATEWAY_NAME \
      --description "API Gateway for Real-Time Market Data" \
      --query 'id' --output text \
      --region $AWS_REGION)
fi

echo "API Gateway ID: $REST_API_ID"

# Get root resource ID
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $REST_API_ID \
  --query 'items[?path==`/`].id' --output text \
  --region $AWS_REGION)

echo "Root Resource ID: $ROOT_RESOURCE_ID"

# Create /api resource if it doesn't exist
API_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $REST_API_ID \
  --query "items[?pathPart=='api'].id" --output text \
  --region $AWS_REGION)

if [ -z "$API_RESOURCE_ID" ]; then
    echo "Creating /api resource..."
    API_RESOURCE_ID=$(aws apigateway create-resource \
      --rest-api-id $REST_API_ID \
      --parent-id $ROOT_RESOURCE_ID \
      --path-part "api" \
      --query 'id' --output text \
      --region $AWS_REGION)
fi

# Create /api/market-indices resource if it doesn't exist
MARKET_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $REST_API_ID \
  --query "items[?pathPart=='market-indices'].id" --output text \
  --region $AWS_REGION)

if [ -z "$MARKET_RESOURCE_ID" ]; then
    echo "Creating /api/market-indices resource..."
    MARKET_RESOURCE_ID=$(aws apigateway create-resource \
      --rest-api-id $REST_API_ID \
      --parent-id $API_RESOURCE_ID \
      --path-part "market-indices" \
      --query 'id' --output text \
      --region $AWS_REGION)
fi

echo "/api/market-indices Resource ID: $MARKET_RESOURCE_ID"

# Setup GET method
echo "Setting up GET method for /api/market-indices..."
aws apigateway put-method \
  --rest-api-id $REST_API_ID \
  --resource-id $MARKET_RESOURCE_ID \
  --http-method GET \
  --authorization-type "NONE" \
  --region $AWS_REGION \
  --no-api-key-required 2>/dev/null || echo "Method already exists"

# Setup OPTIONS method for CORS
echo "Setting up OPTIONS method for CORS..."
aws apigateway put-method \
  --rest-api-id $REST_API_ID \
  --resource-id $MARKET_RESOURCE_ID \
  --http-method OPTIONS \
  --authorization-type "NONE" \
  --region $AWS_REGION \
  --no-api-key-required 2>/dev/null || echo "OPTIONS already exists"

# Setup CORS response
aws apigateway put-method-response \
  --rest-api-id $REST_API_ID \
  --resource-id $MARKET_RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters \
    "method.response.header.Access-Control-Allow-Headers=true,\
     method.response.header.Access-Control-Allow-Methods=true,\
     method.response.header.Access-Control-Allow-Origin=true" \
  --region $AWS_REGION 2>/dev/null || echo "OPTIONS response already exists"

aws apigateway put-integration \
  --rest-api-id $REST_API_ID \
  --resource-id $MARKET_RESOURCE_ID \
  --http-method OPTIONS \
  --type MOCK \
  --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
  --region $AWS_REGION 2>/dev/null || echo "OPTIONS integration already exists"

aws apigateway put-integration-response \
  --rest-api-id $REST_API_ID \
  --resource-id $MARKET_RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters \
    '{"method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'"'",
      "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,OPTIONS'"'"'",
      "method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'"}' \
  --region $AWS_REGION 2>/dev/null || echo "OPTIONS integration response already exists"

# Grant API Gateway permission to invoke Lambda
echo "Granting API Gateway permission to invoke Lambda..."
aws lambda add-permission \
  --function-name $LAMBDA_FUNCTION_NAME \
  --statement-id "AllowAPIGatewayInvoke-$(date +%s)" \
  --action "lambda:InvokeFunction" \
  --principal "apigateway.amazonaws.com" \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):$REST_API_ID/*/*" \
  --region $AWS_REGION 2>/dev/null || echo "Permission already exists"

# Setup Lambda integration for GET
echo "Setting up Lambda integration for GET method..."
aws apigateway put-integration \
  --rest-api-id $REST_API_ID \
  --resource-id $MARKET_RESOURCE_ID \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:$AWS_REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):function:$LAMBDA_FUNCTION_NAME/invocations" \
  --region $AWS_REGION

# Deploy API Gateway
echo "Deploying API Gateway to 'prod' stage..."
aws apigateway create-deployment \
  --rest-api-id $REST_API_ID \
  --stage-name "prod" \
  --description "Market Data API Deployment" \
  --region $AWS_REGION

# Get invoke URL
INVOKE_URL="https://$REST_API_ID.execute-api.$AWS_REGION.amazonaws.com/prod/api/market-indices"

echo ""
echo "======================================"
echo "✅ Deployment Complete!"
echo "======================================"
echo ""
echo "Market Data API Endpoint:"
echo "$INVOKE_URL"
echo ""
echo "Test the endpoint:"
echo "curl $INVOKE_URL"
echo ""
echo "Update your frontend .env file with:"
echo "REACT_APP_MARKET_DATA_API=$INVOKE_URL"
echo ""

# Save to config file
mkdir -p config
cat > config/market_data_api.txt <<EOF
MARKET_DATA_API_URL=$INVOKE_URL
API_GATEWAY_ID=$REST_API_ID
LAMBDA_FUNCTION=$LAMBDA_FUNCTION_NAME
REGION=$AWS_REGION
DEPLOYED_AT=$(date)
EOF

echo "Configuration saved to config/market_data_api.txt"

# Cleanup
rm -rf lambda_market_data_package lambda_market_data.zip
echo "Cleanup complete!"

