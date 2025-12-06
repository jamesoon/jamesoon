#!/bin/bash

# Exit on error
set -e

# Variables
AWS_REGION="ap-southeast-1"
ECR_REPOSITORY_NAME="ml-model-repo"
EKS_CLUSTER_NAME="ml-model-cluster"
LAMBDA_FUNCTION_NAME="ml-model-predictor"

echo "Logging in to Amazon ECR..."
# Get ECR registry URL
ECR_REGISTRY=$(aws ecr describe-repositories --repository-names $ECR_REPOSITORY_NAME --region $AWS_REGION --query 'repositories[0].repositoryUri' --output text | cut -d'/' -f1)
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

if [ $? -ne 0 ]; then
    echo "Error: Failed to login to ECR."
    exit 1
fi

echo "Building, tagging, and pushing image to Amazon ECR..."
IMAGE_TAG=$(git rev-parse --short HEAD || date +%s) # Use git SHA or timestamp as tag
FULL_IMAGE_NAME="${ECR_REGISTRY}/${ECR_REPOSITORY_NAME}:${IMAGE_TAG}"

docker build -t $FULL_IMAGE_NAME .
docker push $FULL_IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "Error: Failed to build or push Docker image."
    exit 1
fi

echo "Updating Kubeconfig for EKS cluster: $EKS_CLUSTER_NAME..."
aws eks update-kubeconfig --name $EKS_CLUSTER_NAME --region $AWS_REGION

echo "Deploying to EKS..."
# Replace the image URI in the deployment.yaml
sed -i.bak "s|YOUR_ECR_REPOSITORY_URI:latest|${FULL_IMAGE_NAME}|g" k8s/deployment.yaml
# Apply Kubernetes manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

echo "Waiting for EKS deployment to be ready..."
kubectl rollout status deployment/ml-model-deployment

# Get the Load Balancer URL for the EKS service
echo "Getting EKS service Load Balancer URL..."
# Wait for the Load Balancer to be provisioned
ATTEMPTS=0
MAX_ATTEMPTS=30
LB_HOSTNAME=""
while [ -z "$LB_HOSTNAME" ] && [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    LB_HOSTNAME=$(kubectl get service ml-model-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    if [ -z "$LB_HOSTNAME" ]; then
        echo "Waiting for Load Balancer hostname... (Attempt $((ATTEMPTS+1)))/$MAX_ATTEMPTS)"
        sleep 10
        ATTEMPTS=$((ATTEMPTS+1))
    fi
done

if [ -z "$LB_HOSTNAME" ]; then
    echo "Error: Load Balancer hostname not found after multiple attempts."
    exit 1
fi

echo "EKS Service Load Balancer URL: http://$LB_HOSTNAME"

# Update Lambda function with EKS Load Balancer URL
echo "Updating Lambda function ($LAMBDA_FUNCTION_NAME) with EKS Load Balancer URL..."
# This assumes the Lambda function already exists and has an environment variable for the EKS endpoint
# The actual Lambda creation will be in 04_create_lambda_api_gateway.sh
aws lambda update-function-configuration \
  --function-name $LAMBDA_FUNCTION_NAME \
  --environment "Variables={EKS_ENDPOINT=http://$LB_HOSTNAME}" \
  --region $AWS_REGION

echo "Deployment to AWS (ECR, EKS, Lambda update) complete."
