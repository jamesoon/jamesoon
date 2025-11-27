
# ML Model Deployment with GitHub Actions, ECR, and EKS

This project implements a complete CI/CD pipeline for deploying a machine learning model to AWS EKS using GitHub Actions. It includes real-time SPY price data from S3, ML-powered predictions, and a React frontend.

## 🚀 Quick Start

### Deploy SPY Data API (Real-Time Market Data)
```bash
bash scripts/deploy_spy_data_api.sh
```
This deploys a Lambda function that serves live SPY price data from your S3 bucket. See [QUICK_START_SPY_API.md](./QUICK_START_SPY_API.md) for details.

### Deploy Complete ML Pipeline
```bash
bash scripts/MASTER_DEPLOY.sh
```
This deploys the entire infrastructure: Docker→ECR→EKS→Lambda→API Gateway→Frontend.

### Test SPY Data API
```bash
curl https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/spy-data | jq .
```

## 📚 Documentation

- **[SPY_DATA_API_GUIDE.md](./SPY_DATA_API_GUIDE.md)** - Complete guide for SPY data API
- **[QUICK_START_SPY_API.md](./QUICK_START_SPY_API.md)** - Quick reference for SPY API
- **[START_HERE.md](./START_HERE.md)** - Main deployment guide
- **[DOCKER_DEPLOYMENT_GUIDE.md](./DOCKER_DEPLOYMENT_GUIDE.md)** - Docker deployment strategy

## Project Structure

- `ml_source/`: Contains the ML model (a simple scikit-learn Logistic Regression) and a Flask API for inference.
- `kubernetes/`: Kubernetes manifests for deploying the ML model to EKS.
- `scripts/`: Shell scripts for provisioning and tearing down AWS infrastructure.
- `.github/workflows/`: GitHub Actions workflow for CI/CD.
- `Dockerfile`: Dockerfile for containerizing the Flask application.

## Setup and Deployment Plan

### 1. AWS Account Configuration

Ensure you have an AWS account configured with the necessary permissions to create ECR repositories, EKS clusters, and IAM roles.

### 2. GitHub Repository Secrets

Add the following secrets to your GitHub repository:

- `AWS_ACCOUNT_ID`: Your AWS account ID.
- `AWS_ACCESS_KEY_ID`: AWS access key ID for a user with programmatic access.
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key for the above user.

**Note:** For production environments, it is highly recommended to use OpenID Connect (OIDC) with GitHub Actions for more secure AWS credential management, rather than storing `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` directly as GitHub secrets. The provided GitHub Actions workflow includes a placeholder for OIDC role assumption.

### 3. Provision AWS Infrastructure

Run the following scripts in order to provision the AWS infrastructure:

1.  **`00_setup_aws.sh`**: Prepares AWS environment (ECR repo, EKS cluster, IAM roles).
2.  **`01_create_model.sh`**: Trains and saves the machine learning model.
3.  **`02_initial_s3_data_load.py`**: Loads initial data to S3.
4.  **`03_build_candidate_container.sh`**: Builds the Docker container for the ML model.
5.  **`04_setup_aws_backend.sh`**: Sets up the backend infrastructure on AWS.
6.  **`05_deploy_to_aws.sh`**: Deploys the ML model to the EKS cluster.
7.  **`06_create_lambda_api_gateway.sh`**: Creates the Lambda function and API Gateway for predictions.
8.  **`07_deploy_market_data_lambda.sh`**: Deploys the market data Lambda function.
9.  **`08_test_market_data_api.sh`**: Tests the market data API endpoint.
10. **`09_build_and_deploy_frontend.sh`**: Builds the React app and deploys it to S3.
11. **`10_setup_cloudfront.sh`**: Creates a CloudFront distribution for the frontend.
12. **`11_setup_route53.sh`**: Configures Route 53 to point a domain to CloudFront.
13. **`12_get_cloudfront_info.sh`**: Utility script to retrieve current CloudFront details.

### 7. Teardown AWS Infrastructure

To remove all the AWS resources created by this project, run the `13_teardown_aws.sh` script:

```bash
bash scripts/teardown_aws.sh
```

This script will:
- Delete the EKS node group and cluster.
- Delete the ECR repository.
- Delete the associated IAM roles.
