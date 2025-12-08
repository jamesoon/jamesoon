#!/bin/bash
set -e

# Script to deploy Trading Backend with DynamoDB
# Cost: $0 (within free tier for low traffic)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_ROOT/config"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Configuration
FUNCTION_NAME="trading-backend"
TABLE_NAME="TradingApp"
REGION="ap-southeast-1"
RUNTIME="python3.11"
HANDLER="lambda_trading.lambda_handler"
API_NAME="trading-api"

echo "========================================="
echo "Trading Backend Deployment"
echo "========================================="
echo "DynamoDB Table: $TABLE_NAME"
echo "Lambda Function: $FUNCTION_NAME"
echo "API Gateway: $API_NAME"
echo "Region: $REGION"
echo "========================================="

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Step 1: Create DynamoDB Table (if it doesn't exist)
echo ""
echo "Step 1: Creating DynamoDB Table..."
echo "----------------------------------------"

if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "✓ DynamoDB table '$TABLE_NAME' already exists"
else
    echo "Creating DynamoDB table '$TABLE_NAME'..."
    aws dynamodb create-table \
        --table-name "$TABLE_NAME" \
        --attribute-definitions \
            AttributeName=userId,AttributeType=S \
            AttributeName=itemType,AttributeType=S \
        --key-schema \
            AttributeName=userId,KeyType=HASH \
            AttributeName=itemType,KeyType=RANGE \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION" \
        --tags Key=Project,Value=SUTD-PRML Key=Environment,Value=Production
    
    echo "Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$REGION"
    echo "✓ DynamoDB table created successfully"
fi

TABLE_ARN=$(aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" --query 'Table.TableArn' --output text)
echo "Table ARN: $TABLE_ARN"

# Step 2: Create or update IAM role for Lambda
echo ""
echo "Step 2: Setting up IAM Role..."
echo "----------------------------------------"

ROLE_NAME="lambda-trading-role"
TRUST_POLICY=$(cat <<EOF
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
)

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "✓ IAM role '$ROLE_NAME' already exists"
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
else
    echo "Creating IAM role '$ROLE_NAME'..."
    ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY" \
        --query 'Role.Arn' \
        --output text)
    
    echo "Waiting for role to propagate..."
    sleep 10
fi

echo "Role ARN: $ROLE_ARN"

# Attach basic Lambda execution policy
echo "Attaching Lambda execution policy..."
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
    2>/dev/null || echo "Policy already attached"

# Create and attach DynamoDB access policy
DYNAMODB_POLICY_NAME="lambda-trading-dynamodb-policy"
DYNAMODB_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "$TABLE_ARN"
    }
  ]
}
EOF
)

# Check if policy exists
POLICY_ARN=$(aws iam list-policies --query "Policies[?PolicyName=='$DYNAMODB_POLICY_NAME'].Arn" --output text 2>/dev/null)

if [ -z "$POLICY_ARN" ]; then
    echo "Creating DynamoDB access policy..."
    POLICY_ARN=$(aws iam create-policy \
        --policy-name "$DYNAMODB_POLICY_NAME" \
        --policy-document "$DYNAMODB_POLICY" \
        --query 'Policy.Arn' \
        --output text)
else
    echo "✓ DynamoDB policy already exists"
fi

echo "Attaching DynamoDB policy..."
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "$POLICY_ARN" \
    2>/dev/null || echo "Policy already attached"

echo "Waiting for IAM policies to propagate..."
sleep 10

# Step 3: Package Lambda function
echo ""
echo "Step 3: Packaging Lambda Function..."
echo "----------------------------------------"

PACKAGE_DIR="$BACKEND_DIR/package_trading"
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# Copy Lambda function
cp "$BACKEND_DIR/lambda_trading.py" "$PACKAGE_DIR/"

# Install dependencies if requirements exist
if [ -f "$BACKEND_DIR/requirements_trading.txt" ]; then
    echo "Installing Python dependencies for Linux x86_64..."
    python3 -m pip install \
        --platform manylinux2014_x86_64 \
        --target "$PACKAGE_DIR/" \
        --implementation cp \
        --python-version 3.11 \
        --only-binary=:all: \
        --upgrade \
        -r "$BACKEND_DIR/requirements_trading.txt"
