#!/bin/bash
set -e

# Configuration
AWS_REGION="ap-southeast-1"
FUNCTION_NAME="prediction-proxy"
API_NAME="MarketDataAPI" # Reuse existing API
STAGE_NAME="prod"
ECR_REPO_NAME="prediction-service"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

echo "=========================================="
echo "Creating Prediction API (Lambda + API Gateway)"
echo "Function: ${FUNCTION_NAME}"
echo "Image: ${IMAGE_URI}"
echo "=========================================="

# 1. Create/Update Lambda Function
echo "Checking Lambda function..."
if aws lambda get-function --function-name ${FUNCTION_NAME} --region ${AWS_REGION} > /dev/null 2>&1; then
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name ${FUNCTION_NAME} \
        --image-uri ${IMAGE_URI} \
        --region ${AWS_REGION}
        
    # Update configuration with environment variables
    # (Optional) Add other env vars here if needed
    # aws lambda update-function-configuration ...
else
    echo "Creating new function..."
    # Create Role if not exists
    ROLE_NAME="lambda-prediction-role"
    if ! aws iam get-role --role-name ${ROLE_NAME} > /dev/null 2>&1; then
        echo "Creating IAM role..."
        aws iam create-role --role-name ${ROLE_NAME} --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }'
        aws iam attach-role-policy --role-name ${ROLE_NAME} --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        
        # Add S3 access for market data
        aws iam attach-role-policy --role-name ${ROLE_NAME} --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
        
        sleep 10 # Wait for propagation
    fi
    ROLE_ARN=$(aws iam get-role --role-name ${ROLE_NAME} --query Role.Arn --output text)

    aws lambda create-function \
        --function-name ${FUNCTION_NAME} \
        --package-type Image \
        --code ImageUri=${IMAGE_URI} \
        --role ${ROLE_ARN} \
        --timeout 60 \
        --memory-size 1024 \
        --region ${AWS_REGION}
fi

# 2. Configure API Gateway
echo "Configuring API Gateway..."
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='${API_NAME}'].id" --output text --region ${AWS_REGION})

if [ -z "$API_ID" ]; then
    echo "Error: API '${API_NAME}' not found. Please deploy the SPY Data API first."
    exit 1
fi

echo "Found API ID: ${API_ID}"

# Get Root Resource ID
ROOT_ID=$(aws apigateway get-resources --rest-api-id ${API_ID} --query "items[?path=='/'].id" --output text --region ${AWS_REGION})

# Create /predict resource
PREDICT_ID=$(aws apigateway get-resources --rest-api-id ${API_ID} --query "items[?path=='/predict'].id" --output text --region ${AWS_REGION})
if [ -z "$PREDICT_ID" ]; then
    echo "Creating /predict resource..."
    PREDICT_ID=$(aws apigateway create-resource --rest-api-id ${API_ID} --parent-id ${ROOT_ID} --path-part predict --query id --output text --region ${AWS_REGION})
fi

# Create /health resource
HEALTH_ID=$(aws apigateway get-resources --rest-api-id ${API_ID} --query "items[?path=='/health'].id" --output text --region ${AWS_REGION})
if [ -z "$HEALTH_ID" ]; then
    echo "Creating /health resource..."
    HEALTH_ID=$(aws apigateway create-resource --rest-api-id ${API_ID} --parent-id ${ROOT_ID} --path-part health --query id --output text --region ${AWS_REGION})
fi

# Create POST method for /predict
echo "Creating POST method for /predict..."
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${PREDICT_ID} \
    --http-method POST \
    --authorization-type NONE \
    --region ${AWS_REGION} || true

# Create GET method for /health
echo "Creating GET method for /health..."
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${HEALTH_ID} \
    --http-method GET \
    --authorization-type NONE \
    --region ${AWS_REGION} || true

# Integrate /predict with Lambda
echo "Integrating /predict with Lambda..."
LAMBDA_ARN=$(aws lambda get-function --function-name ${FUNCTION_NAME} --query Configuration.FunctionArn --output text --region ${AWS_REGION})
aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${PREDICT_ID} \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations \
    --region ${AWS_REGION}

# Integrate /health with Lambda
echo "Integrating /health with Lambda..."
aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${HEALTH_ID} \
    --http-method GET \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations \
    --region ${AWS_REGION}

# Create /api/model/drift resources
echo "Configuring /api/model/drift..."

# 1. Create /api
API_RESOURCE_ID=$(aws apigateway get-resources --rest-api-id ${API_ID} --query "items[?path=='/api'].id" --output text --region ${AWS_REGION})
if [ -z "$API_RESOURCE_ID" ]; then
    echo "Creating /api resource..."
    API_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id ${API_ID} --parent-id ${ROOT_ID} --path-part api --query id --output text --region ${AWS_REGION})
fi

# 2. Create /api/model
MODEL_RESOURCE_ID=$(aws apigateway get-resources --rest-api-id ${API_ID} --query "items[?path=='/api/model'].id" --output text --region ${AWS_REGION})
if [ -z "$MODEL_RESOURCE_ID" ]; then
    echo "Creating /api/model resource..."
    MODEL_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id ${API_ID} --parent-id ${API_RESOURCE_ID} --path-part model --query id --output text --region ${AWS_REGION})
fi

# 3. Create /api/model/drift
DRIFT_RESOURCE_ID=$(aws apigateway get-resources --rest-api-id ${API_ID} --query "items[?path=='/api/model/drift'].id" --output text --region ${AWS_REGION})
if [ -z "$DRIFT_RESOURCE_ID" ]; then
    echo "Creating /api/model/drift resource..."
    DRIFT_RESOURCE_ID=$(aws apigateway create-resource --rest-api-id ${API_ID} --parent-id ${MODEL_RESOURCE_ID} --path-part drift --query id --output text --region ${AWS_REGION})
