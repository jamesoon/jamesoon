"""
AWS Lambda function for Trading Application Backend
Handles user profiles, portfolio, and transactions with DynamoDB
"""
import json
import os
import boto3
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key
from datetime import timedelta

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'TradingApp')
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert Decimal to float for JSON serialization"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def convert_floats_to_decimal(obj):
    """Convert floats to Decimal for DynamoDB"""
    if isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def cors_headers():
    """Return CORS headers for API responses"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }


def response(status_code, body):
    """Create API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': cors_headers(),
        'body': json.dumps(body, cls=DecimalEncoder)
    }


def get_user_profile(username):
    """Get user profile from DynamoDB"""
    try:
        result = table.get_item(
            Key={'userId': username, 'itemType': 'PROFILE'}
        )
        
        if 'Item' in result:
            return result['Item']
        else:
            # Initialize new user with default profile
            profile = {
                'userId': username,
                'itemType': 'PROFILE',
                'cashBalance': Decimal('100000'),
                'initialBalance': Decimal('100000'),
                'createdAt': datetime.utcnow().isoformat()
            }
            table.put_item(Item=profile)
            return profile
            
    except Exception as e:
        print(f"Error getting user profile: {str(e)}")
        return None


def update_user_profile(username, cash_balance):
    """Update user profile cash balance"""
    try:
        table.update_item(
            Key={'userId': username, 'itemType': 'PROFILE'},
            UpdateExpression='SET cashBalance = :cash',
            ExpressionAttributeValues={':cash': Decimal(str(cash_balance))}
        )
        return True
    except Exception as e:
        print(f"Error updating user profile: {str(e)}")
        return False


def get_portfolio(username):
    """Get user's portfolio from DynamoDB"""
    try:
        result = table.query(
            KeyConditionExpression=Key('userId').eq(username) & Key('itemType').begins_with('PORTFOLIO#')
        )
        
        portfolio = []
        for item in result.get('Items', []):
            portfolio.append({
                'ticker': item['ticker'],
                'shares': float(item['shares']),
                'averagePrice': float(item['averagePrice']),
                'currentPrice': float(item.get('currentPrice', item['averagePrice']))
            })
        
        return portfolio
        
    except Exception as e:
        print(f"Error getting portfolio: {str(e)}")
        return []


def update_portfolio_item(username, ticker, shares, average_price, current_price):
    """Update or create a portfolio item"""
    try:
        if shares == 0:
            # Delete item if shares are 0
            table.delete_item(
                Key={'userId': username, 'itemType': f'PORTFOLIO#{ticker}'}
            )
        else:
            # Update or create item
            table.put_item(Item={
                'userId': username,
                'itemType': f'PORTFOLIO#{ticker}',
                'ticker': ticker,
                'shares': Decimal(str(shares)),
                'averagePrice': Decimal(str(average_price)),
                'currentPrice': Decimal(str(current_price)),
                'updatedAt': datetime.utcnow().isoformat()
            })
        return True
    except Exception as e:
        print(f"Error updating portfolio: {str(e)}")
        return False


def add_transaction(username, ticker, trans_type, shares, price, total):
    """Add a transaction record"""
    try:
        timestamp = datetime.utcnow().isoformat()
        transaction_id = f"{timestamp}_{ticker}"
        
        table.put_item(Item={
            'userId': username,
            'itemType': f'TRANSACTION#{timestamp}',
            'transactionId': transaction_id,
            'ticker': ticker,
            'type': trans_type,
            'shares': Decimal(str(shares)),
            'price': Decimal(str(price)),
            'total': Decimal(str(total)),
            'date': timestamp
        })
        return True
    except Exception as e:
        print(f"Error adding transaction: {str(e)}")
        return False


def get_transactions(username, limit=50):
    """Get user's recent transactions"""
    try:
        result = table.query(
            KeyConditionExpression=Key('userId').eq(username) & Key('itemType').begins_with('TRANSACTION#'),
            ScanIndexForward=False,  # Sort descending (newest first)
            Limit=limit
        )
        
        transactions = []
        for item in result.get('Items', []):
            transactions.append({
                'id': item['transactionId'],
                'ticker': item['ticker'],
                'type': item['type'],
                'shares': float(item['shares']),
                'price': float(item['price']),
                'total': float(item['total']),
                'date': item['date']
            })
        
        return transactions
        
    except Exception as e:
        print(f"Error getting transactions: {str(e)}")
        return []


