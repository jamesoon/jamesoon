#!/bin/bash
set -e

# Create archive directories
mkdir -p _archive/scripts
mkdir -p _archive/ml_source

echo "Archiving root files..."
mv API_GATEWAY_MISSING_TOKEN_FIX.md _archive/ 2>/dev/null || true
mv DATA_NORMALIZATION_SUMMARY.md _archive/ 2>/dev/null || true
mv DEPLOYMENT_CHECKLIST.md _archive/ 2>/dev/null || true
mv DEPLOYMENT_GUIDE.md _archive/ 2>/dev/null || true
mv DEPLOYMENT_MASTER_PLAN.md _archive/ 2>/dev/null || true
mv DEPLOYMENT_SUMMARY.md _archive/ 2>/dev/null || true
mv DOCKER_DEPLOYMENT_GUIDE.md _archive/ 2>/dev/null || true
mv FINAL_DEPLOYMENT_SUMMARY.md _archive/ 2>/dev/null || true
mv INFERENCE_REQUIREMENTS.md _archive/ 2>/dev/null || true
mv LAMBDA_SIZE_FIX.md _archive/ 2>/dev/null || true
mv MARKET_DATA_API_SUMMARY.md _archive/ 2>/dev/null || true
mv PROJECT_STATUS.md _archive/ 2>/dev/null || true
mv QUICK_START.md _archive/ 2>/dev/null || true
mv QUICK_START_SPY_API.md _archive/ 2>/dev/null || true
mv READY_TO_DEPLOY.md _archive/ 2>/dev/null || true
mv SPY_API_STATUS.md _archive/ 2>/dev/null || true
mv SPY_API_SUMMARY.md _archive/ 2>/dev/null || true
mv SPY_DATA_API_GUIDE.md _archive/ 2>/dev/null || true
mv START_HERE.md _archive/ 2>/dev/null || true
mv YAHOO_FINANCE_ALTERNATIVES.md _archive/ 2>/dev/null || true
mv check_aws_resources.sh _archive/ 2>/dev/null || true
mv check_lambda_logs.sh _archive/ 2>/dev/null || true
mv cloudfront_config.json _archive/ 2>/dev/null || true
mv cloudfront_config_final.json _archive/ 2>/dev/null || true
mv fix_spy_api_final.sh _archive/ 2>/dev/null || true
mv test_spy_api_simple.sh _archive/ 2>/dev/null || true

echo "Archiving scripts..."
# Move numbered scripts except 09
mv scripts/00_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/01_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/02_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/02_*.py _archive/scripts/ 2>/dev/null || true
mv scripts/03_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/04_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/05_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/06_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/06.1_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/07_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/07.1_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/07_*.md _archive/scripts/ 2>/dev/null || true
mv scripts/08_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/10_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/11_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/12_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/13_*.sh _archive/scripts/ 2>/dev/null || true

# Other obsolete scripts
mv scripts/MASTER_DEPLOY.sh _archive/scripts/ 2>/dev/null || true
mv scripts/add_spy_data_api_endpoint.sh _archive/scripts/ 2>/dev/null || true
mv scripts/build_and_push_docker.sh _archive/scripts/ 2>/dev/null || true
mv scripts/build_lambda_package*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/check_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/create_eks_cluster.sh _archive/scripts/ 2>/dev/null || true
mv scripts/create_lambda_proxy.sh _archive/scripts/ 2>/dev/null || true
mv scripts/create_lambda_spy_data*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/create_spy_endpoint_simple.sh _archive/scripts/ 2>/dev/null || true
mv scripts/deploy_lambda_container.sh _archive/scripts/ 2>/dev/null || true
mv scripts/deploy_spy_data_api.sh _archive/scripts/ 2>/dev/null || true
mv scripts/diagnose_lambda_error.sh _archive/scripts/ 2>/dev/null || true
mv scripts/fix_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/fix_*.py _archive/scripts/ 2>/dev/null || true
mv scripts/get_cloudfront_info.sh _archive/scripts/ 2>/dev/null || true
mv scripts/list_all_apis*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/normalize_and_upload_s3.py _archive/scripts/ 2>/dev/null || true
mv scripts/run_s3_data_load.sh _archive/scripts/ 2>/dev/null || true
mv scripts/setup_aws.sh _archive/scripts/ 2>/dev/null || true
mv scripts/teardown_aws.sh _archive/scripts/ 2>/dev/null || true
mv scripts/test_lambda_*.sh _archive/scripts/ 2>/dev/null || true
mv scripts/test_spy_data_api.sh _archive/scripts/ 2>/dev/null || true
mv scripts/update_api_gateway.sh _archive/scripts/ 2>/dev/null || true
mv scripts/RUN_S3_DATA_LOAD.md _archive/scripts/ 2>/dev/null || true
mv scripts/TEST_API_README.md _archive/scripts/ 2>/dev/null || true

echo "Archiving ml_source files..."
mv ml_source/app_s3.py _archive/ml_source/ 2>/dev/null || true
mv ml_source/create_buysell_model.ipynb _archive/ml_source/ 2>/dev/null || true
mv ml_source/create_buysell_model.py _archive/ml_source/ 2>/dev/null || true
mv ml_source/create_model.py _archive/ml_source/ 2>/dev/null || true
mv ml_source/requirements_s3.txt _archive/ml_source/ 2>/dev/null || true
mv ml_source/test_model.py _archive/ml_source/ 2>/dev/null || true

echo "Cleanup complete. Files moved to _archive/"
