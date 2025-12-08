#!/bin/bash
set -e

# Test script for Trading Backend API

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config/trading_api.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================="
echo "Trading Backend API Test Suite"
echo "========================================="

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Configuration file not found: $CONFIG_FILE${NC}"
    echo ""
    echo "Please run: ./scripts/08_deploy_trading_backend.sh first"
    exit 1
fi

# Load configuration
source "$CONFIG_FILE"

if [ -z "$TRADING_API_URL" ]; then
    echo -e "${RED}❌ TRADING_API_URL not found in config${NC}"
    exit 1
fi

echo -e "${BLUE}API Endpoint:${NC} $TRADING_API_URL"
echo -e "${BLUE}Table Name:${NC} $TABLE_NAME"
echo -e "${BLUE}Function Name:${NC} $FUNCTION_NAME"
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to test endpoint
test_endpoint() {
    local TEST_NAME="$1"
    local METHOD="$2"
    local ENDPOINT="$3"
    local DATA="$4"
    local EXPECTED="$5"
    
    echo -e "${YELLOW}Testing:${NC} $TEST_NAME"
    echo "  URL: $METHOD $ENDPOINT"
    
    if [ -n "$DATA" ]; then
        RESPONSE=$(curl -s -X "$METHOD" "$ENDPOINT" \
            -H "Content-Type: application/json" \
            -d "$DATA")
    else
        RESPONSE=$(curl -s -X "$METHOD" "$ENDPOINT")
    fi
    
    echo "  Response: $RESPONSE"
    
    if echo "$RESPONSE" | grep -q "$EXPECTED"; then
        echo -e "  ${GREEN}✅ PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "  ${RED}❌ FAILED${NC}"
        echo "  Expected to contain: $EXPECTED"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# Test 1: Health Check
echo "========================================="
echo "Test Suite 1: Health Checks"
echo "========================================="
echo ""

test_endpoint \
    "Health endpoint" \
    "GET" \
    "$TRADING_API_URL/api/trading/health" \
    "" \
    "healthy"

test_endpoint \
    "Short health endpoint" \
    "GET" \
    "$TRADING_API_URL/health" \
    "" \
    "healthy"

# Test 2: User Profile
echo "========================================="
echo "Test Suite 2: User Profile"
echo "========================================="
echo ""

test_endpoint \
    "Get user profile (creates if not exists)" \
    "GET" \
    "$TRADING_API_URL/api/trading/profile" \
    '{"username":"user"}' \
    "cashBalance"

# Test 3: Portfolio Operations
echo "========================================="
echo "Test Suite 3: Portfolio Operations"
echo "========================================="
echo ""

test_endpoint \
    "Get empty portfolio" \
    "GET" \
    "$TRADING_API_URL/api/trading/portfolio" \
    '{"username":"user"}' \
    "portfolio"

# Test 4: Buy Stock
echo "========================================="
echo "Test Suite 4: Trading - Buy"
echo "========================================="
echo ""

test_endpoint \
    "Buy AAPL stock" \
    "POST" \
    "$TRADING_API_URL/api/trading/buy" \
    '{"username":"user","ticker":"AAPL","shares":10,"price":150.50}' \
    "success"

test_endpoint \
    "Buy MSFT stock" \
    "POST" \
    "$TRADING_API_URL/api/trading/buy" \
    '{"username":"user","ticker":"MSFT","shares":5,"price":320.75}' \
    "success"

# Test 5: Portfolio After Buy
test_endpoint \
    "Get portfolio after purchases" \
    "GET" \
    "$TRADING_API_URL/api/trading/portfolio" \
    '{"username":"user"}' \
    "AAPL"

# Test 6: Transactions
echo "========================================="
echo "Test Suite 5: Transactions"
echo "========================================="
echo ""

test_endpoint \
    "Get transaction history" \
    "GET" \
    "$TRADING_API_URL/api/trading/transactions" \
    '{"username":"user"}' \
    "transactions"

# Test 7: Sell Stock
echo "========================================="
echo "Test Suite 6: Trading - Sell"
echo "========================================="
echo ""

test_endpoint \
    "Sell AAPL stock" \
    "POST" \
    "$TRADING_API_URL/api/trading/sell" \
    '{"username":"user","ticker":"AAPL","shares":5,"price":155.00}' \
    "success"

# Test 8: Error Cases
echo "========================================="
echo "Test Suite 7: Error Handling"
echo "========================================="
echo ""

test_endpoint \
    "Buy with insufficient funds" \
    "POST" \
    "$TRADING_API_URL/api/trading/buy" \
    '{"username":"user","ticker":"TSLA","shares":1000,"price":10000.00}' \
    "Insufficient"

test_endpoint \
    "Sell non-existent stock" \
    "POST" \
    "$TRADING_API_URL/api/trading/sell" \
    '{"username":"user","ticker":"NOPE","shares":10,"price":100.00}' \
    "Insufficient"

# Test 9: Lambda Function Status
echo "========================================="
echo "Test Suite 8: AWS Infrastructure"
echo "========================================="
echo ""

echo -e "${YELLOW}Checking Lambda function status...${NC}"
LAMBDA_STATE=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.State' \
    --output text 2>/dev/null || echo "ERROR")

if [ "$LAMBDA_STATE" == "Active" ]; then
    echo -e "  ${GREEN}✅ Lambda function is Active${NC}"
    ((TESTS_PASSED++))
else
    echo -e "  ${RED}❌ Lambda function state: $LAMBDA_STATE${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 10: DynamoDB Table Status
echo -e "${YELLOW}Checking DynamoDB table status...${NC}"
TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "ERROR")

