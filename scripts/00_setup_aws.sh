#!/bin/bash

# Exit on error
set -e

# Variables
AWS_REGION="ap-southeast-1"
ECR_REPOSITORY_NAME="ml-model-repo"
EKS_CLUSTER_NAME="ml-model-cluster"
EKS_NODE_GROUP_NAME="ml-model-nodegroup"
EKS_NODE_INSTANCE_TYPE="t2.medium"
EKS_NODE_COUNT=2

# Create ECR repository
echo "Checking for ECR repository..."
if ! aws ecr describe-repositories --repository-names $ECR_REPOSITORY_NAME --region $AWS_REGION >/dev/null 2>&1; then
  echo "Creating ECR repository..."
  aws ecr create-repository --repository-name $ECR_REPOSITORY_NAME --region $AWS_REGION
else
  echo "ECR repository already exists."
fi

# Create EKS cluster role
echo "Checking for EKS cluster role..."
if ! aws iam get-role --role-name $EKS_CLUSTER_NAME-role >/dev/null 2>&1; then
  echo "Creating EKS cluster role..."
  CLUSTER_ROLE_ARN=$(aws iam create-role --role-name $EKS_CLUSTER_NAME-role --assume-role-policy-document file://<(echo '{ "Version": "2012-10-17", "Statement": [ { "Effect": "Allow", "Principal": { "Service": "eks.amazonaws.com" }, "Action": "sts:AssumeRole" } ] }') --query 'Role.Arn' --output text)
  aws iam attach-role-policy --role-name $EKS_CLUSTER_NAME-role --policy-arn arn:aws:iam::aws:policy/AmazonEKSClusterPolicy
else
  echo "EKS cluster role already exists."
  CLUSTER_ROLE_ARN=$(aws iam get-role --role-name $EKS_CLUSTER_NAME-role --query 'Role.Arn' --output text)
fi

# Create EKS node group role
echo "Checking for EKS node group role..."
if ! aws iam get-role --role-name $EKS_NODE_GROUP_NAME-role >/dev/null 2>&1; then
  echo "Creating EKS node group role..."
  NODE_GROUP_ROLE_ARN=$(aws iam create-role --role-name $EKS_NODE_GROUP_NAME-role --assume-role-policy-document file://<(echo '{ "Version": "2012-10-17", "Statement": [ { "Effect": "Allow", "Principal": { "Service": "ec2.amazonaws.com" }, "Action": "sts:AssumeRole" } ] }') --query 'Role.Arn' --output text)
  aws iam attach-role-policy --role-name $EKS_NODE_GROUP_NAME-role --policy-arn arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
  aws iam attach-role-policy --role-name $EKS_NODE_GROUP_NAME-role --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
  aws iam attach-role-policy --role-name $EKS_NODE_GROUP_NAME-role --policy-arn arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
else
  echo "EKS node group role already exists."
  NODE_GROUP_ROLE_ARN=$(aws iam get-role --role-name $EKS_NODE_GROUP_NAME-role --query 'Role.Arn' --output text)
fi

# Create EKS cluster
echo "Creating EKS cluster..."
aws eks create-cluster \
  --region $AWS_REGION \
  --name $EKS_CLUSTER_NAME \
  --role-arn $CLUSTER_ROLE_ARN \
  --resources-vpc-config "subnetIds=$(aws ec2 describe-subnets --query 'Subnets[?MapPublicIpOnLaunch].SubnetId' --output text | tr '\t' ','),securityGroupIds=$(aws ec2 describe-security-groups --group-names 'default' --query 'SecurityGroups[0].GroupId' --output text)"

echo "Waiting for EKS cluster to be active..."
aws eks wait cluster-active --name $EKS_CLUSTER_NAME --region $AWS_REGION

# Create EKS node group
echo "Creating EKS node group..."
aws eks create-nodegroup \
  --region $AWS_REGION \
  --cluster-name $EKS_CLUSTER_NAME \
  --nodegroup-name $EKS_NODE_GROUP_NAME \
  --node-role $NODE_GROUP_ROLE_ARN \
  --instance-types $EKS_NODE_INSTANCE_TYPE \
  --scaling-config minSize=1,maxSize=$EKS_NODE_COUNT,desiredSize=$EKS_NODE_COUNT \
  --subnets $(aws ec2 describe-subnets --query 'Subnets[?MapPublicIpOnLaunch].SubnetId' --output text | tr ' ' ',')

echo "Waiting for EKS node group to be active..."
aws eks wait nodegroup-active --cluster-name $EKS_CLUSTER_NAME --nodegroup-name $EKS_NODE_GROUP_NAME --region $AWS_REGION

echo "AWS infrastructure setup complete."

echo ""
echo "======================================"
echo "Optional: Deploy Market Data Lambda"
echo "======================================"
echo "To deploy the real-time market data API, run:"
echo "./scripts/07_deploy_market_data_lambda.sh"
echo ""