fi

# Create deployment package
cd "$PACKAGE_DIR"
zip -r ../lambda_trading.zip . -q
cd "$PROJECT_ROOT"

echo "✓ Lambda package created: $BACKEND_DIR/lambda_trading.zip"

# Step 4: Create or update Lambda function
echo ""
echo "Step 4: Deploying Lambda Function..."
echo "----------------------------------------"

S3_BUCKET="mdaie-prml-spy-bucket"
S3_KEY="lambda_trading.zip"

echo "Uploading package to S3..."
aws s3 cp "$BACKEND_DIR/lambda_trading.zip" "s3://$S3_BUCKET/$S3_KEY"

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --s3-bucket "$S3_BUCKET" \
        --s3-key "$S3_KEY" \
        --region "$REGION"
    
    echo "Waiting for update to complete..."
    aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"
    
    echo "Updating function configuration..."
    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --handler "$HANDLER" \
        --environment "Variables={DYNAMODB_TABLE=$TABLE_NAME}" \
        --timeout 60 \
        --memory-size 512 \
        --region "$REGION"
else
    echo "Creating new Lambda function..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --code "S3Bucket=$S3_BUCKET,S3Key=$S3_KEY" \
        --environment "Variables={DYNAMODB_TABLE=$TABLE_NAME}" \
        --timeout 60 \
        --memory-size 512 \
        --region "$REGION"
fi

echo "Waiting for Lambda function to be ready..."
aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"
echo "✓ Lambda function deployed successfully"

FUNCTION_ARN=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --query 'Configuration.FunctionArn' --output text)
echo "Function ARN: $FUNCTION_ARN"

# Step 5: Create or update API Gateway
echo ""
echo "Step 5: Setting up API Gateway..."
echo "----------------------------------------"

# Check if API already exists
API_ID=$(aws apigatewayv2 get-apis --region "$REGION" --query "Items[?Name=='$API_NAME'].ApiId" --output text 2>/dev/null)

if [ -z "$API_ID" ] || [ "$API_ID" == "None" ]; then
    echo "Creating new HTTP API..."
    API_ID=$(aws apigatewayv2 create-api \
        --name "$API_NAME" \
        --protocol-type HTTP \
        --cors-configuration "AllowOrigins=*,AllowMethods=GET,POST,PUT,DELETE,OPTIONS,AllowHeaders=*" \
        --region "$REGION" \
        --query 'ApiId' \
        --output text)
    echo "✓ API created: $API_ID"
else
    echo "✓ Using existing API: $API_ID"
fi

API_ENDPOINT=$(aws apigatewayv2 get-api --api-id "$API_ID" --region "$REGION" --query 'ApiEndpoint' --output text)
echo "API Endpoint: $API_ENDPOINT"

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id "$API_ID" --region "$REGION" --query "Items[?IntegrationUri=='$FUNCTION_ARN'].IntegrationId" --output text 2>/dev/null)

if [ -z "$INTEGRATION_ID" ] || [ "$INTEGRATION_ID" == "None" ]; then
    echo "Creating Lambda integration..."
    INTEGRATION_ID=$(aws apigatewayv2 create-integration \
        --api-id "$API_ID" \
        --integration-type AWS_PROXY \
        --integration-uri "$FUNCTION_ARN" \
        --payload-format-version 2.0 \
        --region "$REGION" \
        --query 'IntegrationId' \
        --output text)
    echo "✓ Integration created: $INTEGRATION_ID"
else
    echo "✓ Using existing integration: $INTEGRATION_ID"
fi

# Create routes
ROUTES=(
    "GET /api/trading/health"
    "GET /health"
    "GET /api/trading/profile"
    "GET /api/trading/portfolio"
    "GET /api/trading/transactions"
    "POST /api/trading/buy"
    "POST /api/trading/sell"
    "POST /api/trading/sync"
    "GET /api/trading/metrics"
    "GET /api/reports/daily-matrix"
)

