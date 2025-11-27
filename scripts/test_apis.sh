#!/bin/bash

# Configuration
API_ID="0qoytg0cfg"
REGION="ap-southeast-1"
BASE_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"

echo "=================================================="
echo "Testing Deployed APIs"
echo "Base URL: ${BASE_URL}"
echo "=================================================="

# 1. Test SPY Data API
echo ""
echo "1. Testing SPY Data API (GET /api/spy-data)..."
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "${BASE_URL}/api/spy-data")
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
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "${BASE_URL}/health")
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ Success (HTTP 200)"
    echo "Response: $BODY"
else
    echo "❌ Failed (HTTP $HTTP_STATUS)"
    echo "Response: $BODY"
fi

# 3. Test Prediction API Prediction (Validation Error Expected)
echo ""
echo "3. Testing Prediction API (Validation Error Expected)..."
PAYLOAD='{"features": [[1.0, 2.0, 3.0]]}'
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "${BASE_URL}/predict")
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

if [ "$HTTP_STATUS" -eq 500 ]; then
    echo "✅ Success (Got Expected Validation Error)"
    echo "Response: $BODY"
else
    echo "❌ Unexpected Status (HTTP $HTTP_STATUS)"
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
