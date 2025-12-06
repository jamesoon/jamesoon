# ML Model Inference Requirements

## Overview
The SPY trading prediction model requires a complete feature engineering pipeline to make predictions. It doesn't just take raw price data - it needs 80 engineered features computed from 8 different market instruments.

---

## 1. Model Artifact Structure

The `model.pkl` file contains a dictionary with:

```python
{
    'model': Pipeline(StandardScaler + LinearRegression),
    'feature_columns': list[str],  # 80 feature names in exact order
    'lags': [1, 2, 5],              # Lag periods for features
    'train_start_date': '2015-01-01'  # Minimum historical data needed
}
```

**Key Point**: The model expects exactly **80 features** in a specific order.

---

## 2. Required Market Data

To generate the 80 features, you need historical price data for **8 tickers**:

| Ticker | Name | Purpose |
|--------|------|---------|
| **SPY** | S&P 500 ETF | Primary prediction target |
| **QQQ** | Nasdaq 100 ETF | Tech sector momentum |
| **GOLD** | Gold (GLD ETF) | Safe haven/inflation hedge |
| **OIL** | Oil (USO ETF) | Commodity/inflation proxy |
| **TLT** | 20Y Treasury Bonds | Long-term interest rates |
| **SHY** | 1-3Y Treasury Bonds | Short-term interest rates |
| **VIX** | Volatility Index (^VIX) | Market fear gauge |
| **DXY** | US Dollar Index (DX-Y.NYB) | Currency strength |

### Historical Depth Required
- **Minimum**: 60 trading days before prediction date
- **Recommended**: 100+ days for robust rolling calculations
- **Training**: From 2015-01-01 (2700+ days)

---

## 3. Feature Engineering Pipeline

### Step 1: Base Features (20 features)

Computed directly from price data:

#### SPY-Specific (5 features)
- `spy_ret_1d`: 1-day return
- `spy_ret_5d`: 5-day return  
- `spy_rsi14`: 14-day RSI momentum indicator
- `spy_dist_ma20`: Distance from 20-day moving average (%)
- `spy_vol_z20`: Volume z-score (20-day)

#### Cross-Asset Features (15 features)
- `qqq_ret_5d`: QQQ 5-day return
- `qqq_over_spy_ratio`: QQQ/SPY price ratio
- `gold_ret_5d`: Gold 5-day return
- `oil_ret_5d`: Oil 5-day return
- `tlt_ret_5d`: TLT 5-day return
- `shy_ret_5d`: SHY 5-day return
- `tlt_shy_spread`: TLT - SHY return spread
- `vix_lvl`: VIX level (absolute)
- `vix_chg_5d`: VIX 5-day change
- `dxy_ret_5d`: Dollar Index 5-day return
- `spy_corr_gold_20`: 20-day rolling correlation (SPY-Gold)
- `spy_corr_qqq_20`: 20-day rolling correlation (SPY-QQQ)
- `curve_proxy_tlt_shy`: log(TLT/SHY) yield curve proxy
- `inflation_proxy_oil_minus_gold`: Oil - Gold return difference
- `riskoff_proxy_vix_plus_dxy`: Standardized VIX + DXY (risk-off indicator)

### Step 2: Lagged Features (60 additional features)

For each of the 20 base features, create lagged versions:
- `{feature}_lag1`: Yesterday's value
- `{feature}_lag2`: 2 days ago value
- `{feature}_lag5`: 5 days ago value

**Total**: 20 base × (1 + 3 lags) = **80 features**

### Step 3: Data Alignment

After computing features:
1. Drop rows with NaN (from rolling windows and lags)
2. Align features to model's expected column order
3. Extract latest row (most recent trading day)
4. Pass single row (1 × 80) to model

---

## 4. Data Format Requirements

### Input Data Structure

**Option A: Live yfinance Download**
```python
raw_data = yf.download(
    tickers="SPY QQQ GLD USO TLT SHY ^VIX DX-Y.NYB",
    start="2015-01-01",
    auto_adjust=True,
    group_by="ticker"
)
# Returns: MultiIndex DataFrame with (Ticker, OHLCV) columns
```

**Option B: Pre-loaded S3/Parquet**
```python
# MultiIndex format: (Ticker, Field)
# Fields: Open, High, Low, Close, Volume
# Index: DatetimeIndex (timezone-naive, date-only)
# Normalized ticker names: SPY, QQQ, GOLD, OIL, TLT, SHY, VIX, DXY
```

### Critical Format Rules
1. ✅ **Index**: DatetimeIndex, timezone-naive, no duplicates
2. ✅ **Columns**: MultiIndex with (Ticker, Field) structure
3. ✅ **Ticker Names**: Normalized (GOLD not GLD, OIL not USO, VIX not ^VIX, DXY not DX-Y.NYB)
4. ✅ **No Missing Data**: All 8 tickers must have data for common dates

---

## 5. Inference Process Flow

