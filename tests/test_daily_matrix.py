import sys
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal
import boto3
from moto import mock_aws

# Add backend directory to path
sys.path.append(os.path.abspath("backend"))

@mock_aws
def test_daily_confusion_matrix():
    # Mock DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='TradingApp',
        KeySchema=[
            {'AttributeName': 'userId', 'KeyType': 'HASH'},
            {'AttributeName': 'itemType', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'userId', 'AttributeType': 'S'},
            {'AttributeName': 'itemType', 'AttributeType': 'S'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    
    # Import after mocking
    import lambda_trading
    lambda_trading.table = table
    from lambda_trading import calculate_daily_confusion_matrix
    
    # Setup Data
    # Use dates relative to now to ensure they fall within the query range
    today = datetime.now()
    d1 = (today - timedelta(days=20)).strftime('%Y-%m-%d')
    d2 = (today - timedelta(days=19)).strftime('%Y-%m-%d')
    d1_exit = (today - timedelta(days=15)).strftime('%Y-%m-%d') # approx 5 days after d1
    d2_exit = (today - timedelta(days=14)).strftime('%Y-%m-%d') # approx 5 days after d2
    
    # 1. Market Data (SPY)
    dates = [
        (d1, 100.0), # Pred Date 1
        (d2, 101.0), # Pred Date 2
        (d1_exit, 105.0), # Exit for Date 1 (Up)
        (d2_exit, 95.0),  # Exit for Date 2 (Down)
    ]
    
    for d, price in dates:
        table.put_item(Item={
            'userId': 'MARKET#SPY',
            'itemType': f'DATE#{d}',
            'date': d,
            'close': Decimal(str(price))
        })
        
    # 2. Predictions
    # Pred 1: Date d1 (Entry 100). Exit d1_exit (105). Return > 0.
    # Signal: BUY -> TP
    
    # Pred 2: Date d2 (Entry 101). Exit d2_exit (95). Return < 0.
    # Signal: BUY -> FP
    
    predictions = [
        (d1, 'BUY'),
        (d2, 'BUY')
    ]
    
    for d, signal in predictions:
        table.put_item(Item={
            'userId': 'PREDICTION#SPY',
            'itemType': f'DATE#{d}',
            'date': d,
            'signal': signal,
            'pred_return': Decimal('0.01'),
            'current_price': Decimal('100'),
            'prob_up': Decimal('0.6')
        })
        
    # Run Calculation
    metrics = calculate_daily_confusion_matrix(days=30)
    
    print("Metrics:", json.dumps(metrics, indent=2))
    
    # Assertions
    assert metrics['total_predictions'] == 2
    assert metrics['tp'] == 1
    assert metrics['fp'] == 1
    assert metrics['tn'] == 0
    assert metrics['fn'] == 0
    assert metrics['accuracy'] == 0.5
    assert metrics['precision'] == 0.5
    
    print("Test Passed!")

if __name__ == "__main__":
    test_daily_confusion_matrix()
