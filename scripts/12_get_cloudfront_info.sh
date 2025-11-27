#!/bin/bash

# Exit on error
set -e

# Variables
S3_BUCKET_NAME="ml-model-frontend-$(aws sts get-caller-identity --query Account --output text)"

echo "Searching for CloudFront distribution linked to S3 bucket: $S3_BUCKET_NAME"

# Find the distribution ID
CLOUDFRONT_DISTRIBUTION_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?contains(Origins.Items[0].DomainName, '$S3_BUCKET_NAME')].Id" --output text | head -n 1 | awk '{print $1}')

if [ -z "$CLOUDFRONT_DISTRIBUTION_ID" ]; then
    echo "Error: Could not find a CloudFront distribution for the frontend S3 bucket: $S3_BUCKET_NAME"
    exit 1
fi

# Get distribution details
DISTRIBUTION_INFO=$(aws cloudfront get-distribution --id $CLOUDFRONT_DISTRIBUTION_ID)

CLOUDFRONT_DOMAIN_NAME=$(echo $DISTRIBUTION_INFO | jq -r '.Distribution.DomainName')
LAST_MODIFIED=$(echo $DISTRIBUTION_INFO | jq -r '.Distribution.LastModifiedTime')

echo ""
echo "--- Current CloudFront Details ---"
echo "S3 Origin Bucket: $S3_BUCKET_NAME"
echo "Distribution ID: $CLOUDFRONT_DISTRIBUTION_ID"
echo "CloudFront Domain: https://$CLOUDFRONT_DOMAIN_NAME"
echo "Last Modified: $LAST_MODIFIED"
echo "----------------------------------"
echo ""
echo "This is the 'new' or current version. For a rollback, you would need to redeploy a previous version of the frontend code."
