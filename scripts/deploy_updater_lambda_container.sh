#!/bin/bash
# Deploy Updater Lambda as a Docker Container Image
# This fetches data from Yahoo Finance and updates S3

set -e

AWS_REGION="${AWS_REGION:-ap-southeast-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FUNCTION_NAME="market-data-updater"
REPO_NAME="market-data-updater"
S3_BUCKET_NAME="${S3_BUCKET_NAME:-mdaie-prml-spy-bucket}"
S3_FILE_KEY="${S3_FILE_KEY:-market_data_normalized.parquet}"

echo "=========================================="
echo "Deploying Updater Lambda as Docker Image"
echo "=========================================="
echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo "Repository: $REPO_NAME"
echo ""

# 1. Create ECR Repository
echo "Step 1: Creating ECR Repository..."
aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION 2>/dev/null || echo "Repository already exists"

# 2. Login to ECR
echo "Step 2: Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 3. Create Dockerfile
echo "Step 3: Creating Dockerfile..."
BUILD_DIR=$(mktemp -d)
cp "/Users/jamesoon/Library/Mobile Documents/com~apple~CloudDocs/Desktop/PROJECTS/SUTD/MSTR-DAIE/MLOPS/Project/lambda_data_updater/lambda_function.py" $BUILD_DIR/

cat > $BUILD_DIR/Dockerfile <<EOF
FROM public.ecr.aws/lambda/python:3.11

# Install dependencies
RUN pip install pandas==2.1.4 yfinance>=0.2.40 boto3==1.34.10 pyarrow==14.0.1 requests

# Copy function code
COPY lambda_function.py \${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ]
EOF

# 4. Build and Push Image
echo "Step 4: Building and Pushing Docker Image..."
cd $BUILD_DIR
IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:latest"

docker build --platform linux/amd64 -t $REPO_NAME .
docker tag $REPO_NAME:latest $IMAGE_URI
docker push $IMAGE_URI

echo "Image pushed: $IMAGE_URI"

# 5. Create/Update Lambda Function
echo "Step 5: Creating/Updating Lambda Function..."

# Create IAM role if not exists
ROLE_NAME="lambda-market-data-updater-role"
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

ROLE_ARN=$(aws iam create-role \
    --role-name $ROLE_NAME \
    --assume-role-policy-document "$TRUST_POLICY" \
    --query 'Role.Arn' \
    --output text 2>/dev/null || \
    aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)

# Attach policies
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

# Create S3 read/write policy
S3_POLICY_NAME="lambda-market-data-s3-rw"
S3_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_NAME}",
        "arn:aws:s3:::${S3_BUCKET_NAME}/*"
      ]
    }
  ]
}
EOF
)

S3_POLICY_ARN=$(aws iam create-policy \
    --policy-name $S3_POLICY_NAME \
    --policy-document "$S3_POLICY" \
    --query 'Policy.Arn' \
    --output text 2>/dev/null || \
    aws iam list-policies --query "Policies[?PolicyName=='$S3_POLICY_NAME'].Arn" --output text)

aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn $S3_POLICY_ARN 2>/dev/null || true

# Wait for role propagation
sleep 10

if aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION &>/dev/null; then
    echo "Updating existing function..."
    # Check if existing function is Zip or Image
    PACKAGE_TYPE=$(aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION --query 'Configuration.PackageType' --output text)
    
    if [ "$PACKAGE_TYPE" == "Zip" ]; then
        echo "Deleting existing Zip function to replace with Image..."
        aws lambda delete-function --function-name $FUNCTION_NAME --region $AWS_REGION
        
        echo "Creating new function..."
        aws lambda create-function \
            --function-name $FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$IMAGE_URI \
            --role $ROLE_ARN \
            --timeout 300 \
            --memory-size 1024 \
            --environment "Variables={S3_BUCKET_NAME=$S3_BUCKET_NAME,S3_FILE_KEY=$S3_FILE_KEY}" \
            --region $AWS_REGION
    else
        aws lambda update-function-code \
            --function-name $FUNCTION_NAME \
            --image-uri $IMAGE_URI \
            --region $AWS_REGION
            
        aws lambda wait function-updated --function-name $FUNCTION_NAME --region $AWS_REGION
        
        aws lambda update-function-configuration \
            --function-name $FUNCTION_NAME \
            --environment "Variables={S3_BUCKET_NAME=$S3_BUCKET_NAME,S3_FILE_KEY=$S3_FILE_KEY}" \
            --timeout 300 \
            --memory-size 1024 \
            --region $AWS_REGION
    fi
else
    echo "Creating new function..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$IMAGE_URI \
        --role $ROLE_ARN \
        --timeout 300 \
        --memory-size 1024 \
        --environment "Variables={S3_BUCKET_NAME=$S3_BUCKET_NAME,S3_FILE_KEY=$S3_FILE_KEY}" \
        --region $AWS_REGION
fi

# 6. Set up EventBridge Schedule
echo "Step 6: Setting up EventBridge Schedule..."

RULE_NAME="daily-market-data-update"
# Run at 00:00 UTC daily (7 PM EST / 8 PM EDT - 3-4 hours after market close)
SCHEDULE_EXPRESSION="cron(0 0 * * ? *)"

echo "Creating EventBridge rule: $RULE_NAME with schedule: $SCHEDULE_EXPRESSION"
aws events put-rule \
    --name $RULE_NAME \
    --schedule-expression "$SCHEDULE_EXPRESSION" \
    --state ENABLED \
    --region $AWS_REGION

# Get Lambda ARN
FUNCTION_ARN=$(aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION --query 'Configuration.FunctionArn' --output text)

# Add permission for EventBridge to invoke Lambda
echo "Adding permission for EventBridge to invoke Lambda..."
aws lambda remove-permission --function-name $FUNCTION_NAME --statement-id EventBridgeInvoke 2>/dev/null || true
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id EventBridgeInvoke \
    --action 'lambda:InvokeFunction' \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:$AWS_REGION:$AWS_ACCOUNT_ID:rule/$RULE_NAME" \
    --region $AWS_REGION

# Add Lambda as target
echo "Adding Lambda as target..."
aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id"="1","Arn"="$FUNCTION_ARN" \
    --region $AWS_REGION

# Cleanup
rm -rf $BUILD_DIR

echo ""
echo "=========================================="
echo "✓ Updater Lambda Deployed & Scheduled!"
echo "=========================================="
echo "Function Name: $FUNCTION_NAME"
echo "Schedule: Daily at 00:00 UTC"
echo "Image URI: $IMAGE_URI"
echo ""

# Test the function (Dry run)
echo "Testing Lambda function (Dry run)..."
# We don't want to actually update data in test, but the handler will try.
# Just invoke it and see if it runs.
echo '{}' > /tmp/test-payload.json

aws lambda invoke \
    --function-name $FUNCTION_NAME \
    --region $AWS_REGION \
    --payload file:///tmp/test-payload.json \
    /tmp/market-data-response.json

echo ""
echo "Lambda Response:"
cat /tmp/market-data-response.json | jq .
echo ""
