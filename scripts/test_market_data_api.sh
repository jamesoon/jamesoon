#!/bin/bash

# Exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables
AWS_REGION="ap-southeast-1"
LAMBDA_FUNCTION_NAME="market-data-fetcher"
CONFIG_FILE="config/market_data_api.txt"

echo ""
echo "======================================"
echo "Market Data API - Test Suite"
echo "======================================"
echo ""

# Check if config file exists
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${GREEN}✓${NC} Found configuration file"
    source "$CONFIG_FILE"
    API_URL="$MARKET_DATA_API_URL"
else
    echo -e "${YELLOW}⚠${NC} Configuration file not found"
    echo "Attempting to get API URL from AWS..."
    
    # Get API Gateway ID
    REST_API_ID=$(aws apigateway get-rest-apis \
      --query "items[?name=='MarketDataAPI'].id" \
      --output text \
      --region $AWS_REGION 2>/dev/null || echo "")
    
    if [ -z "$REST_API_ID" ]; then
        echo -e "${RED}✗${NC} Could not find MarketDataAPI"
        echo "Please run: ./scripts/07_deploy_market_data_lambda.sh first"
        exit 1
    fi
    
    API_URL="https://$REST_API_ID.execute-api.$AWS_REGION.amazonaws.com/prod/api/market-indices"
fi

echo "API URL: $API_URL"
echo ""

# Test 1: Check if Lambda function exists
echo -e "${BLUE}Test 1: Lambda Function Status${NC}"
if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION &>/dev/null; then
    echo -e "${GREEN}✓${NC} Lambda function exists: $LAMBDA_FUNCTION_NAME"
    
    # Get Lambda details
    LAMBDA_STATE=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION --query 'Configuration.State' --output text)
    LAMBDA_MEMORY=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION --query 'Configuration.MemorySize' --output text)
    LAMBDA_TIMEOUT=$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION --query 'Configuration.Timeout' --output text)
    
    echo "  State: $LAMBDA_STATE"
    echo "  Memory: ${LAMBDA_MEMORY}MB"
    echo "  Timeout: ${LAMBDA_TIMEOUT}s"
else
    echo -e "${RED}✗${NC} Lambda function not found"
    exit 1
fi
echo ""

# Test 2: Health Check Endpoint
echo -e "${BLUE}Test 2: Health Check Endpoint${NC}"
HEALTH_URL="${API_URL/market-indices/health}"
echo "Testing: $HEALTH_URL"

HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$HEALTH_URL")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC} Health check passed (HTTP $HTTP_CODE)"
    echo "Response:"
    echo "$HEALTH_BODY" | jq '.' 2>/dev/null || echo "$HEALTH_BODY"
else
    echo -e "${RED}✗${NC} Health check failed (HTTP $HTTP_CODE)"
    echo "$HEALTH_BODY"
fi
echo ""

# Test 3: Market Indices Endpoint
echo -e "${BLUE}Test 3: Market Indices Endpoint${NC}"
echo "Testing: $API_URL"
echo "Fetching market data (this may take 10-20 seconds)..."

START_TIME=$(date +%s)
MARKET_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL")
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

HTTP_CODE=$(echo "$MARKET_RESPONSE" | tail -n1)
MARKET_BODY=$(echo "$MARKET_RESPONSE" | sed '$d')

echo "Response time: ${DURATION}s"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓${NC} Market data fetched successfully (HTTP $HTTP_CODE)"
    
    # Check if response is valid JSON
    if echo "$MARKET_BODY" | jq empty 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Response is valid JSON"
        
        # Count indices
        INDEX_COUNT=$(echo "$MARKET_BODY" | jq 'length' 2>/dev/null)
        echo "Number of indices: $INDEX_COUNT"
        
        # Display summary for each index
        echo ""
        echo "Market Indices Summary:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        for i in $(seq 0 $((INDEX_COUNT - 1))); do
            NAME=$(echo "$MARKET_BODY" | jq -r ".[$i].name")
            SYMBOL=$(echo "$MARKET_BODY" | jq -r ".[$i].symbol")
            CURRENT=$(echo "$MARKET_BODY" | jq -r ".[$i].current")
            CHANGE=$(echo "$MARKET_BODY" | jq -r ".[$i].change")
            CHANGE_PCT=$(echo "$MARKET_BODY" | jq -r ".[$i].changePercent")
            DATA_POINTS=$(echo "$MARKET_BODY" | jq -r ".[$i].chartData | length")
            
            # Color code based on change
            if (( $(echo "$CHANGE >= 0" | bc -l) )); then
                COLOR=$GREEN
                ARROW="↑"
            else
                COLOR=$RED
                ARROW="↓"
            fi
            
            echo -e "${COLOR}$ARROW $NAME ($SYMBOL)${NC}"
            echo "  Current: $CURRENT"
            echo "  Change: $CHANGE ($CHANGE_PCT%)"
            echo "  Data Points: $DATA_POINTS days"
            echo ""
        done
        
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Save sample response
        echo "$MARKET_BODY" | jq '.' > /tmp/market_data_sample.json 2>/dev/null
        echo "Full response saved to: /tmp/market_data_sample.json"
        
    else
        echo -e "${RED}✗${NC} Response is not valid JSON"
        echo "$MARKET_BODY"
    fi
else
    echo -e "${RED}✗${NC} Failed to fetch market data (HTTP $HTTP_CODE)"
    echo "$MARKET_BODY"
fi
echo ""

# Test 4: CORS Headers
echo -e "${BLUE}Test 4: CORS Headers${NC}"
CORS_RESPONSE=$(curl -s -I -X OPTIONS "$API_URL")

