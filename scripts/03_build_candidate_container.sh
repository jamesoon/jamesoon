#!/bin/bash
# Script to build the Docker image for the ML model

echo "Building Docker image for the ML model..."

# Get ECR registry from AWS CLI (assuming AWS credentials are configured)
# This is a placeholder, in a real CI/CD, this would come from the ECR login step
# For local testing, you might need to manually login to ECR first or configure AWS CLI
ECR_REGISTRY=$(aws ecr describe-repositories --repository-names ml-model-repo --query 'repositories[0].repositoryUri' --output text | cut -d'/' -f1)
if [ -z "$ECR_REGISTRY" ]; then
    echo "Error: Could not determine ECR registry. Please ensure 'ml-model-repo' exists and AWS CLI is configured."
    exit 1
fi

IMAGE_NAME="${ECR_REGISTRY}/ml-model-repo"
IMAGE_TAG="latest" # For local build, we can use 'latest', CI/CD will use SHA

docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

if [ $? -eq 0 ]; then
    echo "Docker image built successfully: ${IMAGE_NAME}:${IMAGE_TAG}"
else
    echo "Error building Docker image."
    exit 1
fi
