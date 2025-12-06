#!/bin/bash

# Configuration
REGION="ap-southeast-1"
API_NAME="MarketDataAPI"

echo "=================================================="
echo "Testing Deployed APIs"
echo "=================================================="

# Get API ID dynamically
echo "Fetching API ID for '$API_NAME'..."
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='$API_NAME'].id" --output text --region $REGION)

if [ -z "$API_ID" ] || [ "$API_ID" == "None" ]; then
    echo "❌ Error: Could not find API Gateway with name '$API_NAME'"
    exit 1
fi

BASE_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
echo "Base URL: ${BASE_URL}"
echo "=================================================="

# 1. Test Market Data API
echo ""
echo "1. Testing Market Data API (GET /api/market-indices)..."
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "${BASE_URL}/api/market-indices")
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ Success (HTTP 200)"
    echo "Response Snippet: $(echo $BODY | cut -c 1-100)..."
else
    echo "❌ Failed (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi

# 2. Test Prediction API Health
echo ""
echo "2. Testing Prediction API Health (GET /health)..."
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "${BASE_URL}/healthcare")
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ Success (HTTP 200)"
    echo "Response: $BODY"
else
    echo "❌ Failed (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi

# 3. Test Prediction API Prediction (Features)
echo ""
echo "3. Testing Prediction API (Features)..."
PAYLOAD='{"features": [[1.0, 2.0, 3.0]]}'
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "${BASE_URL}/predict")
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ Success (HTTP 200)"
    echo "Response: $BODY"
else
    echo "❌ Failed (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi

# 4. Test Prediction API (Dummy/Fallback)
echo ""
echo "4. Testing Prediction API (Dummy/Fallback)..."
PAYLOAD='{}'
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "${BASE_URL}/predict")
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ Success (HTTP 200)"
    echo "Response: $BODY"
else
    echo "❌ Failed (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi

echo ""
echo "=================================================="
echo "Test Complete"
echo "=================================================="
