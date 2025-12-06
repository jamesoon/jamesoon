#!/bin/bash

# Configuration
REGION="ap-southeast-1"
API_NAME="MarketDataAPI" # Assuming the prediction API is part of MarketDataAPI

echo "=================================================="
echo "Testing Prediction API for SPY by Date"
echo "=================================================="

# Get API ID dynamically
echo "Fetching API ID for '$API_NAME'வுகளை..."
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='$API_NAME'].id" --output text --region $REGION)

if [ -z "$API_ID" ] || [ "$API_ID" == "None" ]; then
    echo "❌ Error: Could not find API Gateway with name '$API_NAME'"
    exit 1
fi

BASE_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
echo "Base URL: ${BASE_URL}"
echo "=================================================="

# Prompt for date input
read -p "Enter date for SPY prediction (YYYY-MM-DD): " PREDICTION_DATE

# Validate date format (basic check)
if ! [[ "$PREDICTION_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "❌ Error: Invalid date format. Please use YYYY-MM-DD."
    exit 1
fi

# Construct JSON payload
PAYLOAD="{\"date\": \"${PREDICTION_DATE}\", \"ticker\": \"SPY\"}"

echo ""
echo "Sending prediction request for SPY on $PREDICTION_DATE..."
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
