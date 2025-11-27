#!/bin/bash

# Exit on error
set -e

# Variables
AWS_REGION="ap-southeast-1"
S3_BUCKET_NAME="ml-model-frontend-$(aws sts get-caller-identity --query Account --output text)"

echo "Creating CloudFront distribution..."

CALLER_REFERENCE=$(date +%s)
# Substitute variables in the JSON file
sed -e "s/\$S3_BUCKET_NAME/$S3_BUCKET_NAME/g" \
    -e "s/\$AWS_REGION/$AWS_REGION/g" \
    -e "s/\$CALLER_REFERENCE/$CALLER_REFERENCE/g" \
    cloudfront_config.json > cloudfront_config_final.json

DISTRIBUTION_INFO=$(aws cloudfront create-distribution \
  --distribution-config file://cloudfront_config_final.json \
  --query 'Distribution' \
  --output json)

DISTRIBUTION_ID=$(echo $DISTRIBUTION_INFO | jq -r '.Id')
DISTRIBUTION_DOMAIN=$(echo $DISTRIBUTION_INFO | jq -r '.DomainName')

echo "CloudFront distribution created."
echo "Distribution ID: $DISTRIBUTION_ID"
echo "Distribution Domain: https://$DISTRIBUTION_DOMAIN"

echo "Waiting for distribution to be deployed... (This can take several minutes)"
aws cloudfront wait distribution-deployed --id $DISTRIBUTION_ID

echo "CloudFront distribution deployed successfully."
