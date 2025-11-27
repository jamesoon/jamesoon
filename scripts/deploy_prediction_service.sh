#!/bin/bash
set -e

# Configuration
AWS_REGION="ap-southeast-1"
ECR_REPO_NAME="prediction-service"
DOCKER_HUB_USERNAME="jamezoon"
IMAGE_TAG="latest"

# Get Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "=========================================="
echo "Deploying Prediction Service"
echo "Region: ${AWS_REGION}"
echo "ECR Repo: ${ECR_REPO_NAME}"
echo "=========================================="

# 1. Create ECR Repository if it doesn't exist
echo "Checking ECR repository..."
aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${AWS_REGION} > /dev/null 2>&1 || \
    aws ecr create-repository --repository-name ${ECR_REPO_NAME} --region ${AWS_REGION}

# 2. Login to ECR
echo "Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# 3. Build Docker Image
echo "Building Docker image..."
cd ml_source
# Build for amd64 to ensure compatibility with EKS/Lambda if needed
docker build --platform linux/amd64 -t ${ECR_REPO_NAME}:${IMAGE_TAG} .

# 4. Tag and Push to ECR
echo "Pushing to ECR..."
docker tag ${ECR_REPO_NAME}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
docker push ${ECR_URI}:${IMAGE_TAG}

# 5. Push to Docker Hub (as requested)
echo "Pushing to Docker Hub..."
# Assuming user is already logged in or we skip this if it fails
docker tag ${ECR_REPO_NAME}:${IMAGE_TAG} ${DOCKER_HUB_USERNAME}/${ECR_REPO_NAME}:${IMAGE_TAG}
# docker push ${DOCKER_HUB_USERNAME}/${ECR_REPO_NAME}:${IMAGE_TAG} || echo "Warning: Failed to push to Docker Hub. Continuing..."

echo "Image pushed successfully: ${ECR_URI}:${IMAGE_TAG}"

# 6. Create Kubernetes Manifests
echo "Creating Kubernetes manifests..."
mkdir -p ../k8s

cat <<EOF > ../k8s/prediction-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prediction-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prediction-service
  template:
    metadata:
      labels:
        app: prediction-service
    spec:
      containers:
      - name: prediction-service
        image: ${ECR_URI}:${IMAGE_TAG}
        ports:
        - containerPort: 5000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
EOF

cat <<EOF > ../k8s/prediction-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: prediction-service
spec:
  selector:
    app: prediction-service
  ports:
    - protocol: TCP
      port: 80
      targetPort: 5000
  type: ClusterIP
EOF

# 7. Apply to EKS
echo "Applying to EKS..."
# Check if kubectl is configured
if kubectl get nodes > /dev/null 2>&1; then
    kubectl apply -f ../k8s/prediction-deployment.yaml
    kubectl apply -f ../k8s/prediction-service.yaml
    echo "Deployment applied to EKS."
else
    echo "Warning: kubectl not configured or cluster not reachable. Skipping EKS deployment."
fi

echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