if [ "$TABLE_STATUS" == "ACTIVE" ]; then
    echo -e "  ${GREEN}✅ DynamoDB table is Active${NC}"
    ((TESTS_PASSED++))
else
    echo -e "  ${RED}❌ DynamoDB table status: $TABLE_STATUS${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 11: CORS Headers
echo -e "${YELLOW}Checking CORS headers...${NC}"
CORS_CHECK=$(curl -s -I "$TRADING_API_URL/api/trading/health" | grep -i "access-control-allow-origin" || echo "")

if [ -n "$CORS_CHECK" ]; then
    echo -e "  ${GREEN}✅ CORS headers present${NC}"
    echo "  $CORS_CHECK"
    ((TESTS_PASSED++))
else
    echo -e "  ${RED}❌ CORS headers missing${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 12: CloudWatch Logs
echo "========================================="
echo "Test Suite 9: CloudWatch Logs"
echo "========================================="
echo ""

echo -e "${YELLOW}Checking CloudWatch logs...${NC}"
LOG_GROUP="/aws/lambda/$FUNCTION_NAME"

if aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --region "$REGION" \
    --max-items 1 >/dev/null 2>&1; then
    
    echo -e "  ${GREEN}✅ CloudWatch logs available${NC}"
    echo "  Log group: $LOG_GROUP"
    ((TESTS_PASSED++))
    
    # Get recent errors
    echo ""
    echo "  Recent log entries:"
    aws logs tail "$LOG_GROUP" --region "$REGION" --since 5m --format short | head -20 || echo "  (no recent logs)"
else
    echo -e "  ${YELLOW}⚠️  No CloudWatch logs yet (function may not have been invoked)${NC}"
fi
echo ""

# Test 13: Data Validation
echo "========================================="
echo "Test Suite 10: Data Validation"
echo "========================================="
echo ""

echo -e "${YELLOW}Testing data persistence...${NC}"

# Get profile data
PROFILE_DATA=$(curl -s -X GET "$TRADING_API_URL/api/trading/profile" -d '{"username":"user"}')
CASH_BALANCE=$(echo "$PROFILE_DATA" | grep -o '"cashBalance":[0-9.]*' | cut -d: -f2 || echo "0")

if [ "$CASH_BALANCE" != "0" ] && [ -n "$CASH_BALANCE" ]; then
    echo -e "  ${GREEN}✅ Cash balance retrieved: \$$CASH_BALANCE${NC}"
    ((TESTS_PASSED++))
else
    echo -e "  ${RED}❌ Failed to retrieve cash balance${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Summary
echo "========================================="
echo "TEST SUMMARY"
echo "========================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    echo ""
    echo "✅ Trading Backend API is fully operational"
    echo ""
    echo "📝 Next steps:"
    echo "  1. Update frontend .env:"
    echo "     REACT_APP_TRADING_API=$TRADING_API_URL"
    echo "  2. Redeploy frontend:"
    echo "     ./scripts/09_build_and_deploy_frontend.sh"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed${NC}"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "  - Check CloudWatch logs: aws logs tail $LOG_GROUP --region $REGION --follow"
    echo "  - Verify Lambda permissions: aws lambda get-policy --function-name $FUNCTION_NAME"
    echo "  - Check DynamoDB table: aws dynamodb scan --table-name $TABLE_NAME --region $REGION"
    echo ""
    exit 1
fi