```
1. Load Model Artifact
   └─> Extract: model, feature_columns, lags, train_start_date

2. Download/Load Market Data
   └─> Get OHLCV data for 8 tickers from train_start_date to today

3. Compute Base Features (20 features)
   ├─> Extract Close/Volume for each ticker
   ├─> Calculate returns, RSI, moving averages, correlations
   └─> Drop NaN rows (first ~60 rows)

4. Add Lagged Features (60 additional features)
   ├─> For each base feature, create lag1, lag2, lag5
   └─> Drop NaN rows (first 5 additional rows)

5. Align Features
   ├─> Reorder columns to match model's feature_columns
   ├─> Verify all 80 columns present
   └─> Extract latest row (1 × 80 array)

6. Make Prediction
   ├─> Pass feature array to model.predict()
   ├─> Get predicted return (e.g., -0.002472 = -0.25%)
   └─> Generate BUY/SELL signal

7. Format Result
   └─> Return: signal, predicted prices, return, date
```

---

## 6. Python Dependencies

```txt
# Core ML
scikit-learn>=1.0.0    # Pipeline, StandardScaler, LinearRegression
numpy>=1.21.0,<2.0.0   # NumPy 1.x (model pickled with NumPy 1.x)
pandas>=1.3.0          # DataFrame operations

# Data Sources
yfinance>=0.2.0        # Yahoo Finance API
boto3>=1.26.0          # AWS S3 (optional, for pre-loaded data)
pyarrow>=10.0.0        # Parquet file format (optional)

# API
flask>=2.0.0           # REST API server

# Utilities
python-dateutil>=2.8.0
```

---

## 7. Minimal Inference Example

```python
import pickle
import pandas as pd
import yfinance as yf

# 1. Load model
with open('model.pkl', 'rb') as f:
    artifact = pickle.load(f)
model = artifact['model']
feature_columns = artifact['feature_columns']
lags = artifact['lags']

# 2. Download data
tickers_yf = "SPY QQQ GLD USO TLT SHY ^VIX DX-Y.NYB"
raw = yf.download(tickers_yf, start="2015-01-01", auto_adjust=True, group_by="ticker")

# 3. Compute features (see app.py for full implementation)
base_features, spy_close = compute_base_features(raw)
lagged_features = add_lagged_features(base_features, lags=lags)

# 4. Prepare input
X = lagged_features[feature_columns].iloc[-1:]  # Latest row

# 5. Predict
pred_return = model.predict(X)[0]
signal = "BUY" if pred_return > 0 else "SELL"

print(f"Signal: {signal}, Predicted Return: {pred_return:.2%}")
```

---

## 8. API Endpoints

### Health Check
```bash
GET /healthcheck
Response: {
  "status": "healthy",
  "model_loaded": true,
  "has_feature_columns": true
}
```

### Prediction
```bash
POST /predict
Content-Type: application/json

Request Body:
{
  "ticker": "SPY",           # Optional (currently only SPY supported)
  "date": "2024-01-15"       # Optional (uses latest if not provided)
}

Response:
{
  "signal_date": "2024-01-15",
  "pred_open_930": 478.50,
  "pred_close_1600": 478.20,
  "pred_intraday_change": -0.30,
  "pred_intraday_return": -0.000627,
  "signal": "SELL",
  "prediction": [0]
}
```

---

## 9. Common Issues

### Issue: "All rows dropped after dropna()"
**Cause**: Not enough historical data or data alignment issues  
**Solution**: Ensure at least 100 trading days of data for all 8 tickers

### Issue: "Missing columns in inference features"
**Cause**: Feature engineering doesn't match training  
**Solution**: Use exact same `compute_base_features()` and `add_lagged_features()` functions

### Issue: "Could not find GOLD data"
**Cause**: Ticker naming mismatch (GLD vs GOLD)  
**Solution**: Use normalized ticker names or update `download_price_data()` to handle mapping

### Issue: NumPy version mismatch
**Cause**: Model pickled with NumPy 2.x, running on NumPy 1.x  
**Solution**: Use `CompatUnpickler` class in `app.py` (already implemented)

---

## 10. Performance Considerations

### Latency Sources
- **yfinance download**: 2-5 seconds (can be slow/unreliable)
- **Feature computation**: <100ms (fast, pure pandas/numpy)
- **Model prediction**: <10ms (very fast)

### Optimization Strategy
✅ **Implemented**: Use S3 pre-loaded data instead of live yfinance  
- Store daily OHLCV data in S3 as Parquet
- Lambda function updates S3 daily (EventBridge trigger)
- Inference loads from S3 (100-200ms) instead of yfinance (2-5s)
- **Latency improvement**: ~10-20x faster

---

## Summary

The model requires:
1. ✅ **80 engineered features** (20 base + 60 lagged)
2. ✅ **8 market instruments** (SPY, QQQ, GOLD, OIL, TLT, SHY, VIX, DXY)
3. ✅ **100+ days of history** for rolling calculations
4. ✅ **Exact feature order** matching training
5. ✅ **Normalized data format** (timezone-naive, no duplicates, consistent ticker names)

The entire pipeline is encapsulated in `app.py` and can be tested with `test_model.py`.

