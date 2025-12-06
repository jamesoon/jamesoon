#!/bin/bash

# Exit on error
set -e

echo "Setting up core AWS infrastructure (ECR, EKS)..."
bash scripts/setup_aws.sh

# Variables
AWS_REGION="ap-southeast-1"
LAMBDA_ROLE_NAME="ml-api-lambda-role"
API_GATEWAY_ROLE_NAME="ml-api-gateway-role"
LAMBDA_FUNCTION_NAME="ml-model-predictor" # Placeholder for actual Lambda creation
API_GATEWAY_NAME="MLModelAPI" # Placeholder for actual API Gateway creation

# Create IAM role for Lambda function
echo "Creating IAM role for Lambda function: $LAMBDA_ROLE_NAME..."
LAMBDA_ROLE_ARN=$(aws iam create-role \
  --role-name $LAMBDA_ROLE_NAME \
  --assume-role-policy-document file://<(echo '{ \
    "Version": "2012-10-17", \
    "Statement": [ \
      { \
        "Effect": "Allow", \
        "Principal": { \
          "Service": "lambda.amazonaws.com" \
        }, \
        "Action": "sts:AssumeRole" \
      } \
    ] \
  }') \
  --query 'Role.Arn' --output text)

echo "Attaching policies to Lambda role..."
# Policy for Lambda to write logs to CloudWatch
aws iam attach-role-policy \
  --role-name $LAMBDA_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Policy for Lambda to invoke the EKS service (via Load Balancer)
# This policy grants broad access to EC2, which might be more than needed.
# In a production environment, this should be scoped down to specific resources.
aws iam attach-role-policy \
  --role-name $LAMBDA_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess # Placeholder, needs refinement for specific LB access

echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"

# Create IAM role for API Gateway to invoke Lambda
echo "Creating IAM role for API Gateway: $API_GATEWAY_ROLE_NAME..."
API_GATEWAY_ROLE_ARN=$(aws iam create-role \
  --role-name $API_GATEWAY_ROLE_NAME \
  --assume-role-policy-document file://<(echo '{ \
    "Version": "2012-10-17", \
    "Statement": [ \
      { \
        "Effect": "Allow", \
        "Principal": { \
          "Service": "apigateway.amazonaws.com" \
        }, \
        "Action": "sts:AssumeRole" \
      } \
    ] \
  }') \
  --query 'Role.Arn' --output text)

echo "Attaching policies to API Gateway role..."
# Policy for API Gateway to invoke the Lambda function
aws iam put-role-policy \
  --role-name $API_GATEWAY_ROLE_NAME \
  --policy-name InvokeLambdaPolicy \
  --policy-document file://<(echo '{ \
    "Version": "2012-10-17", \
    "Statement": [ \
      { \
        "Effect": "Allow", \
        "Action": "lambda:InvokeFunction", \
        "Resource": "arn:aws:lambda:'"$AWS_REGION"':"$(aws sts get-caller-identity --query Account --output text)":function:'"$LAMBDA_FUNCTION_NAME"'" \
      } \
    ] \
  }')

echo "API Gateway Role ARN: $API_GATEWAY_ROLE_ARN"

echo "AWS backend infrastructure setup complete (IAM roles for Lambda and API Gateway created)."
echo "Note: Actual Lambda function and API Gateway will be created in a subsequent script."