def calculate_trade_metrics(transactions):
    """
    Calculate confusion matrix based on trades vs actual 5-day return of SPY.
    Uses stored SPY data from DynamoDB (MARKET#SPY).
    
    TP: BUY & SPY UP
    FP: BUY & SPY DOWN
    TN: SELL & SPY DOWN
    FN: SELL & SPY UP
    """
    metrics = {
        'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0,
        'total_trades': 0,
        'accuracy': 0.0,
        'precision': 0.0,
        'recall': 0.0,
        'f1': 0.0
    }
    
    if not transactions:
        return metrics
        
    try:
        # 1. Get date range from transactions to fetch relevant SPY data
        # Transactions are YYYY-MM-DDTHH:MM:SS
        dates = [t['date'][:10] for t in transactions]
        if not dates:
            return metrics
            
        min_date = min(dates)
        # We need data up to max_date + 5 days (trading days approx included)
        # Simple upper bound: Now
        max_date_obj = datetime.now()
        max_date = max_date_obj.strftime('%Y-%m-%d')
        
        # 2. Query DynamoDB for SPY data associated with the date range
        # Since we can't easily query a range on Sort Key if Partition Key is fixed to MARKET#SPY 
        # and we want a subset, we use the timestamp range.
        # However, DynamoDB 'between' condition works on the sort key.
        # Our Sort Key is 'DATE#YYYY-MM-DD'.
        
        # Add buffer to min date in case of timezones, just to be safe
        query_start = f"DATE#{min_date}"
        query_end = f"DATE#{max_date}"
        
        response = table.query(
            KeyConditionExpression=Key('userId').eq('MARKET#SPY') & Key('itemType').between(query_start, query_end)
        )
        
        # Map: YYYY-MM-DD -> Close Price
        spy_prices = {}
        spy_dates = []
        for item in response.get('Items', []):
            d = item['date']
            spy_prices[d] = float(item['close'])
            spy_dates.append(d)
            
        spy_dates.sort()
        
        # 3. Evaluate each trade
        for t in transactions:
            trade_date = t['date'][:10]
            
            # Find entry (SPY price on trade date)
            # If exact date missing, maybe find next closest?
            # For simplicity, look for exact date or next available in our fetched list
            
            entry_date = None
            entry_price = None
            
            if trade_date in spy_prices:
                entry_date = trade_date
                entry_price = spy_prices[trade_date]
            else:
                # Find first date >= trade_date
                for d in spy_dates:
                    if d > trade_date:
                        entry_date = d
                        entry_price = spy_prices[d]
                        break
            
            if entry_price is None:
                continue # Cannot evaluate without entry price
                
            # Find exit (SPY price 5 days after entry date)
            # We look for a date that is at least 5 days after entry_date
            # Simple approximation: index of entry + 5? No, dates might be gaps.
            # Let's find a date that is >= entry_date + 5 calendar days
            
            entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
            target_dt = entry_dt + timedelta(days=5)
            target_date_str = target_dt.strftime('%Y-%m-%d')
            
            exit_price = None
            
            # Find first date >= target_date_str
            for d in spy_dates:
                if d >= target_date_str:
                    exit_price = spy_prices[d]
                    break
            
            if exit_price is None:
                # Not enough data yet (trade is too recent)
                continue
                
            # Calculate Return
            ret = (exit_price - entry_price) / entry_price
            is_price_up = ret > 0
            is_buy = t['type'] == 'BUY'
            
            if is_buy and is_price_up:
                metrics['tp'] += 1
            elif is_buy and not is_price_up:
                metrics['fp'] += 1
            elif not is_buy and not is_price_up:
                metrics['tn'] += 1
            elif not is_buy and is_price_up:
                metrics['fn'] += 1
                
            metrics['total_trades'] += 1

        # Calculate derived metrics
        total = metrics['total_trades']
        if total > 0:
            metrics['accuracy'] = (metrics['tp'] + metrics['tn']) / total
            
            if (metrics['tp'] + metrics['fp']) > 0:
                metrics['precision'] = metrics['tp'] / (metrics['tp'] + metrics['fp'])
            
            if (metrics['tp'] + metrics['fn']) > 0:
                metrics['recall'] = metrics['tp'] / (metrics['tp'] + metrics['fn'])
                
            if (metrics['precision'] + metrics['recall']) > 0:
                metrics['f1'] = 2 * (metrics['precision'] * metrics['recall']) / (metrics['precision'] + metrics['recall'])

    except Exception as e:
        print(f"Error calculating metrics: {str(e)}")
        
    return metrics


