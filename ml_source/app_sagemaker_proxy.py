import os
import json
import boto3
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Configuration
ENDPOINT_NAME = os.environ.get('SAGEMAKER_ENDPOINT_NAME')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-1')

# Initialize SageMaker Runtime Client
try:
    sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=AWS_REGION)
except Exception as e:
    print(f"Error initializing SageMaker runtime client: {e}")
    sagemaker_runtime = None

# Add CORS headers to every response
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "prediction-proxy",
        "sagemaker_endpoint": ENDPOINT_NAME,
        "region": AWS_REGION
    })

@app.route("/predict", methods=["POST"])
def predict():
    if not sagemaker_runtime:
        return jsonify({"error": "SageMaker client not initialized"}), 500
    
    if not ENDPOINT_NAME:
        return jsonify({"error": "SAGEMAKER_ENDPOINT_NAME environment variable not set"}), 500

    try:
        # Get JSON data from request
        data = request.get_json(force=True)
        
        # Prepare payload for SageMaker
        # The SageMaker endpoint expects a JSON body with 'ticker' and 'date' (optional)
        # or whatever the input_fn expects.
        # Our updated input_fn in sagemaker_inference.py accepts JSON.
        
        payload = json.dumps(data)
        
        # Invoke Endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType='application/json',
            Body=payload
        )
        
        # Parse Response
        result = json.loads(response['Body'].read().decode())
        
        return jsonify(result)

    except Exception as e:
        print(f"Error invoking SageMaker endpoint: {e}")
        return jsonify({"error": str(e)}), 500

from apig_wsgi import make_lambda_handler
handler = make_lambda_handler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