for ROUTE in "${ROUTES[@]}"; do
    METHOD=$(echo "$ROUTE" | cut -d' ' -f1)
    PATH=$(echo "$ROUTE" | cut -d' ' -f2)
    ROUTE_KEY="$METHOD $PATH"
    
    ROUTE_ID=$(aws apigatewayv2 get-routes --api-id "$API_ID" --region "$REGION" --query "Items[?RouteKey=='$ROUTE_KEY'].RouteId" --output text 2>/dev/null)
    
    if [ -z "$ROUTE_ID" ] || [ "$ROUTE_ID" == "None" ]; then
        echo "Creating route: $ROUTE_KEY"
        aws apigatewayv2 create-route \
            --api-id "$API_ID" \
            --route-key "$ROUTE_KEY" \
            --target "integrations/$INTEGRATION_ID" \
            --region "$REGION" \
    else
        echo "✓ Route exists: $ROUTE_KEY"
    fi
done

# Create $default stage (auto-deploy)
STAGE_NAME='$default'
if ! aws apigatewayv2 get-stage --api-id "$API_ID" --stage-name "$STAGE_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Creating default stage..."
    aws apigatewayv2 create-stage \
        --api-id "$API_ID" \
        --stage-name "$STAGE_NAME" \
        --auto-deploy \
        --region "$REGION"
fi

# Grant API Gateway permission to invoke Lambda
echo "Granting API Gateway invoke permission..."
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "apigateway-invoke-$API_ID" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:*:$API_ID/*/*" \
    --region "$REGION" \
    2>/dev/null || echo "Permission already exists"

echo "✓ API Gateway configured successfully"

# Step 6: Save configuration
echo ""
echo "Step 6: Saving Configuration..."
echo "----------------------------------------"

cat > "$CONFIG_DIR/trading_api.txt" << EOF
# Trading Backend API Configuration
# Generated: $(date)

TRADING_API_URL=$API_ENDPOINT
API_ID=$API_ID
FUNCTION_NAME=$FUNCTION_NAME
FUNCTION_ARN=$FUNCTION_ARN
TABLE_NAME=$TABLE_NAME
TABLE_ARN=$TABLE_ARN
REGION=$REGION
DEPLOYED_AT=$(date -Iseconds)
EOF

echo "✓ Configuration saved to: $CONFIG_DIR/trading_api.txt"

# Step 7: Test the API
echo ""
echo "Step 7: Testing API..."
echo "----------------------------------------"

echo "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s "$API_ENDPOINT/api/trading/health")
echo "Response: $HEALTH_RESPONSE"

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "✅ Health check passed!"
else
    echo "⚠️  Health check failed - API may need a moment to fully deploy"
fi

# Cleanup
echo ""
echo "Cleaning up temporary files..."
rm -rf "$PACKAGE_DIR"
rm -f "$BACKEND_DIR/lambda_trading.zip"

# Final summary
echo ""
echo "========================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "========================================="
echo ""
echo "📊 DynamoDB Table: $TABLE_NAME"
echo "📦 Lambda Function: $FUNCTION_NAME"
echo "🌐 API Endpoint: $API_ENDPOINT"
echo ""
echo "📝 API Endpoints:"
echo "  - GET  $API_ENDPOINT/api/trading/health"
echo "  - GET  $API_ENDPOINT/api/trading/profile"
echo "  - GET  $API_ENDPOINT/api/trading/portfolio"
echo "  - GET  $API_ENDPOINT/api/trading/transactions"
echo "  - POST $API_ENDPOINT/api/trading/buy"
echo "  - POST $API_ENDPOINT/api/trading/sell"
echo "  - POST $API_ENDPOINT/api/trading/sync"
echo ""
echo "💰 Cost Estimate:"
echo "  - DynamoDB: FREE (within free tier for <25GB & low traffic)"
echo "  - Lambda: FREE (within 1M free requests/month)"
echo "  - API Gateway: FREE (within 1M free requests/month)"
echo "  - Total: $0.00/month (for typical usage)"
echo ""
echo "🔧 Next Steps:"
echo "  1. Update frontend .env with: REACT_APP_TRADING_API=$API_ENDPOINT"
echo "  2. Run: ./scripts/09_build_and_deploy_frontend.sh"
echo "  3. Test: ./scripts/08.1_test_trading_api.sh"
echo ""
echo "========================================="

