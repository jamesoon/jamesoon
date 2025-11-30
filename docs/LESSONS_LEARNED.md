# Lessons Learned

This document records critical lessons, bug fixes, and architectural decisions to prevent future regressions.

## Template

### [YYYY-MM-DD] [Topic/Error Name]
- **Context**: What were we trying to do?
- **Issue**: What went wrong? (Paste error logs if applicable)
- **Solution**: How did we fix it?
- **Prevention**: How do we ensure this doesn't happen again?

---

## [2025-11-27] Lambda Deployment Errors (Example)
- **Context**: Deploying the market data updater lambda.
- **Issue**: Deployment failed due to package size exceeding AWS limits or missing dependencies in the layer.
- **Solution**: [Placeholder: Describe the actual solution used, e.g., using Docker container images or splitting layers]
- **Prevention**: Always check package size before deployment. Use `scripts/check_lambda_size.sh` (if it exists).

## [2025-11-27] Agent Context Missing
- **Context**: Agents were making changes without knowing project standards.
- **Issue**: Inconsistent code style and repeated errors.
- **Solution**: Implemented `AGENT_INSTRUCTIONS.md` and `.cursorrules`.
- **Prevention**: Agents are now instructed to read these files first.

## [2025-11-30] Model Inference Mismatch & Drift Monitoring
- **Context**: Debugging why the `model-inference` module (SageMaker) gave different predictions compared to local/Lambda execution.
- **Issue**: The SageMaker inference script (`sagemaker_inference.py`) was not loading the same fresh data from S3 as the local application (`app_s3.py`). It was likely relying on stale or differently processed features passed in the request body.
- **Solution**: Updated `ml_source/sagemaker_inference.py` to:
    1. Load market data directly from S3 (`s3://mdaie-prml-spy-bucket/market-data/latest.parquet`).
    2. Implement the exact same feature engineering logic as `app_s3.py` (RSI, rolling means, etc.).
    3. Log inference details to CloudWatch for debugging.
- **Prevention**: Ensure that inference logic (feature engineering) is shared or identical across all environments (Local, Lambda, SageMaker). Use a shared library or identical script logic.
- **Drift Monitoring**: Created `scripts/setup_drift_monitoring.py` to enable SageMaker Data Capture and guide the setup of Model Quality Monitoring.
