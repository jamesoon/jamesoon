import time
import requests
import logging
import os
from prometheus_client import start_http_server, Gauge, Histogram, Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Metrics definition
SYSTEM_HEALTH = Gauge(
    'system_health_status',
    'Health status of the component (1 = Healthy, 0 = Unhealthy)',
    ['component', 'url']
)

REQUEST_LATENCY = Histogram(
    'api_request_latency_seconds',
    'Latency of API requests in seconds',
    ['component', 'method']
)

REQUEST_COUNT = Counter(
    'api_request_count',
    'Total number of API requests',
    ['component', 'method', 'status']
)

# Configuration
# You can override these with environment variables
CONFIG = {
    'Frontend': os.getenv('FRONTEND_URL', 'https://prml.mdaie-sutd.fit'),
    'Market Data API': os.getenv('MARKET_DATA_API_URL', 'https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/api/market-indices'),
    'Trading API': os.getenv('TRADING_API_URL', 'https://m6dc44h91f.execute-api.ap-southeast-1.amazonaws.com/health'),
    'Prediction API': os.getenv('PREDICTION_API_URL', 'https://0qoytg0cfg.execute-api.ap-southeast-1.amazonaws.com/prod/predict'),
}

def check_endpoint(component, url, method='GET', payload=None):
    """
    Checks an endpoint and updates metrics.
    """
    logger.info(f"Checking {component} at {url}...")
    
    start_time = time.time()
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=payload, timeout=10)
        else:
            logger.error(f"Unsupported method {method}")
            return

        latency = time.time() - start_time
        
        # Update metrics
        REQUEST_LATENCY.labels(component=component, method=method).observe(latency)
        REQUEST_COUNT.labels(component=component, method=method, status=response.status_code).inc()
        
        # Determine health (2xx or 3xx is usually healthy)
        is_healthy = 1 if 200 <= response.status_code < 400 else 0
        SYSTEM_HEALTH.labels(component=component, url=url).set(is_healthy)
        
        logger.info(f"{component}: Status {response.status_code}, Latency {latency:.4f}s")
        
    except requests.RequestException as e:
        logger.error(f"Error checking {component}: {e}")
        SYSTEM_HEALTH.labels(component=component, url=url).set(0)
        # We can verify connection errors as status 0 or 503
        REQUEST_COUNT.labels(component=component, method=method, status='error').inc()

def run_monitoring_loop(interval=60):
    """
    Main monitoring loop.
    """
    logger.info(f"Starting monitoring loop. Metrics exposed on port 8000")
    
    # Start Prometheus HTTP server
    start_http_server(8000)
    
    while True:
        # 1. Check Frontend
        check_endpoint('Frontend', CONFIG['Frontend'])
        
        # 2. Check Market Data API
        check_endpoint('Market Data API', CONFIG['Market Data API'])
        
        # 3. Check Trading API (Health check)
        # Note: If /health doesn't exist, we might get 403/404, but we check reachability
        check_endpoint('Trading API', CONFIG['Trading API'])
        
        # 4. Check Prediction API
        # We assume a GET request might return 405 or 400 if payload missing, but proves connectivity
        # Or we can try a dummy POST if we know the schema
        check_endpoint('Prediction API', CONFIG['Prediction API'], method='GET')
        
        time.sleep(interval)

if __name__ == '__main__':
    run_monitoring_loop()
