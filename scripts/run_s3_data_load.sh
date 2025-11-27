#!/bin/bash

# Helper script to run the S3 data load with proper setup

set -e

echo "=========================================="
echo "S3 Market Data Initial Load"
echo "=========================================="
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "✗ Error: python3 not found. Please install Python 3."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "✗ Error: AWS credentials not configured."
    echo "  Run: aws configure"
    exit 1
fi

echo "✓ AWS credentials configured"
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "  Account: $AWS_ACCOUNT"

# Get or prompt for bucket name
if [ -z "$S3_BUCKET_NAME" ]; then
    echo ""
    read -p "Enter S3 bucket name (or press Enter for default): " BUCKET_NAME
    if [ -z "$BUCKET_NAME" ]; then
        BUCKET_NAME="your-market-data-bucket"
        echo "Using default: $BUCKET_NAME"
    fi
else
    BUCKET_NAME="$S3_BUCKET_NAME"
    echo "Using bucket from environment: $BUCKET_NAME"
fi

# Check if bucket exists
if aws s3 ls "s3://$BUCKET_NAME" &> /dev/null; then
    echo "✓ Bucket exists: $BUCKET_NAME"
else
    echo ""
    echo "⚠ Bucket does not exist: $BUCKET_NAME"
    read -p "Create it now? (y/n): " CREATE_BUCKET
    if [ "$CREATE_BUCKET" = "y" ] || [ "$CREATE_BUCKET" = "Y" ]; then
        AWS_REGION=$(aws configure get region || echo "ap-southeast-1")
        echo "Creating bucket in region: $AWS_REGION"
        aws s3 mb "s3://$BUCKET_NAME" --region "$AWS_REGION"
        echo "✓ Bucket created"
    else
        echo "✗ Please create the bucket first:"
        echo "  aws s3 mb s3://$BUCKET_NAME --region ap-southeast-1"
        exit 1
    fi
fi

# Check if required Python packages are installed
echo ""
echo "Checking Python dependencies..."
MISSING_PACKAGES=()

python3 -c "import boto3" 2>/dev/null || MISSING_PACKAGES+=("boto3")
python3 -c "import pandas" 2>/dev/null || MISSING_PACKAGES+=("pandas")
python3 -c "import yfinance" 2>/dev/null || MISSING_PACKAGES+=("yfinance")
python3 -c "import pyarrow" 2>/dev/null || MISSING_PACKAGES+=("pyarrow")

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "⚠ Missing packages: ${MISSING_PACKAGES[*]}"
    read -p "Install missing packages? (y/n): " INSTALL
    if [ "$INSTALL" = "y" ] || [ "$INSTALL" = "Y" ]; then
        echo "Installing packages..."
        pip3 install "${MISSING_PACKAGES[@]}"
        echo "✓ Packages installed"
    else
        echo "✗ Please install missing packages:"
        echo "  pip3 install ${MISSING_PACKAGES[*]}"
        exit 1
    fi
else
    echo "✓ All dependencies installed"
fi

# Run the script
echo ""
echo "=========================================="
echo "Running data load script..."
echo "=========================================="
echo ""

export S3_BUCKET_NAME="$BUCKET_NAME"
python3 scripts/02_initial_s3_data_load.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Success!"
    echo "=========================================="
    echo ""
    echo "Data uploaded to: s3://$BUCKET_NAME/market-data/latest.parquet"
    echo ""
    echo "Next steps:"
    echo "1. Deploy Lambda updater for daily updates"
    echo "2. Update EKS service to use S3 data"
else
    echo ""
    echo "=========================================="
    echo "❌ Failed with exit code: $EXIT_CODE"
    echo "=========================================="
    exit $EXIT_CODE
fi