fi

# 4. Create GET method for /api/model/drift
echo "Creating GET method for /api/model/drift..."
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${DRIFT_RESOURCE_ID} \
    --http-method GET \
    --authorization-type NONE \
    --region ${AWS_REGION} || true

# 5. Integrate with Lambda
echo "Integrating /api/model/drift with Lambda..."
aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${DRIFT_RESOURCE_ID} \
    --http-method GET \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations \
    --region ${AWS_REGION}

# 6. Add CORS for /api/model/drift
echo "Adding CORS for /api/model/drift..."
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${DRIFT_RESOURCE_ID} \
    --http-method OPTIONS \
    --authorization-type NONE \
    --region ${AWS_REGION} || true

aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${DRIFT_RESOURCE_ID} \
    --http-method OPTIONS \
    --type MOCK \
    --request-templates '{"application/json":"{\"statusCode\": 200}"}' \
    --region ${AWS_REGION}

aws apigateway put-method-response \
    --rest-api-id ${API_ID} \
    --resource-id ${DRIFT_RESOURCE_ID} \
    --http-method OPTIONS \
    --status-code 200 \
    --response-models '{"application/json": "Empty"}' \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": true, "method.response.header.Access-Control-Allow-Methods": true, "method.response.header.Access-Control-Allow-Origin": true}' \
    --region ${AWS_REGION} || true

aws apigateway put-integration-response \
    --rest-api-id ${API_ID} \
    --resource-id ${DRIFT_RESOURCE_ID} \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": "'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'", "method.response.header.Access-Control-Allow-Methods": "'"'GET,OPTIONS'"'", "method.response.header.Access-Control-Allow-Origin": "'"'*'"'"}' \
    --region ${AWS_REGION} || true

# 7. Grant permission
aws lambda add-permission \
    --function-name ${FUNCTION_NAME} \
    --statement-id apigateway-drift-$(date +%s) \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*/api/model/drift" \
    --region ${AWS_REGION} || true

# Add CORS for /predict
echo "Adding CORS for /predict..."
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${PREDICT_ID} \
    --http-method OPTIONS \
    --authorization-type NONE \
    --region ${AWS_REGION} || true

aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${PREDICT_ID} \
    --http-method OPTIONS \
    --type MOCK \
    --request-templates '{"application/json":"{\"statusCode\": 200}"}' \
    --region ${AWS_REGION}

aws apigateway put-method-response \
    --rest-api-id ${API_ID} \
    --resource-id ${PREDICT_ID} \
    --http-method OPTIONS \
    --status-code 200 \
    --response-models '{"application/json": "Empty"}' \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": true, "method.response.header.Access-Control-Allow-Methods": true, "method.response.header.Access-Control-Allow-Origin": true}' \
    --region ${AWS_REGION} || true

aws apigateway put-integration-response \
    --rest-api-id ${API_ID} \
    --resource-id ${PREDICT_ID} \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": "'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'", "method.response.header.Access-Control-Allow-Methods": "'"'POST,OPTIONS'"'", "method.response.header.Access-Control-Allow-Origin": "'"'*'"'"}' \
    --region ${AWS_REGION} || true

# Add CORS for /health
echo "Adding CORS for /health..."
aws apigateway put-method \
    --rest-api-id ${API_ID} \
    --resource-id ${HEALTH_ID} \
    --http-method OPTIONS \
    --authorization-type NONE \
    --region ${AWS_REGION} || true

aws apigateway put-integration \
    --rest-api-id ${API_ID} \
    --resource-id ${HEALTH_ID} \
    --http-method OPTIONS \
    --type MOCK \
    --request-templates '{"application/json":"{\"statusCode\": 200}"}' \
    --region ${AWS_REGION}

aws apigateway put-method-response \
    --rest-api-id ${API_ID} \
    --resource-id ${HEALTH_ID} \
    --http-method OPTIONS \
    --status-code 200 \
    --response-models '{"application/json": "Empty"}' \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": true, "method.response.header.Access-Control-Allow-Methods": true, "method.response.header.Access-Control-Allow-Origin": true}' \
    --region ${AWS_REGION} || true

aws apigateway put-integration-response \
    --rest-api-id ${API_ID} \
    --resource-id ${HEALTH_ID} \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": "'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'", "method.response.header.Access-Control-Allow-Methods": "'"'GET,OPTIONS'"'", "method.response.header.Access-Control-Allow-Origin": "'"'*'"'"}' \
    --region ${AWS_REGION} || true

# Grant permission to API Gateway to invoke Lambda
echo "Granting permissions..."
aws lambda add-permission \
    --function-name ${FUNCTION_NAME} \
    --statement-id apigateway-predict-$(date +%s) \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*/predict" \
    --region ${AWS_REGION} || true

aws lambda add-permission \
    --function-name ${FUNCTION_NAME} \
    --statement-id apigateway-health-$(date +%s) \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*/health" \
    --region ${AWS_REGION} || true

# Deploy API
echo "Deploying API..."
aws apigateway create-deployment \
    --rest-api-id ${API_ID} \
    --stage-name ${STAGE_NAME} \
    --region ${AWS_REGION}

echo "=========================================="
echo "API Deployed!"
echo "Endpoint: https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${STAGE_NAME}/predict"
echo "=========================================="
