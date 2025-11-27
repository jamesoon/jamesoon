#!/bin/bash

# Exit on error
set -e

# Variables
AWS_REGION="ap-southeast-1"
LAMBDA_FUNCTION_NAME="ml-model-predictor"
LAMBDA_ROLE_NAME="ml-api-lambda-role"
API_GATEWAY_NAME="MLModelAPI"
API_GATEWAY_RESOURCE_PATH="/predict"
API_GATEWAY_METHOD="POST"

# Get Lambda Role ARN
LAMBDA_ROLE_ARN=$(aws iam get-role --role-name $LAMBDA_ROLE_NAME --query 'Role.Arn' --output text)
if [ -z "$LAMBDA_ROLE_ARN" ]; then
    echo "Error: Lambda role $LAMBDA_ROLE_NAME not found. Run 02_setup_aws_backend.sh first."
    exit 1
fi

echo "Packaging Lambda function..."
# Create a temporary directory for packaging
mkdir -p lambda_package
# Install dependencies into the temporary directory
pip install --target lambda_package -r lambda_proxy/requirements.txt
# Copy the lambda_function.py into the package
cp lambda_proxy/lambda_function.py lambda_package/
# Zip the contents
cd lambda_package
zip -r ../lambda_function.zip .
cd ..
rm -rf lambda_package

echo "Creating Lambda function: $LAMBDA_FUNCTION_NAME..."
# Create Lambda function
aws lambda create-function \
  --function-name $LAMBDA_FUNCTION_NAME \
  --runtime python3.9 \
  --role $LAMBDA_ROLE_ARN \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --environment "Variables={EKS_ENDPOINT=http://localhost:5000}" \
  --timeout 30 \
  --memory-size 128 \
  --region $AWS_REGION

echo "Creating API Gateway: $API_GATEWAY_NAME..."
# Create REST API
REST_API_ID=$(aws apigateway create-rest-api \
  --name $API_GATEWAY_NAME \
  --description "API Gateway for ML Model Prediction" \
  --query 'id' --output text \
  --region $AWS_REGION)

echo "API Gateway ID: $REST_API_ID"

# Get root resource ID
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $REST_API_ID \
  --query 'items[?path==`/`].id' --output text \
  --region $AWS_REGION)

echo "Root Resource ID: $ROOT_RESOURCE_ID"

# Create /predict resource
PREDICT_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $REST_API_ID \
  --parent-id $ROOT_RESOURCE_ID \
  --path-part "predict" \
  --query 'id' --output text \
  --region $AWS_REGION)

echo "/predict Resource ID: $PREDICT_RESOURCE_ID"

# Grant API Gateway permission to invoke Lambda
echo "Granting API Gateway permission to invoke Lambda..."
aws lambda add-permission \
  --function-name $LAMBDA_FUNCTION_NAME \
  --statement-id "AllowAPIGatewayInvoke" \
  --action "lambda:InvokeFunction" \
  --principal "apigateway.amazonaws.com" \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):$REST_API_ID/*/$API_GATEWAY_METHOD$API_GATEWAY_RESOURCE_PATH" \
  --region $AWS_REGION

# Set up integration with Lambda function
echo "Setting up integration for $API_GATEWAY_METHOD $API_GATEWAY_RESOURCE_PATH with Lambda..."
aws apigateway put-method \
  --rest-api-id $REST_API_ID \
  --resource-id $PREDICT_RESOURCE_ID \
  --http-method $API_GATEWAY_METHOD \
  --authorization-type "NONE" \
  --region $AWS_REGION

aws apigateway put-integration \
  --rest-api-id $REST_API_ID \
  --resource-id $PREDICT_RESOURCE_ID \
  --http-method $API_GATEWAY_METHOD \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:$AWS_REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):function:$LAMBDA_FUNCTION_NAME/invocations" \
  --region $AWS_REGION

# Deploy API Gateway
echo "Deploying API Gateway..."
aws apigateway create-deployment \
  --rest-api-id $REST_API_ID \
  --stage-name "prod" \
  --description "Production Deployment" \
  --region $AWS_REGION

echo "API Gateway setup complete. Invoke URL:"
aws apigateway get-rest-apis --query "items[?name=='$API_GATEWAY_NAME'].{id:id}" --output text --region $AWS_REGION | xargs -I {} echo "https://{{}}.execute-api.$AWS_REGION.amazonaws.com/prod$API_GATEWAY_RESOURCE_PATH"

echo "Remember to update the Lambda function's EKS_ENDPOINT environment variable after EKS deployment."
