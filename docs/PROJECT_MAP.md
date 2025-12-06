# Project Map and Architecture Overview

This document maps the local file structure to the deployed AWS architecture, explaining how each component is related and used.

## 🏗 High-Level Architecture

The project consists of 4 main components deployed on AWS:

1.  **Frontend**: React App (S3 + CloudFront)
2.  **Trading Backend**: Trading Logic & User Data (Lambda + DynamoDB)
3.  **ML Prediction Service**: SPY Price Prediction Model (EKS / SageMaker)
4.  **Market Data Updater**: Daily Data Fetcher (Lambda + EventBridge)

---

## 📂 File to Deployment Mapping

### 1. Frontend (`frontend/`)
*   **Local Path**: `/frontend`
*   **Deployment Target**: **AWS S3** (`ml-model-frontend-ACCOUNT_ID`) served via **CloudFront**.
*   **Key Files**:
    *   `src/`: React source code.
    *   `package.json`: Dependencies.
*   **Deployment Script**: `scripts/10-build_and_deploy_frontend.sh`
*   **Interaction**: User interface. Calls APIs via API Gateway.

### 2. Trading Backend (`backend/`)
*   **Local Path**: `/backend`
*   **Deployment Target**: **AWS Lambda** (Trading Logic) & **DynamoDB** (User State).
*   **Key Files**:
    *   `lambda_function.py` (or similar): Enty point for trading logic.
    *   `requirements.txt`: Python dependencies.
*   **Deployment Script**: `scripts/09-deploy_trading_backend.sh`
*   **Interaction**: Handles trade execution, portfolio management. Accessed via API Gateway (`/api/trading`).

### 3. ML Prediction Service (`ml_source/`)
*   **Local Path**: `/ml_source` & `/Dockerfile`
*   **Deployment Target**: **AWS EKS** (Elastic Kubernetes Service) OR **SageMaker**.
    *   *Current Configuration uses Docker for EKS/Lambda container images.*
*   **Key Files**:
    *   `app.py`: Flask API for inference.
    *   `model.pkl`: Trained scikit-learn model.
    *   `Dockerfile`: Defines the container image (Python 3.9, installs requirements, runs app.py).
*   **Deployment Script**:
    *   `scripts/04-build_candidate_container.sh` (Builds Docker Image)
    *   `scripts/15-deploy_and_monitor_sagemaker.py` (SageMaker Option)
    *   `scripts/06-deploy_to_aws.sh` (EKS Option)
*   **Interaction**: Provides "Buy/Sell" predictions based on market data. Accessed via API Gateway (`/predict`).

### 4. Market Data Updater (`lambda_data_updater/`)
*   **Local Path**: `/lambda_data_updater`
*   **Deployment Target**: **AWS Lambda** triggers by **EventBridge** (Cron).
*   **Key Files**:
    *   `lambda_function.py`: Fetches latest yahoo finance data.
    *   `requirements.txt`: Dependencies (yfinance, boto3).
*   **Deployment Script**: `scripts/08-deploy_market_data_lambda.sh` (or `12-deploy_updater_lambda_container.sh`)
*   **Interaction**: Updates S3 bucket (`mdaie-prml-spy-bucket`) with latest Parquet data daily.

### 5. Infrastructure & Scripts (`scripts/`)
*   **Purpose**: Automation for setup, deployment, and testing.
*   **Key Scripts**:
    *   `01-setup_aws.sh` to `15-deploy...`: Ordered deployment sequence.
    *   `test_*.sh`: Verification scripts.

### 6. Documentation (`docs/`)
*   **Purpose**: Project guides and references.
*   **Key Files**:
    *   `START_HERE.md`: Main entry point.
    *   `DEPLOYMENT_GUIDE.md`: Detailed instructions.
    *   `PROJECT_MAP.md`: This file.

---

## 🔄 Data Flow

1.  **Data Ingestion**: `Market Data Updater` (Lambda) -> Fetches Data -> Saves to **S3** (`latest.parquet`).
2.  **Model Inference**:
    *   User clicks "Get Prediction" on **Frontend**.
    *   Request -> **API Gateway** -> **ML Prediction Service** (Docker/EKS).
    *   ML Service reads `latest.parquet` from **S3**.
    *   Returns prediction to Frontend.
3.  **Trading**:
    *   User clicks "Buy/Sell" on **Frontend**.
    *   Request -> **API Gateway** -> **Trading Backend** (Lambda).
    *   Updates User Balance/Positions in **DynamoDB**.
