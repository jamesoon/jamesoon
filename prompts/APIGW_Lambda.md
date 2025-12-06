# API Gateway & Lambda Implementation Prompt

You are an expert AWS Cloud Architect and Python Developer. Your task is to design and implement the **API Gateway** and **Lambda functions** for the MLOps Trading Project.

## Context
We have an existing MLOps pipeline that:
1.  Updates market data daily (S3).
2.  Trains a model (SageMaker).
3.  Serves predictions (Lambda Proxy).
4.  Displays data on a frontend (React/Next.js).

We need an **API Gateway** to expose this functionality securely to the frontend.

## Architecture Overview

### 1. API Gateway (REST API)
Create a REST API with the following resources:

| Resource | Method | Integration | Description |
| :--- | :--- | :--- | :--- |
| `/market-data` | `GET` | Lambda: `spy-data-fetcher` | Returns SPY price data, history, and metrics from S3. |
| `/predict` | `POST` | Lambda: `prediction-proxy` | Accepts ticker, loads model/data from S3, computes features, and returns prediction. |
| `/admin/update` | `POST` | Lambda: `market-data-updater` | Manually triggers the daily data update process. |

**Global Settings:**
-   **CORS**: Enable for all endpoints (Allow-Origin: `*` for dev, specific domain for prod).
-   **Auth**: API Key for `/admin/update`. Open for `/market-data` and `/predict` (or restrict to frontend domain).

---

## Lambda Function Specifications

### 1. `spy-data-fetcher`
-   **Source Code**: `lambda_spy_data/lambda_function.py`
-   **Runtime**: Python 3.9+
-   **Memory**: 512MB (Pandas processing)
-   **Timeout**: 10 seconds
-   **Permissions**: `s3:GetObject` on Data Bucket.
-   **Layers**: `AWSDataWrangler` or `Pandas` layer.
-   **Env Vars**:
    -   `S3_BUCKET_NAME`: Target bucket (`mdaie-prml-spy-bucket`).
    -   `S3_FILE_KEY`: `market_data_normalized.parquet`.

### 2. `market-data-updater`
-   **Source Code**: `lambda_data_updater/lambda_function.py`
-   **Runtime**: Python 3.9+
-   **Memory**: 1024MB (Data processing)
-   **Timeout**: 5 minutes (Network calls + S3 I/O)
-   **Permissions**: `s3:PutObject`, `s3:GetObject` on Data Bucket.
-   **Triggers**:
    -   EventBridge Schedule: `cron(30 16 ? * MON-FRI *)` (4:30 PM EST).
    -   API Gateway: `/admin/update`.
-   **Env Vars**:
    -   `S3_BUCKET_NAME`: Target bucket (`mdaie-prml-spy-bucket`).

### 3. `prediction-proxy` (Formerly `model-inference`)
-   **Purpose**: Perform inference using S3-stored model and data (replaces SageMaker Endpoint).
-   **Source Code**: `ml_source/app_s3.py`
-   **Runtime**: Python 3.9+ (Container Image recommended due to dependencies)
-   **Memory**: 1024MB (Feature computation)
-   **Timeout**: 30 seconds
-   **Permissions**: `s3:GetObject` on Data Bucket.
-   **Env Vars**:
    -   `S3_BUCKET_NAME`: Target bucket (`mdaie-prml-spy-bucket`).
    -   `S3_DATA_KEY`: `market-data/latest.parquet`.
-   **Logic**:
    1.  Receive JSON payload (`{"ticker": "SPY"}`).
    2.  Load model (`model.pkl`) and data (`latest.parquet`) from S3 (or local cache).
    3.  Compute technical indicators (RSI, MA, Volatility).
    4.  Run inference using the loaded model.
    5.  Return prediction signal (BUY/SELL) and price targets.

---

## Implementation Requirements

1.  **Infrastructure as Code**: Provide **Terraform** or **AWS SAM** template to deploy:
    -   API Gateway.
    -   Lambda Functions.
    -   IAM Roles & Policies.
    -   EventBridge Rule.
2.  **Code Improvements**:
    -   Ensure `lambda_spy_data` handles `awswrangler` vs `pyarrow` gracefully (already in code).
    -   Add structured logging to all Lambdas.
3.  **Deployment Instructions**:
    -   Steps to package Lambdas (handling dependencies like `pandas`, `yfinance`, `pyarrow`).
    -   Steps to deploy the stack.

## Reference Files
-   `prompts/api_gateway.md`: General API Gateway standards.
-   `ml_source/app_s3.py`: Prediction logic.
-   `lambda_spy_data/lambda_function.py`: Market data fetcher logic.
-   `lambda_data_updater/lambda_function.py`: Market data updater logic.