def calculate_daily_confusion_matrix(days=30):
    """
    Calculate confusion matrix for daily model predictions vs actual market moves.
    Compares PREDICTION#SPY vs MARKET#SPY (5-day return).
    """
    metrics = {
        'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0,
        'total_predictions': 0,
        'accuracy': 0.0,
        'precision': 0.0,
        'recall': 0.0,
        'f1': 0.0,
        'dates': [],
        'actual_returns': [],
        'predicted_signals': []
    }
    
    try:
        # 1. Get Predictions (PREDICTION#SPY)
        # Scan or Query last N days. For simplicity, let's query a range if possible, 
        # or just scan if volume is low. Query is better.
        # We need a date range.
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10) # Buffer
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        query_start = f"DATE#{start_str}"
        query_end = f"DATE#{end_str}"
        
        # Query Predictions
        pred_response = table.query(
            KeyConditionExpression=Key('userId').eq('PREDICTION#SPY') & Key('itemType').between(query_start, query_end)
        )
        predictions = pred_response.get('Items', [])
        
        if not predictions:
            return metrics
            
        # 2. Get Market Data (MARKET#SPY) for same range + 5 days forward
        market_end_date = end_date + timedelta(days=10)
        market_end_str = market_end_date.strftime('%Y-%m-%d')
        market_query_end = f"DATE#{market_end_str}"
        
        market_response = table.query(
            KeyConditionExpression=Key('userId').eq('MARKET#SPY') & Key('itemType').between(query_start, market_query_end)
        )
        market_data = market_response.get('Items', [])
        
        # Map Date -> Close Price
        market_prices = {item['date']: float(item['close']) for item in market_data}
        market_dates = sorted(market_prices.keys())
        
        # 3. Evaluate
        for pred in predictions:
            pred_date = pred['date']
            signal = pred['signal'] # BUY or SELL
            
            # Find entry price (Close on pred_date)
            if pred_date not in market_prices:
                continue
            
            entry_price = market_prices[pred_date]
            
            # Find exit price (Close 5 days later)
            # Logic: Find first date >= pred_date + 5 days
            pred_dt = datetime.strptime(pred_date, '%Y-%m-%d')
            target_dt = pred_dt + timedelta(days=5)
            target_str = target_dt.strftime('%Y-%m-%d')
            
            exit_price = None
            for d in market_dates:
                if d >= target_str:
                    exit_price = market_prices[d]
                    break
            
            if exit_price is None:
                continue # Not enough data yet
            
            # Calculate Actual Return
            actual_ret = (exit_price - entry_price) / entry_price
            is_actual_up = actual_ret > 0
            is_pred_buy = signal == 'BUY'
            
            # Update Metrics
            if is_pred_buy and is_actual_up:
                metrics['tp'] += 1
            elif is_pred_buy and not is_actual_up:
                metrics['fp'] += 1
            elif not is_pred_buy and not is_actual_up:
                metrics['tn'] += 1
            elif not is_pred_buy and is_actual_up:
                metrics['fn'] += 1
            
            metrics['total_predictions'] += 1
            metrics['dates'].append(pred_date)
            metrics['actual_returns'].append(actual_ret)
            metrics['predicted_signals'].append(1 if is_pred_buy else 0)
            
        # Calculate derived metrics
        total = metrics['total_predictions']
        if total > 0:
            metrics['accuracy'] = (metrics['tp'] + metrics['tn']) / total
            
            if (metrics['tp'] + metrics['fp']) > 0:
                metrics['precision'] = metrics['tp'] / (metrics['tp'] + metrics['fp'])
            
            if (metrics['tp'] + metrics['fn']) > 0:
                metrics['recall'] = metrics['tp'] / (metrics['tp'] + metrics['fn'])
                
            if (metrics['precision'] + metrics['recall']) > 0:
                metrics['f1'] = 2 * (metrics['precision'] * metrics['recall']) / (metrics['precision'] + metrics['recall'])
                
    except Exception as e:
        print(f"Error calculating daily matrix: {str(e)}")
        
    return metrics


