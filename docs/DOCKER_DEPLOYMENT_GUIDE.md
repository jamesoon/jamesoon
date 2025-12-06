# Docker Deployment Guide - Dual Registry Strategy

## Architecture Overview

Based on the PRML Finance Projection MODE architecture:

```
Notebook Development → Docker → DockerHub (Backup) → AWS ECR (Deployment) → EKS
```

### Dual Registry Strategy

1. **DockerHub** (`jamezoon/ml-model-spy`)
   - Purpose: Backup, sharing, version control
   - Public/private: Your choice
   - Benefits: Easy sharing, version history, free storage

2. **AWS ECR** (`{account-id}.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo`)
   - Purpose: Production deployment to EKS
   - Private: Yes (AWS managed)
   - Benefits: Low latency, AWS integration, security

## Quick Start

### Option 1: Build and Push Only (Standalone)
```bash
# Build, test, and push to both DockerHub and ECR
bash scripts/04-build_candidate_container.sh
```

### Option 2: Full Deployment (Includes Build + Deploy)
```bash
# Complete deployment pipeline
bash scripts/11-deploy_prediction_lambda.sh
```

## Detailed Workflow

### Step 1: Prerequisites

```bash
# 1. Configure AWS credentials
aws configure

# 2. Login to DockerHub (optional, for backup)
docker login -u jamezoon

# 3. Verify S3 bucket exists
aws s3 ls s3://mdaie-prml-spy-bucket/

# 4. Ensure model files exist
ls -l ml_source/model.pkl
ls -l ml_source/app.py
```

### Step 2: Build and Push

```bash
# Navigate to project root
cd /Users/jamesoon/Library/Mobile\ Documents/com~apple~CloudDocs/Desktop/PROJECTS/SUTD/MSTR-DAIE/MLOPS/Project

# Run build script
bash scripts/04-build_candidate_container.sh
```

**What this does:**
1. ✅ Builds Docker image
2. ✅ Tests container locally (health check + prediction)
3. ✅ Pushes to DockerHub: `jamezoon/ml-model-spy:latest`
4. ✅ Creates ECR repository (if needed)
5. ✅ Pushes to ECR: `{account}.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo:latest`

### Step 3: Deploy to EKS

```bash
# Full deployment
bash scripts/11-deploy_prediction_lambda.sh
```

This will:
- Use the ECR image (not DockerHub) for deployment
- Create EKS cluster
- Deploy to Kubernetes
- Setup Lambda proxy
- Configure API Gateway

## Image Tags

Both registries use the same tagging strategy:

```bash
# Latest (for deployment)
latest

# Timestamp (for rollback)
20251124-143000
```

### DockerHub Images
```bash
jamezoon/ml-model-spy:latest
jamezoon/ml-model-spy:20251124-143000
```

### ECR Images
```bash
{account-id}.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo:latest
{account-id}.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo:20251124-143000
```

## Manual Operations

### Build Only
```bash
docker build -t ml-model:latest .
```

### Test Locally
```bash
docker run -d -p 5001:5000 \
  -e S3_BUCKET_NAME=mdaie-prml-spy-bucket \
  -e AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id) \
  -e AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key) \
  -e AWS_REGION=ap-southeast-1 \
  ml-model:latest

# Test endpoints
curl http://localhost:5001/healthcheck
curl -X POST http://localhost:5001/predict \
  -H "Content-Type: application/json" \
  -d '{"ticker":"SPY"}'
```

### Push to DockerHub Only
```bash
docker login -u jamezoon
docker tag ml-model:latest jamezoon/ml-model-spy:latest
docker push jamezoon/ml-model-spy:latest
```

### Push to ECR Only
```bash
# Get account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO_URI="$AWS_ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo"

# Create ECR repo (if needed)
aws ecr create-repository \
  --repository-name ml-model-repo \
  --region ap-southeast-1

# Login to ECR
aws ecr get-login-password --region ap-southeast-1 | \
  docker login --username AWS --password-stdin $ECR_REPO_URI

# Tag and push
docker tag ml-model:latest $ECR_REPO_URI:latest
docker push $ECR_REPO_URI:latest
```

### Pull from Either Registry

```bash
# From DockerHub (public)
docker pull jamezoon/ml-model-spy:latest

# From ECR (requires AWS credentials)
aws ecr get-login-password --region ap-southeast-1 | \
  docker login --username AWS --password-stdin {account-id}.dkr.ecr.ap-southeast-1.amazonaws.com
docker pull {account-id}.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo:latest
```

## Kubernetes Deployment

The Kubernetes deployment ALWAYS uses ECR (not DockerHub):

```yaml
# kubernetes/deployment.yaml
spec:
  containers:
  - name: ml-model-container
    image: YOUR_ECR_REPOSITORY_URI:latest  # This gets replaced during deployment
```

During deployment, `YOUR_ECR_REPOSITORY_URI` is replaced with:
```
{account-id}.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo:latest
```

### Update Running Deployment
```bash
# Get current ECR URI
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO_URI="$AWS_ACCOUNT_ID.dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo"

# Update deployment
kubectl set image deployment/ml-model-deployment \
  ml-model-container=$ECR_REPO_URI:latest

# Check rollout status
kubectl rollout status deployment/ml-model-deployment

# Rollback if needed
kubectl rollout undo deployment/ml-model-deployment
```

## Troubleshooting

### DockerHub Login Failed
```bash
# Check credentials
docker login -u jamezoon

# If push fails, deployment continues with ECR only
# DockerHub is optional for backup
```

### ECR Login Failed
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Re-login to ECR
aws ecr get-login-password --region ap-southeast-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-southeast-1.amazonaws.com
```

### Image Not Found in ECR
```bash
# List images
aws ecr list-images \
  --repository-name ml-model-repo \
  --region ap-southeast-1

# Rebuild and push
bash scripts/04-build_candidate_container.sh
```

### EKS Can't Pull Image
```bash
# Verify ECR permissions for EKS
aws ecr get-repository-policy \
  --repository-name ml-model-repo \
  --region ap-southeast-1

# Check if image exists
aws ecr describe-images \
  --repository-name ml-model-repo \
  --region ap-southeast-1

# Verify EKS node IAM role has ECR permissions
# Should have: AmazonEC2ContainerRegistryReadOnly policy
```

## Cost Comparison

| Registry | Storage | Transfer | Monthly Cost |
|----------|---------|----------|--------------|
| **DockerHub** | Free (public) | Free | $0 |
| **AWS ECR** | $0.10/GB/month | $0.09/GB out | ~$0.50-2/month |

**Total estimated cost**: < $2/month for ECR (DockerHub free)

## Security Considerations

### DockerHub
- ✅ Consider making repository private if model is sensitive
- ✅ No AWS credentials stored in image
- ✅ Environment variables passed at runtime

### AWS ECR
- ✅ Private by default
- ✅ Integrated with AWS IAM
- ✅ Image scanning enabled
- ✅ Encryption at rest (AES256)

### Never Include in Image
- ❌ AWS access keys
- ❌ Database passwords
- ❌ API tokens
- ❌ Sensitive data

All secrets are passed via environment variables at runtime.

## Registry Status Check

```bash
# Check DockerHub images
curl -s "https://hub.docker.com/v2/repositories/jamezoon/ml-model-spy/tags/" | jq '.results[] | {name, last_updated}'

# Check ECR images
aws ecr describe-images \
  --repository-name ml-model-repo \
  --region ap-southeast-1 \
  --query 'imageDetails[*].[imageTags[0],imagePushedAt]' \
  --output table
```

## Best Practices

1. **Always tag with timestamp**
   - Enables easy rollback
   - Maintains version history

2. **Use `latest` for active deployment**
   - Easy to identify current version
   - Simplifies deployment scripts

3. **Test locally before pushing**
   - Catches errors early
   - Saves deployment time

4. **Keep both registries in sync**
   - DockerHub for backup
   - ECR for deployment

5. **Regular cleanup**
   ```bash
   # Delete old ECR images (keep last 10)
   aws ecr list-images \
     --repository-name ml-model-repo \
     --region ap-southeast-1 \
     --query 'imageIds[10:]' \
     --output json | \
     jq -r '.[] | .imageDigest' | \
     xargs -I {} aws ecr batch-delete-image \
       --repository-name ml-model-repo \
       --region ap-southeast-1 \
       --image-ids imageDigest={}
   ```

## Quick Reference

```bash
# Build and push to both registries
bash scripts/04-build_candidate_container.sh

# Full deployment (uses ECR)
bash scripts/11-deploy_prediction_lambda.sh

# Check DockerHub
docker pull jamezoon/ml-model-spy:latest

# Check ECR
aws ecr describe-images --repository-name ml-model-repo --region ap-southeast-1

# Update EKS deployment
kubectl set image deployment/ml-model-deployment \
  ml-model-container=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-southeast-1.amazonaws.com/ml-model-repo:latest
```

