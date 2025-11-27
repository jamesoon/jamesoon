"""
AWS Lambda function for fetching real-time market data from Yahoo Finance
Fronted by API Gateway
"""

import json
import boto3
from datetime import datetime, timedelta
import yfinance as yf
from decimal import Decimal

# Initialize DynamoDB for caching (optional)
dynamodb = boto3.resource('dynamodb')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def get_market_data():
    """
    Fetch market indices data from Yahoo Finance for the past 3 months
    """
    indices = [
        {'name': 'DOW', 'symbol': '^DJI'},
        {'name': 'NASDAQ', 'symbol': '^IXIC'},
        {'name': 'S&P 500', 'symbol': '^GSPC'},
        {'name': 'RUSSELL 2000', 'symbol': '^RUT'},
    ]
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # 3 months
    
    results = []
    
    for index in indices:
        try:
            # Fetch data using yfinance
            ticker = yf.Ticker(index['symbol'])
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                print(f"No data for {index['name']}")
                continue
            
            # Prepare chart data
            chart_data = []
            for date, row in hist.iterrows():
                chart_data.append({
                    'date': date.strftime('%b %d'),
                    'open': round(float(row['Open']), 2),
                    'high': round(float(row['High']), 2),
                    'low': round(float(row['Low']), 2),
                    'close': round(float(row['Close']), 2),
                    'openClose': [round(float(row['Open']), 2), round(float(row['Close']), 2)]
                })
            
            # Calculate current and change
            current = float(hist['Close'].iloc[-1])
            previous = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current
            change = current - previous
            change_percent = (change / previous) * 100
            
            results.append({
                'name': index['name'],
                'symbol': index['symbol'],
                'current': round(current, 2),
                'change': round(change, 2),
                'changePercent': round(change_percent, 2),
                'color': '#4caf50' if change >= 0 else '#f44336',
                'chartData': chart_data
            })
            
            print(f"✓ Fetched {index['name']}: {current:.2f}")
            
        except Exception as e:
            print(f"Error fetching {index['name']}: {str(e)}")
            continue
    
    return results

def lambda_handler(event, context):
    """
    AWS Lambda handler function
    """
    print(f"Event: {json.dumps(event)}")
    
    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': ''
        }
    
    try:
        # Route handling
        path = event.get('path', '')
        http_method = event.get('httpMethod', 'GET')
        
        # Health check endpoint
        if path == '/health' or path == '/api/health':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'ok',
                    'message': 'SUTD Trading Market Data API',
                    'timestamp': datetime.now().isoformat()
                })
            }
        
        # Market indices endpoint
        if path in ['/market-indices', '/api/market-indices']:
            if http_method == 'GET':
                market_data = get_market_data()
                
                if not market_data:
                    return {
                        'statusCode': 500,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'error': 'Failed to fetch market data'
                        })
                    }
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps(market_data)
                }
        
        # Default: not found
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Not found',
                'path': path
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }

