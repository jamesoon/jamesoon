# Low-Cost Model Drift Monitoring Solutions

## Cost Comparison

| Solution | Monthly Cost | Setup Time | Features |
|----------|-------------|------------|----------|
| **SageMaker Model Monitor** | $43-50 | 2-3 hours | Automated, enterprise-grade |
| **CloudWatch + DynamoDB + Lambda** | $0-2 | 1 hour | Custom, flexible |
| **Evidently AI (Open Source)** | $0 | 30 mins | Rich dashboards, local |
| **WhyLabs (Managed SaaS)** | $0-50 | 15 mins | Free tier: 10M rows |
| **Custom Prometheus + Grafana** | $0-5 | 2 hours | Real-time, self-hosted |

---

## **RECOMMENDED: CloudWatch + DynamoDB Solution**

### **Total Cost: $0-2/month** (within free tier)

**Why This Works**:
- ✅ Minimal changes to existing Lambda setup
- ✅ Stays within AWS free tier
- ✅ No additional infrastructure
- ✅ CloudWatch dashboards included
- ✅ SNS email alerts free (first 1,000)

### **Architecture**

```
┌─────────────────────────────────────────────────────────┐
│                    Prediction Flow                       │
└─────────────────────────────────────────────────────────┘

API Gateway → Lambda (Prediction)
                 ↓
                 ├─→ Return prediction to user
                 ├─→ Store in DynamoDB (PredictionHistory)
                 └─→ Send CloudWatch metrics

┌─────────────────────────────────────────────────────────┐
│                   Monitoring Flow                        │
└─────────────────────────────────────────────────────────┘

EventBridge (daily trigger)
    ↓
Lambda (Drift Analysis)
    ↓
    ├─→ Query last 7 days predictions (DynamoDB)
    ├─→ Query baseline (30 days ago)
    ├─→ Statistical tests (KS test, PSI)
    ├─→ Publish CloudWatch metrics
    └─→ SNS alert if drift detected
```

---

## **Implementation Steps**

### **Step 1: Create DynamoDB Table**

```bash
aws dynamodb create-table \
    --table-name ModelPredictionHistory \
    --attribute-definitions \
        AttributeName=modelName,AttributeType=S \
        AttributeName=timestamp,AttributeType=S \
    --key-schema \
        AttributeName=modelName,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --tags Key=Project,Value=SUTD-PRML \
    --region ap-southeast-1
```

**Schema**:
```json
{
  "modelName": "SPY-Predictor",
  "timestamp": "2025-11-30T12:00:00Z",
  "prediction": 1,
  "confidence": 0.87,
  "features": {
    "rsi": 65.3,
    "macd": 1.2,
    "volume": 1000000
  },
  "actual": null  // Updated later with ground truth
}
```

**Cost**: $0/month (free tier: 25GB storage, 200M requests)

---

### **Step 2: Update Prediction Lambda**

Add these lines to your existing prediction Lambda:

```python
import boto3
import json
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    # Your existing prediction code
    prediction = model.predict(features)
    confidence = model.predict_proba(features).max()
    
    # === NEW: Log prediction ===
    log_prediction(
        model_name='SPY-Predictor',
        prediction=int(prediction[0]),
        confidence=float(confidence),
        features=features_dict
    )
    
    # === NEW: Send metrics to CloudWatch ===
    send_cloudwatch_metrics(
        prediction=int(prediction[0]),
        confidence=float(confidence)
    )
    
    # Return prediction (existing code)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'prediction': int(prediction[0]),
            'confidence': float(confidence)
        })
    }

def log_prediction(model_name, prediction, confidence, features):
    """Store prediction in DynamoDB"""
    table = dynamodb.Table('ModelPredictionHistory')
    
    # Convert floats to Decimal for DynamoDB
    features_decimal = {k: Decimal(str(v)) for k, v in features.items()}
    
    table.put_item(Item={
        'modelName': model_name,
        'timestamp': datetime.utcnow().isoformat(),
        'prediction': prediction,
        'confidence': Decimal(str(confidence)),
        'features': features_decimal,
        'actual': None  # Update later
    })

def send_cloudwatch_metrics(prediction, confidence):
    """Send custom metrics to CloudWatch"""
    cloudwatch.put_metric_data(
        Namespace='MLOps/SPYPredictor',
        MetricData=[
            {
                'MetricName': 'PredictionValue',
                'Value': prediction,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'PredictionConfidence',
                'Value': confidence * 100,  # Convert to percentage
                'Unit': 'Percent',
                'Timestamp': datetime.utcnow()
            }
        ]
    )
```

**Cost**: $0.30/metric/month × 2 metrics = **$0.60/month**

---

### **Step 3: Create Drift Detection Lambda**

```python
import boto3
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from scipy import stats
import json

dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

def lambda_handler(event, context):
    """
    Analyze model drift - runs daily via EventBridge
    """
    
    # 1. Fetch recent predictions (last 7 days)
    recent_predictions = get_predictions(days=7)
    
    # 2. Fetch baseline predictions (30 days ago, 7 day window)
    baseline_predictions = get_predictions(days=7, offset_days=30)
    
    if len(recent_predictions) < 10 or len(baseline_predictions) < 10:
        print("Insufficient data for drift analysis")
        return
    
    # 3. Run drift tests
    drift_results = {
        'timestamp': datetime.utcnow().isoformat(),
        'tests': {}
    }
    
    # Test 1: Prediction Distribution Drift (Kolmogorov-Smirnov Test)
    recent_preds = [p['prediction'] for p in recent_predictions]
    baseline_preds = [p['prediction'] for p in baseline_predictions]
    
    ks_stat, ks_pvalue = stats.ks_2samp(recent_preds, baseline_preds)
    drift_results['tests']['prediction_distribution'] = {
        'ks_statistic': float(ks_stat),
        'p_value': float(ks_pvalue),
        'drift_detected': ks_pvalue < 0.05
    }
    
    # Test 2: Confidence Drift
    recent_conf = [float(p['confidence']) for p in recent_predictions]
    baseline_conf = [float(p['confidence']) for p in baseline_predictions]
    
    conf_mean_recent = np.mean(recent_conf)
    conf_mean_baseline = np.mean(baseline_conf)
    conf_drift = abs(conf_mean_recent - conf_mean_baseline)
    
    drift_results['tests']['confidence_drift'] = {
        'recent_mean': float(conf_mean_recent),
        'baseline_mean': float(conf_mean_baseline),
        'absolute_drift': float(conf_drift),
        'drift_detected': conf_drift > 0.10  # 10% threshold
    }
    
    # Test 3: Prediction Ratio Drift
    recent_up_ratio = sum(recent_preds) / len(recent_preds)
    baseline_up_ratio = sum(baseline_preds) / len(baseline_preds)
    ratio_drift = abs(recent_up_ratio - baseline_up_ratio)
    
    drift_results['tests']['prediction_ratio'] = {
        'recent_up_ratio': float(recent_up_ratio),
        'baseline_up_ratio': float(baseline_up_ratio),
        'drift': float(ratio_drift),
        'drift_detected': ratio_drift > 0.20  # 20% threshold
    }
    
    # Test 4: Feature Drift (PSI - Population Stability Index)
    feature_drifts = {}
    for feature_name in recent_predictions[0]['features'].keys():
        recent_vals = [float(p['features'][feature_name]) for p in recent_predictions]
        baseline_vals = [float(p['features'][feature_name]) for p in baseline_predictions]
        
        psi = calculate_psi(baseline_vals, recent_vals)
        feature_drifts[feature_name] = {
            'psi': float(psi),
            'drift_detected': psi > 0.2  # PSI > 0.2 indicates significant drift
        }
    
    drift_results['tests']['feature_drift'] = feature_drifts
    
    # 4. Send metrics to CloudWatch
    any_drift_detected = (
        drift_results['tests']['prediction_distribution']['drift_detected'] or
        drift_results['tests']['confidence_drift']['drift_detected'] or
        drift_results['tests']['prediction_ratio']['drift_detected'] or
        any(f['drift_detected'] for f in feature_drifts.values())
    )
    
    cloudwatch.put_metric_data(
        Namespace='MLOps/SPYPredictor/Drift',
        MetricData=[
            {
                'MetricName': 'KS_PValue',
                'Value': ks_pvalue,
                'Unit': 'None'
            },
            {
                'MetricName': 'ConfidenceDrift',
                'Value': conf_drift,
                'Unit': 'None'
            },
            {
                'MetricName': 'DriftDetected',
                'Value': 1 if any_drift_detected else 0,
                'Unit': 'Count'
            }
        ]
    )
    
    # 5. Alert if drift detected
    if any_drift_detected:
        send_drift_alert(drift_results)
    
    print(f"Drift analysis complete: {json.dumps(drift_results, indent=2)}")
    return drift_results


def get_predictions(days=7, offset_days=0):
    """Fetch predictions from DynamoDB"""
    table = dynamodb.Table('ModelPredictionHistory')
    
    end_time = datetime.utcnow() - timedelta(days=offset_days)
    start_time = end_time - timedelta(days=days)
    
    response = table.query(
        KeyConditionExpression='modelName = :model AND #ts BETWEEN :start AND :end',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ExpressionAttributeValues={
            ':model': 'SPY-Predictor',
            ':start': start_time.isoformat(),
            ':end': end_time.isoformat()
        }
    )
    
    return response['Items']


def calculate_psi(baseline, current, bins=10):
    """
    Calculate Population Stability Index (PSI)
    PSI < 0.1: No significant change
    PSI 0.1-0.2: Moderate change
    PSI > 0.2: Significant change (drift)
    """
    breakpoints = np.linspace(
        min(min(baseline), min(current)),
        max(max(baseline), max(current)),
        bins + 1
    )
    
    baseline_hist = np.histogram(baseline, bins=breakpoints)[0]
    current_hist = np.histogram(current, bins=breakpoints)[0]
    
    # Add small epsilon to avoid division by zero
    epsilon = 1e-10
    baseline_perc = (baseline_hist + epsilon) / (sum(baseline_hist) + epsilon * bins)
    current_perc = (current_hist + epsilon) / (sum(current_hist) + epsilon * bins)
    
    psi = sum((current_perc - baseline_perc) * np.log(current_perc / baseline_perc))
    return psi


def send_drift_alert(drift_results):
    """Send SNS alert when drift is detected"""
    
    # Format alert message
    message = "🚨 MODEL DRIFT DETECTED - SPY Predictor\n\n"
    message += f"Timestamp: {drift_results['timestamp']}\n\n"
    
    if drift_results['tests']['prediction_distribution']['drift_detected']:
        message += f"❌ Prediction Distribution Drift\n"
        message += f"   KS p-value: {drift_results['tests']['prediction_distribution']['p_value']:.4f}\n\n"
    
    if drift_results['tests']['confidence_drift']['drift_detected']:
        message += f"❌ Confidence Drift\n"
        message += f"   Recent: {drift_results['tests']['confidence_drift']['recent_mean']:.2%}\n"
        message += f"   Baseline: {drift_results['tests']['confidence_drift']['baseline_mean']:.2%}\n"
        message += f"   Drift: {drift_results['tests']['confidence_drift']['absolute_drift']:.2%}\n\n"
    
    if drift_results['tests']['prediction_ratio']['drift_detected']:
        message += f"❌ Prediction Ratio Drift\n"
        message += f"   Recent UP ratio: {drift_results['tests']['prediction_ratio']['recent_up_ratio']:.2%}\n"
        message += f"   Baseline UP ratio: {drift_results['tests']['prediction_ratio']['baseline_up_ratio']:.2%}\n\n"
    
    # Feature drifts
    feature_drifts = drift_results['tests']['feature_drift']
    drifted_features = [f for f, v in feature_drifts.items() if v['drift_detected']]
    if drifted_features:
        message += f"❌ Feature Drift Detected:\n"
        for feature in drifted_features:
            message += f"   {feature}: PSI = {feature_drifts[feature]['psi']:.3f}\n"
    
    message += "\n📊 View CloudWatch Dashboard: https://console.aws.amazon.com/cloudwatch/\n"
    
    # Send SNS notification
    sns.publish(
        TopicArn=os.environ['DRIFT_ALERT_TOPIC_ARN'],
        Subject='⚠️ Model Drift Alert - SPY Predictor',
        Message=message
    )
```

**Cost**: $0/month (1 invocation/day within free tier)

---

### **Step 4: Deploy Infrastructure**

```bash
# 1. Create SNS topic for alerts
aws sns create-topic --name model-drift-alerts --region ap-southeast-1

# 2. Subscribe your email
aws sns subscribe \
    --topic-arn arn:aws:sns:ap-southeast-1:ACCOUNT_ID:model-drift-alerts \
    --protocol email \
    --notification-endpoint your-email@example.com

# 3. Deploy drift detection Lambda
# (Package and deploy similar to trading-backend)

# 4. Create EventBridge rule (daily at 9 AM UTC)
aws events put-rule \
    --name daily-drift-check \
    --schedule-expression "cron(0 9 * * ? *)" \
    --region ap-southeast-1

# 5. Add Lambda as target
aws events put-targets \
    --rule daily-drift-check \
    --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:drift-detection"
```

---

### **Step 5: Create CloudWatch Dashboard**

```bash
# Create dashboard with drift metrics
aws cloudwatch put-dashboard \
    --dashboard-name SPY-Model-Monitoring \
    --dashboard-body file://dashboard-config.json
```

**dashboard-config.json**:
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["MLOps/SPYPredictor", "PredictionConfidence", {"stat": "Average"}],
          [".", ".", {"stat": "p50"}],
          [".", ".", {"stat": "p95"}]
        ],
        "period": 3600,
        "stat": "Average",
        "region": "ap-southeast-1",
        "title": "Model Confidence Over Time"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["MLOps/SPYPredictor/Drift", "KS_PValue"]
        ],
        "period": 86400,
        "stat": "Average",
        "region": "ap-southeast-1",
        "title": "Prediction Distribution Drift (KS Test p-value)",
        "annotations": {
          "horizontal": [{
            "value": 0.05,
            "label": "Drift Threshold"
          }]
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["MLOps/SPYPredictor", "PredictionValue", {"stat": "Sum", "label": "UP Predictions"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "ap-southeast-1",
        "title": "Prediction Distribution"
      }
    }
  ]
}
```

---

## **Cost Summary**

| Component | Cost/Month |
|-----------|------------|
| DynamoDB (storage + requests) | $0.00 (free tier) |
| CloudWatch metrics (2 custom) | $0.60 |
| Lambda invocations | $0.00 (free tier) |
| SNS notifications (email) | $0.00 (first 1,000) |
| CloudWatch Dashboard | $3.00 (first 3 free) |
| **TOTAL** | **$0.60 - $3.60/month** |

**Free tier benefits**:
- DynamoDB: 25 GB storage, 200M requests/month
- Lambda: 1M requests, 400,000 GB-seconds/month
- CloudWatch: First 3 dashboards free, 10 metrics free
- SNS: 1,000 email notifications/month

---

## **Alternative: Evidently AI (Free, Open Source)**

### **Cost: $0 (runs locally or in Lambda)**

**Pros**:
- Beautiful HTML drift reports
- Pre-built drift tests
- No AWS dependencies
- Can run in Lambda

**Setup**:
```python
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, DataQualityPreset

# Create drift report
report = Report(metrics=[
    DataDriftPreset(),
    DataQualityPreset()
])

report.run(reference_data=baseline_df, current_data=recent_df)
report.save_html('drift_report.html')

# Upload to S3 for viewing
s3.upload_file('drift_report.html', bucket, 'reports/drift_report.html')
```

**Sample Report**: Interactive HTML with:
- Feature drift visualization
- Distribution comparisons
- Statistical test results
- Recommended actions

---

## **Recommendation for Your Project**

**Use CloudWatch + DynamoDB + Lambda Solution**

**Why**:
1. **Cheapest**: $0.60-3.60/month vs $43-50 for SageMaker
2. **No infrastructure changes**: Works with existing Lambda setup
3. **Flexible**: Full control over drift logic
4. **Production-ready**: Enterprise AWS services
5. **Extensible**: Easy to add more metrics later

**Setup Time**: ~1 hour
**ROI**: Saves $40-47/month vs SageMaker

Want me to create the deployment scripts for this solution?