def lambda_handler(event, context):
    """Main Lambda handler"""
    
    print(f"Event: {json.dumps(event)}")
    
    # Handle API Gateway v2 format (HTTP API)
    if 'requestContext' in event and 'http' in event['requestContext']:
        # API Gateway v2 (HTTP API)
        http_method = event['requestContext']['http']['method']
        path = event.get('rawPath', '')
    else:
        # API Gateway v1 (REST API) or direct invoke
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
    
    # Handle OPTIONS for CORS
    if http_method == 'OPTIONS':
        return response(200, {'message': 'OK'})
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        
        # Extract username from body, query params, or default to 'user'
        # For GET requests, check query parameters first
        query_params = event.get('queryStringParameters', {}) or {}
        username = query_params.get('username') or body.get('username', 'user')
        
        # Route requests
        if path == '/api/trading/health' or path == '/health':
            return response(200, {'status': 'healthy', 'service': 'trading-api'})
        
        elif path == '/api/trading/profile' and http_method == 'GET':
            profile = get_user_profile(username)
            if profile:
                return response(200, profile)
            else:
                return response(500, {'error': 'Failed to get profile'})
        
        elif path == '/api/trading/portfolio' and http_method == 'GET':
            portfolio = get_portfolio(username)
            return response(200, {'portfolio': portfolio})
        
        elif path == '/api/trading/transactions' and http_method == 'GET':
            transactions = get_transactions(username)
            return response(200, {'transactions': transactions})

        elif path == '/api/trading/metrics' and http_method == 'GET':
            # Get all transactions for metrics (limit 100 for performance)
            transactions = get_transactions(username, limit=100)
            metrics = calculate_trade_metrics(transactions)
            return response(200, metrics)

        elif path == '/api/reports/daily-matrix' and http_method == 'GET':
            # Daily Model Confusion Matrix
            metrics = calculate_daily_confusion_matrix(days=30)
            return response(200, metrics)
        
        elif path == '/api/trading/buy' and http_method == 'POST':
            ticker = body.get('ticker')
            shares = body.get('shares')
            price = body.get('price')
            
            if not all([ticker, shares, price]):
                return response(400, {'error': 'Missing required fields'})
            
            # Get current profile
            profile = get_user_profile(username)
            if not profile:
                return response(500, {'error': 'Failed to get profile'})
            
            cash_balance = float(profile['cashBalance'])
            total = shares * price
            
            # Check if sufficient funds
            if total > cash_balance:
                return response(400, {'error': 'Insufficient funds'})
            
            # Get current portfolio item
            portfolio = get_portfolio(username)
            existing = next((s for s in portfolio if s['ticker'] == ticker), None)
            
            if existing:
                # Update existing position
                total_shares = existing['shares'] + shares
                new_avg_price = ((existing['averagePrice'] * existing['shares']) + (price * shares)) / total_shares
                update_portfolio_item(username, ticker, total_shares, new_avg_price, price)
            else:
                # Create new position
                update_portfolio_item(username, ticker, shares, price, price)
            
            # Update cash balance
            new_balance = cash_balance - total
            update_user_profile(username, new_balance)
            
            # Add transaction
            add_transaction(username, ticker, 'BUY', shares, price, total)
            
            return response(200, {
                'success': True,
                'newBalance': new_balance,
                'message': f'Bought {shares} shares of {ticker}'
            })
        
        elif path == '/api/trading/sell' and http_method == 'POST':
            ticker = body.get('ticker')
            shares = body.get('shares')
            price = body.get('price')
            
            if not all([ticker, shares, price]):
                return response(400, {'error': 'Missing required fields'})
            
            # Get current profile
            profile = get_user_profile(username)
            if not profile:
                return response(500, {'error': 'Failed to get profile'})
            
            # Get current portfolio
            portfolio = get_portfolio(username)
            existing = next((s for s in portfolio if s['ticker'] == ticker), None)
            
            if not existing or existing['shares'] < shares:
                return response(400, {'error': 'Insufficient shares'})
            
            total = shares * price
            cash_balance = float(profile['cashBalance'])
            
            # Update portfolio
            new_shares = existing['shares'] - shares
            update_portfolio_item(username, ticker, new_shares, existing['averagePrice'], price)
            
            # Update cash balance
            new_balance = cash_balance + total
            update_user_profile(username, new_balance)
            
            # Add transaction
            add_transaction(username, ticker, 'SELL', shares, price, total)
            
            return response(200, {
                'success': True,
                'newBalance': new_balance,
                'message': f'Sold {shares} shares of {ticker}'
            })
        
        elif path == '/api/trading/sync' and http_method == 'POST':
            # Full sync endpoint - upload entire state
            profile_data = body.get('profile', {})
            portfolio_data = body.get('portfolio', [])
            transactions_data = body.get('transactions', [])
            
            # Update profile
            if profile_data:
                table.put_item(Item={
                    'userId': username,
                    'itemType': 'PROFILE',
                    'cashBalance': Decimal(str(profile_data.get('cashBalance', 100000))),
                    'initialBalance': Decimal(str(profile_data.get('initialBalance', 100000))),
                    'updatedAt': datetime.utcnow().isoformat()
                })
            
            # Update portfolio
            for stock in portfolio_data:
                update_portfolio_item(
                    username,
                    stock['ticker'],
                    stock['shares'],
                    stock['averagePrice'],
                    stock.get('currentPrice', stock['averagePrice'])
                )
            
            # Add transactions (only new ones)
            for trans in transactions_data[:10]:  # Limit to last 10
                add_transaction(
                    username,
                    trans['ticker'],
                    trans['type'],
                    trans['shares'],
                    trans['price'],
                    trans['total']
                )
            
            return response(200, {'success': True, 'message': 'Data synced'})
        
        else:
            return response(404, {'error': 'Not found'})
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {'error': str(e)})

