#!/bin/bash

# Exit on error
set -e

# Variables
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
S3_BUCKET_NAME="ml-model-frontend-$AWS_ACCOUNT_ID"
API_GATEWAY_ID="${API_GATEWAY_ID:-0qoytg0cfg}"

# Set API Gateway URL for frontend
export REACT_APP_SPY_DATA_API="https://$API_GATEWAY_ID.execute-api.$AWS_REGION.amazonaws.com/prod/api/spy-data"
export REACT_APP_PREDICTION_API="https://$API_GATEWAY_ID.execute-api.$AWS_REGION.amazonaws.com/prod/predict"

echo "========================================="
echo "Deploying Frontend"
echo "========================================="
echo "S3 Bucket: $S3_BUCKET_NAME"
echo "SPY Data API: $REACT_APP_SPY_DATA_API"
echo "Prediction API: $REACT_APP_PREDICTION_API"
echo ""

echo "Checking for S3 bucket: $S3_BUCKET_NAME..."
if ! aws s3api head-bucket --bucket "$S3_BUCKET_NAME" >/dev/null 2>&1; then
  echo "Creating S3 bucket for frontend: $S3_BUCKET_NAME..."
  aws s3 mb s3://$S3_BUCKET_NAME --region $AWS_REGION
else
  echo "S3 bucket already exists."
fi

echo "Configuring S3 bucket for static website hosting..."
aws s3 website s3://$S3_BUCKET_NAME --index-document index.html --error-document index.html --region $AWS_REGION

echo "Disabling S3 Block Public Access for the bucket..."
aws s3api put-public-access-block \
    --bucket $S3_BUCKET_NAME \
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

echo "Setting S3 bucket policy to allow public read access..."
aws s3api put-bucket-policy \
  --bucket $S3_BUCKET_NAME \
  --policy file://<(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$S3_BUCKET_NAME/*"
        }
    ]
}
EOF
) \
  --region $AWS_REGION

echo "Building the React frontend application..."
cd frontend
npm install
REACT_APP_SPY_DATA_API=$REACT_APP_SPY_DATA_API REACT_APP_PREDICTION_API=$REACT_APP_PREDICTION_API npm run build
cd ..

echo "Uploading frontend build to S3 bucket..."
aws s3 cp frontend/build/ s3://$S3_BUCKET_NAME/ --recursive --region $AWS_REGION

echo "Frontend deployed to S3. Website URL:"
echo "http://$S_BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com"

echo "Invalidating CloudFront distribution..."
CLOUDFRONT_DISTRIBUTION_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?contains(Origins.Items[0].DomainName, '$S3_BUCKET_NAME')].Id" --output text | head -n 1 | awk '{print $1}')

if [ -z "$CLOUDFRONT_DISTRIBUTION_ID" ]; then
    echo "Could not find CloudFront distribution for bucket $S3_BUCKET_NAME."
    echo "Please run '06_setup_cloudfront.sh' first, then run this script again."
else
    echo "Found CloudFront distribution ID: $CLOUDFRONT_DISTRIBUTION_ID"
    aws cloudfront create-invalidation --distribution-id $CLOUDFRONT_DISTRIBUTION_ID --paths "/*"
    echo "CloudFront invalidation created successfully."
fi