if echo "$CORS_RESPONSE" | grep -i "access-control-allow-origin" > /dev/null; then
    echo -e "${GREEN}✓${NC} CORS headers present"
    echo "$CORS_RESPONSE" | grep -i "access-control"
else
    echo -e "${YELLOW}⚠${NC} CORS headers not found"
fi
echo ""

# Test 5: Lambda Logs (Recent Invocations)
echo -e "${BLUE}Test 5: Recent Lambda Invocations${NC}"
echo "Checking CloudWatch logs (last 5 minutes)..."

LOG_GROUP="/aws/lambda/$LAMBDA_FUNCTION_NAME"

if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region $AWS_REGION &>/dev/null; then
    # Get recent log events
    RECENT_LOGS=$(aws logs tail "$LOG_GROUP" --since 5m --format short --region $AWS_REGION 2>/dev/null | head -20)
    
    if [ -n "$RECENT_LOGS" ]; then
        echo -e "${GREEN}✓${NC} Recent invocations found"
        echo "Last few log entries:"
        echo "$RECENT_LOGS"
    else
        echo -e "${YELLOW}⚠${NC} No recent invocations in last 5 minutes"
    fi
else
    echo -e "${YELLOW}⚠${NC} Log group not found or no permissions"
fi
echo ""

# Test 6: Lambda Metrics
echo -e "${BLUE}Test 6: Lambda Metrics (Last Hour)${NC}"

INVOCATIONS=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION_NAME \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum \
    --region $AWS_REGION \
    --query 'Datapoints[0].Sum' \
    --output text 2>/dev/null || echo "0")

ERRORS=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION_NAME \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum \
    --region $AWS_REGION \
    --query 'Datapoints[0].Sum' \
    --output text 2>/dev/null || echo "0")

if [ "$INVOCATIONS" != "None" ] && [ "$INVOCATIONS" != "0" ]; then
    echo -e "${GREEN}✓${NC} Invocations (last hour): ${INVOCATIONS:-0}"
    echo "  Errors: ${ERRORS:-0}"
    
    if [ "$ERRORS" != "0" ] && [ "$ERRORS" != "None" ]; then
        ERROR_RATE=$(echo "scale=2; $ERRORS / $INVOCATIONS * 100" | bc)
        echo -e "  ${RED}Error Rate: ${ERROR_RATE}%${NC}"
    fi
else
    echo -e "${YELLOW}⚠${NC} No invocations in the last hour"
fi
echo ""

# Test 7: Data Validation
echo -e "${BLUE}Test 7: Data Validation${NC}"

if [ -f "/tmp/market_data_sample.json" ]; then
    # Check required fields
    REQUIRED_FIELDS=("name" "symbol" "current" "change" "changePercent" "chartData")
    ALL_VALID=true
    
    for field in "${REQUIRED_FIELDS[@]}"; do
        if echo "$MARKET_BODY" | jq -e ".[0].$field" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Field '$field' present"
        else
            echo -e "${RED}✗${NC} Field '$field' missing"
            ALL_VALID=false
        fi
    done
    
    # Check chart data structure
    FIRST_CHART_POINT=$(echo "$MARKET_BODY" | jq '.[0].chartData[0]' 2>/dev/null)
    if [ -n "$FIRST_CHART_POINT" ] && [ "$FIRST_CHART_POINT" != "null" ]; then
        echo -e "${GREEN}✓${NC} Chart data structure valid"
        echo "Sample data point:"
        echo "$FIRST_CHART_POINT" | jq '.'
    else
        echo -e "${RED}✗${NC} Chart data structure invalid"
        ALL_VALID=false
    fi
    
    if [ "$ALL_VALID" = true ]; then
        echo -e "\n${GREEN}✓${NC} All validation checks passed"
    fi
else
    echo -e "${YELLOW}⚠${NC} No sample data to validate"
fi
echo ""

# Summary
echo "======================================"
echo "Test Summary"
echo "======================================"
echo ""
echo "API Endpoint: $API_URL"
echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "Region: $AWS_REGION"
echo ""

# Frontend integration instructions
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Frontend Integration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Update frontend/.env:"
echo "   REACT_APP_MARKET_DATA_API=$API_URL"
echo ""
echo "2. Restart frontend:"
echo "   cd frontend && npm start"
echo ""
echo "3. Test in browser:"
echo "   http://localhost:3000/portfolio"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Additional commands
echo "Useful Commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "View live logs:"
echo "  aws logs tail /aws/lambda/$LAMBDA_FUNCTION_NAME --follow"
echo ""
echo "Invoke Lambda directly:"
echo "  aws lambda invoke --function-name $LAMBDA_FUNCTION_NAME \\"
echo "    --payload '{\"httpMethod\":\"GET\",\"path\":\"/api/market-indices\"}' \\"
echo "    response.json && cat response.json | jq"
echo ""
echo "Get API Gateway details:"
echo "  aws apigateway get-rest-apis --query \"items[?name=='MarketDataAPI']\""
echo ""
echo "Check CloudWatch metrics:"
echo "  aws cloudwatch get-metric-statistics \\"
echo "    --namespace AWS/Lambda \\"
echo "    --metric-name Duration \\"
echo "    --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION_NAME \\"
echo "    --start-time \$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \\"
echo "    --end-time \$(date -u +%Y-%m-%dT%H:%M:%S) \\"
echo "    --period 300 \\"
echo "    --statistics Average"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${GREEN}✓ Testing complete!${NC}"
echo ""

