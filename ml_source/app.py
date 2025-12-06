"""
Flask app for ML inference using S3-stored market data.
This version loads data from S3 instead of downloading on-demand.
"""

import pickle
import warnings
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from datetime import datetime
import boto3
from io import BytesIO
import os

warnings.filterwarnings("ignore")

app = Flask(__name__)

# AWS Configuration
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'your-market-data-bucket')
S3_KEY = os.environ.get('S3_DATA_KEY', 'market_data_normalized.parquet')
USE_S3 = os.environ.get('USE_S3', 'true').lower() == 'true'

# Initialize S3 client
s3_client = None
if USE_S3:
    try:
        s3_client = boto3.client('s3')
        print(f"✓ S3 client initialized. Bucket: {S3_BUCKET}")
    except Exception as e:
        print(f"⚠ Warning: Could not initialize S3 client: {e}")
        print("  Falling back to yfinance downloads")
        USE_S3 = False

# Ticker configuration
TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GOLD",  # S3 data uses GOLD (not GLD)
    "OIL": "OIL",    # S3 data uses OIL (not USO)
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "VIX",    # S3 data uses VIX (not ^VIX)
    "DXY": "DXY",    # S3 data uses DXY (not DX-Y.NYB)
}

# Default lags (will be overridden by model artifact if present)
LAGS = [1, 2, 5]

# Global cache for market data
_market_data_cache = None
_cache_timestamp = None

# Load the model artifact
try:
    # Debug: List files
    print(f"Current CWD: {os.getcwd()}")
    print(f"Files in CWD: {os.listdir('.')}")
    
    # Try loading from current directory (Docker/Lambda) first, then ml_source (Local)
    model_path = 'model.pkl'
    if not os.path.exists(model_path):
        model_path = 'ml_source/model.pkl'
        
    with open(model_path, 'rb') as f:
        artifact = pickle.load(f)
    
    print(f"DEBUG: Artifact loaded. Type: {type(artifact)}")
    
    # Handle both old format (just model) and new format (artifact dict)
    if isinstance(artifact, dict):
        print(f"DEBUG: Artifact keys: {artifact.keys()}")
        # Load Linear Model (for price targets)
        model = artifact.get('model')
        if model is None:
            model = artifact.get('linear_model')
            
        # Load Logistic Model (for signals)
        logistic_model = artifact.get('logistic_model')
        threshold = artifact.get('threshold', 0.5)
        
        if model is None:
            print("DEBUG: Linear model missing!")
        else:
            print(f"DEBUG: Linear Model loaded. Type: {type(model)}")
            
        if logistic_model is None:
            print("DEBUG: Logistic model missing! Will fallback to linear model for signals.")
        else:
            print(f"DEBUG: Logistic Model loaded. Type: {type(logistic_model)}")
            print(f"DEBUG: Threshold: {threshold}")
            
        feature_columns = artifact.get('feature_columns')
        lags = artifact.get('lags', LAGS)
        train_start_date = artifact.get('train_start_date', '2015-01-01')
    else:
        # Legacy format: just the model
        model = artifact
        logistic_model = None
        threshold = 0.5
        feature_columns = None
        lags = LAGS
        train_start_date = '2015-01-01'
except Exception as e:
    print(f"ERROR loading model: {e}")
    import traceback
    traceback.print_exc()
    model = None
    logistic_model = None
    threshold = 0.5
    feature_columns = None
    lags = LAGS
    train_start_date = '2015-01-01'


def load_market_data_from_s3():
    """Load market data from S3."""
    global _market_data_cache, _cache_timestamp
    
    try:
        print(f"Loading data from s3://{S3_BUCKET}/{S3_KEY}...")
        obj = s3_client.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        df = pd.read_parquet(BytesIO(obj['Body'].read()))
        
        _market_data_cache = df
        _cache_timestamp = datetime.now()
        
        print(f"✓ Loaded {len(df)} rows from S3")
        print(f"  Date range: {df.index[0]} to {df.index[-1]}")
        
        return df
    except Exception as e:
        print(f"✗ Error loading from S3: {str(e)}")
        raise ValueError(f"Failed to load data from S3: {str(e)}")


def get_market_data(use_cache=True, max_cache_age_minutes=60):
    """
    Get market data, using cache if available and fresh.
    
    Parameters:
    -----------
    use_cache : bool
        Whether to use cached data
    max_cache_age_minutes : int
        Maximum age of cache in minutes before refreshing
    """
    global _market_data_cache, _cache_timestamp
    
    if USE_S3:
        # Check cache
        if use_cache and _market_data_cache is not None and _cache_timestamp:
            age_minutes = (datetime.now() - _cache_timestamp).total_seconds() / 60
            if age_minutes < max_cache_age_minutes:
                print(f"Using cached data (age: {age_minutes:.1f} minutes)")
                return _market_data_cache.copy()
        
        # Load from S3
        return load_market_data_from_s3()
    else:
        # Fallback to yfinance (original behavior)
        import yfinance as yf
        
        def download_price_data(tickers_dict, start_date="2015-01-01", end_date=None, auto_adjust=True):
            yf_tickers = " ".join(tickers_dict.values())
            data = yf.download(
                yf_tickers,
                start=start_date,
                end=end_date,
                auto_adjust=auto_adjust,
                group_by="ticker",
                progress=False
            )
            if isinstance(data.columns, pd.MultiIndex):
                return data.sort_index(axis=1)
            symbol = list(tickers_dict.keys())[0]
            return pd.concat({symbol: data}, axis=1).sort_index(axis=1)
        
        return download_price_data(TICKERS, start_date=train_start_date)


def compute_rsi(series, window=14):
    """
    Compute RSI (Relative Strength Index) for a price series.
    Uses the classic Wilder's smoothing approach.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_base_features(raw):
    """
    Compute all base (non-lagged) features from raw price data.
    """
    # Extract per-symbol data for convenience
    # Use TICKERS mapping for both MultiIndex check and flat column access
    spy = raw[TICKERS["SPY"]] if (TICKERS["SPY"], "Close") in raw.columns else raw[TICKERS["SPY"]]
    qqq = raw[TICKERS["QQQ"]] if (TICKERS["QQQ"], "Close") in raw.columns else raw[TICKERS["QQQ"]]
    gld = raw[TICKERS["GOLD"]] if (TICKERS["GOLD"], "Close") in raw.columns else raw[TICKERS["GOLD"]]
    uso = raw[TICKERS["OIL"]] if (TICKERS["OIL"], "Close") in raw.columns else raw[TICKERS["OIL"]]
    tlt = raw[TICKERS["TLT"]] if (TICKERS["TLT"], "Close") in raw.columns else raw[TICKERS["TLT"]]
    shy = raw[TICKERS["SHY"]] if (TICKERS["SHY"], "Close") in raw.columns else raw[TICKERS["SHY"]]
    vix = raw[TICKERS["VIX"]] if (TICKERS["VIX"], "Close") in raw.columns else raw[TICKERS["VIX"]]
    dxy = raw[TICKERS["DXY"]] if (TICKERS["DXY"], "Close") in raw.columns else raw[TICKERS["DXY"]]

    def get_close(df):
        """Extract Close or Adj Close column, handling both MultiIndex and flat columns."""
        # Handle MultiIndex columns (e.g., ("SPY", "Adj Close"))
        if isinstance(df.columns, pd.MultiIndex):
            # Try Adj Close first, then Close
            for col_name in ["Adj Close", "Close"]:
                for col in df.columns:
                    if col[1] == col_name:  # Second level matches
                        return df[col]
            raise KeyError(f"Could not find Close or Adj Close in columns: {list(df.columns)}")
        else:
            # Flat columns
            if "Adj Close" in df.columns:
                return df["Adj Close"]
            elif "Close" in df.columns:
                return df["Close"]
            else:
                raise KeyError(f"Could not find Close or Adj Close in columns: {list(df.columns)}")
    
    def get_volume(df):
        """Extract Volume column, handling both MultiIndex and flat columns."""
        if isinstance(df.columns, pd.MultiIndex):
            for col in df.columns:
                if col[1] == "Volume":
                    return df[col]
            raise KeyError(f"Could not find Volume in columns: {list(df.columns)}")
        else:
            if "Volume" in df.columns:
                return df["Volume"]
            else:
                raise KeyError(f"Could not find Volume in columns: {list(df.columns)}")

    # Initialize features DataFrame on SPY's index
    # features = pd.DataFrame(index=spy_close.index) # Moved down
    
    # Debug: Check data sizes
    print(f"DEBUG: compute_base_features - raw shape: {raw.shape}")
    
    # Fix data alignment: Normalize index to date and aggregate
    # This handles cases where different tickers have slightly different timestamps (e.g. 05:00 vs 06:00)
    # causing interleaved NaNs.
    if not raw.empty:
        raw.index = raw.index.normalize()
        raw = raw.groupby(raw.index).max()
        print(f"DEBUG: compute_base_features - raw shape after normalize/groupby: {raw.shape}")

    # Re-extract per-symbol data after alignment
    spy = raw[TICKERS["SPY"]] if (TICKERS["SPY"], "Close") in raw.columns else raw[TICKERS["SPY"]]
    qqq = raw[TICKERS["QQQ"]] if (TICKERS["QQQ"], "Close") in raw.columns else raw[TICKERS["QQQ"]]
    gld = raw[TICKERS["GOLD"]] if (TICKERS["GOLD"], "Close") in raw.columns else raw[TICKERS["GOLD"]]
    uso = raw[TICKERS["OIL"]] if (TICKERS["OIL"], "Close") in raw.columns else raw[TICKERS["OIL"]]
    tlt = raw[TICKERS["TLT"]] if (TICKERS["TLT"], "Close") in raw.columns else raw[TICKERS["TLT"]]
    shy = raw[TICKERS["SHY"]] if (TICKERS["SHY"], "Close") in raw.columns else raw[TICKERS["SHY"]]
    vix = raw[TICKERS["VIX"]] if (TICKERS["VIX"], "Close") in raw.columns else raw[TICKERS["VIX"]]
    dxy = raw[TICKERS["DXY"]] if (TICKERS["DXY"], "Close") in raw.columns else raw[TICKERS["DXY"]]

    # We'll work with Adjusted Close and Volume where applicable
    spy_close = get_close(spy).copy()
    spy_vol = get_volume(spy).copy()

    qqq_close = get_close(qqq).copy()
    gld_close = get_close(gld).copy()
    uso_close = get_close(uso).copy()
    tlt_close = get_close(tlt).copy()
    shy_close = get_close(shy).copy()
    vix_close = get_close(vix).copy()
    dxy_close = get_close(dxy).copy()

    # Initialize features DataFrame on SPY's index
    features = pd.DataFrame(index=spy_close.index)

    print(f"DEBUG: compute_base_features - spy_close len: {len(spy_close)}")
    if len(spy_close) > 0:
        print(f"DEBUG: spy_close head:\n{spy_close.head()}")
        print(f"DEBUG: spy_close tail:\n{spy_close.tail()}")
    else:
        print("DEBUG: spy_close is EMPTY!")

    # --- SPY-specific features ---
    features["spy_ret_1d"] = spy_close.pct_change(1)
    features["spy_ret_5d"] = spy_close.pct_change(5)

    features["spy_rsi14"] = compute_rsi(spy_close, window=14)

    ma20 = spy_close.rolling(window=20).mean()
    features["spy_dist_ma20"] = (spy_close - ma20) / ma20

    vol_mean20 = spy_vol.rolling(window=20).mean()
    vol_std20 = spy_vol.rolling(window=20).std()
    features["spy_vol_z20"] = (spy_vol - vol_mean20) / vol_std20

    # --- Cross-asset features ---
    features["qqq_ret_5d"] = qqq_close.pct_change(5)
    features["qqq_over_spy_ratio"] = qqq_close / spy_close

    features["gold_ret_5d"] = gld_close.pct_change(5)
    features["oil_ret_5d"] = uso_close.pct_change(5)

    features["tlt_ret_5d"] = tlt_close.pct_change(5)
    features["shy_ret_5d"] = shy_close.pct_change(5)
    features["tlt_shy_spread"] = features["tlt_ret_5d"] - features["shy_ret_5d"]

    features["vix_lvl"] = vix_close
    features["vix_chg_5d"] = vix_close.pct_change(5)

    features["dxy_ret_5d"] = dxy_close.pct_change(5)

    # Rolling correlations (20-day) on daily returns
    spy_daily_ret = spy_close.pct_change(1)
    gld_daily_ret = gld_close.pct_change(1)
    qqq_daily_ret = qqq_close.pct_change(1)

    features["spy_corr_gold_20"] = (
        spy_daily_ret.rolling(window=20).corr(gld_daily_ret)
    )
    features["spy_corr_qqq_20"] = (
        spy_daily_ret.rolling(window=20).corr(qqq_daily_ret)
    )

    # Curve proxy - log price ratio (TLT/SHY) ~ long vs short duration
    features["curve_proxy_tlt_shy"] = np.log(tlt_close / shy_close)

    # Inflation proxy - oil outperforming gold
    features["inflation_proxy_oil_minus_gold"] = (
        features["oil_ret_5d"] - features["gold_ret_5d"]
    )

    # Risk-off proxy - standardized VIX + standardized DXY
    vix_z = (vix_close - vix_close.rolling(60).mean()) / vix_close.rolling(60).std()
    dxy_ret_5d = features["dxy_ret_5d"]
    dxy_z = (dxy_ret_5d - dxy_ret_5d.rolling(60).mean()) / dxy_ret_5d.rolling(60).std()
    features["riskoff_proxy_vix_plus_dxy"] = vix_z + dxy_z

    # Drop rows with insufficient history for rolling stats
    features = features.dropna()

    return features, spy_close


def add_lagged_features(features, lags=LAGS):
    """
    Given a DataFrame of base features, append lagged versions of each column.
    """
    features_lagged = features.copy()
    for col in features.columns:
        for lag in lags:
            features_lagged[f"{col}_lag{lag}"] = features[col].shift(lag)
    # Drop rows with NaN, but keep track of how many we had before
    rows_before = len(features_lagged)
    
    # Debug: Check for NaNs
    print("DEBUG: Feature NaN counts before dropna:")
    print(features_lagged.isna().sum())
    
    features_clean = features_lagged.dropna()
    rows_after = len(features_clean)
    
    if rows_after == 0:
        print(f"DEBUG: All {rows_before} rows dropped!")
        print(f"DEBUG: Sample features_lagged:\n{features_lagged.tail()}")
        raise ValueError(f"All {rows_before} rows were dropped after dropna(). "
                       f"This suggests data alignment issues. "
                       f"NaN counts per column:\n{features_lagged.isna().sum()}")
    return features_clean


def run_inference(ticker=None, date=None):
    """
    Run inference pipeline using S3-stored data:
    1. Load data from S3 (or cache)
    2. Compute features
    3. Make prediction
    4. Return BUY/SELL signal
    
    Parameters:
    -----------
    ticker : str, optional
        Stock ticker (currently only SPY is supported, but kept for API compatibility)
    date : str, optional
        Date in YYYY-MM-DD format (if None, uses latest available date)
    
    Returns:
    --------
    dict : Prediction result with signal and metadata
    """
    if model is None:
        raise ValueError("Model not loaded. Please ensure model.pkl exists.")
    
    if feature_columns is None:
        raise ValueError("Model artifact missing feature_columns. Please retrain and save the model with feature_columns.")
    
    # Load market data from S3 (or fallback to yfinance)
    try:
        raw_prices = get_market_data(use_cache=True)
        
        # Filter to requested date if provided
        if date:
            cutoff_date = pd.to_datetime(date)
            # Handle timezone comparison issue
            if raw_prices.index.tz is not None and cutoff_date.tz is None:
                cutoff_date = cutoff_date.tz_localize('UTC')
            elif raw_prices.index.tz is None and cutoff_date.tz is not None:
                cutoff_date = cutoff_date.tz_localize(None)
                
            raw_prices = raw_prices[raw_prices.index <= cutoff_date]
        
        # Ensure we have enough history
        if len(raw_prices) < 70:
            raise ValueError(f"Insufficient data: only {len(raw_prices)} rows available. Need at least 70.")
        
    except Exception as e:
        raise ValueError(f"Failed to load market data: {str(e)}")
    
    # Recompute base + lagged features
    try:
        recent_base, recent_spy_close = compute_base_features(raw_prices)
        recent_lagged = add_lagged_features(recent_base, lags=lags)
        recent_lagged = recent_lagged.dropna()
    except Exception as e:
        raise ValueError(f"Failed to compute features: {str(e)}")
    
    # Align to training feature columns
    missing_cols = [c for c in feature_columns if c not in recent_lagged.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in inference features: {missing_cols}")
    
    X_all = recent_lagged[feature_columns].dropna()
    
    if len(X_all) == 0:
        raise ValueError("No valid feature rows after processing. Check data availability.")
    
    # Latest row = most recent trading day
    latest_features = X_all.iloc[-1:]
    latest_date = latest_features.index[0]
    
    # Make prediction (Linear Regression for targets)
    try:
        pred_ret = float(model.predict(latest_features)[0])
    except Exception as e:
        raise ValueError(f"Failed to make prediction: {str(e)}")
    
    # Make prediction (Logistic Regression for signal)
    prob_up = 0.5
    if logistic_model:
        try:
            prob_up = float(logistic_model.predict_proba(latest_features)[0, 1])
        except Exception as e:
            print(f"Warning: Logistic prediction failed: {e}")
            
    # Map predicted return to prices
    latest_spy_close = float(recent_spy_close.reindex(recent_lagged.index).iloc[-1])
    pred_open_930 = latest_spy_close
    pred_close_1600 = pred_open_930 * (1.0 + pred_ret)
    pred_intraday_change = pred_close_1600 - pred_open_930
    
    # BUY/SELL signal based on Logistic Probability (and optionally positive return)
    # We require BOTH high probability AND positive predicted return for a strong BUY
    if logistic_model:
        if (prob_up >= threshold) and (pred_ret > 0):
            signal = "BUY"
        else:
            signal = "SELL"
    else:
        # Fallback to linear model only
        signal = "BUY" if pred_ret > 0 else "SELL"
    
    # Convert prediction to binary (0 = DOWN/SELL, 1 = UP/BUY)
    prediction_binary = 1 if signal == "BUY" else 0
    
    return {
        "signal_date": latest_date.strftime("%Y-%m-%d") if hasattr(latest_date, 'strftime') else str(latest_date),
        "pred_open_930": round(pred_open_930, 2),
        "pred_close_1600": round(pred_close_1600, 2),
        "pred_intraday_change": round(pred_intraday_change, 4),
        "pred_intraday_return": round(pred_ret, 6),
        "prob_up": round(prob_up, 4),
        "threshold": round(threshold, 4),
        "signal": signal,
        "prediction": [prediction_binary],  # For backward compatibility with frontend
    }



def calculate_model_drift(days=30):
    """
    Backtest the model over the last N days to calculate drift metrics.
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
        # Load data
        df = get_market_data(use_cache=True)
        
        # Get SPY Close for actuals
        # Handle MultiIndex or flat columns
        spy_close = None
        if isinstance(df.columns, pd.MultiIndex):
            # Try to find SPY Close
            if ('SPY', 'Close') in df.columns:
                spy_close = df[('SPY', 'Close')]
            elif ('SPY', 'Adj Close') in df.columns:
                spy_close = df[('SPY', 'Adj Close')]
        else:
            if 'Close' in df.columns:
                spy_close = df['Close']
            elif 'Adj Close' in df.columns:
                spy_close = df['Adj Close']
                
        if spy_close is None:
            raise ValueError("Could not find SPY Close data for backtesting")
            
        # Get last N valid trading days (excluding last 5 days as we can't know actual return yet)
        # We need T+5 to exist to evaluate.
        if len(df) < 6:
            return metrics
            
        valid_dates = df.index[:-5] 
        test_dates = valid_dates[-days:] if len(valid_dates) >= days else valid_dates
        
        for date in test_dates:
            date_str = date.strftime('%Y-%m-%d')
            
            # Run inference for this date
            try:
                pred = run_inference(ticker='SPY', date=date_str)
                signal = pred['signal']
                
                # Calculate actual 5-day return
                loc = df.index.get_loc(date)
                entry_price = float(spy_close.iloc[loc])
                exit_price = float(spy_close.iloc[loc + 5])
                actual_ret = (exit_price - entry_price) / entry_price
                
                is_price_up = actual_ret > 0
                is_buy = signal == 'BUY'
                
                if is_buy and is_price_up:
                    metrics['tp'] += 1
                elif is_buy and not is_price_up:
                    metrics['fp'] += 1
                elif not is_buy and not is_price_up:
                    metrics['tn'] += 1
                elif not is_buy and is_price_up:
                    metrics['fn'] += 1
                
                metrics['total_predictions'] += 1
                metrics['dates'].append(date_str)
                metrics['actual_returns'].append(actual_ret)
                metrics['predicted_signals'].append(1 if is_buy else 0)
                
            except Exception as e:
                print(f"Error backtesting date {date_str}: {e}")
                continue
                
        # Derived metrics
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
        print(f"Error calculating drift: {e}")
        import traceback
        traceback.print_exc()
        
    return metrics


@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    """Health check endpoint to verify API is running"""
    return jsonify({
        'status': 'healthy',
        'service': 'ML Prediction API',
        'model_loaded': model is not None,
        'has_feature_columns': feature_columns is not None,
        'data_source': 'S3' if USE_S3 else 'yfinance',
        's3_bucket': S3_BUCKET if USE_S3 else None,
        'cache_status': 'loaded' if _market_data_cache is not None else 'empty',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/model/drift', methods=['GET'])
def get_drift_metrics():
    try:
        metrics = calculate_model_drift(days=30)
        return jsonify(metrics), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/predict', methods=['POST'])
def predict():
    """
    Prediction endpoint.
    
    Expected request body:
    {
        "ticker": "SPY" (optional, currently only SPY supported),
        "date": "2024-01-15" (optional, uses latest if not provided),
    }
    """
    try:
        data = request.get_json(force=True)
        
        ticker = data.get('ticker', 'SPY')
        date = data.get('date', None)
        
        # Run inference
        print("DEBUG: STARTING INFERENCE v18")
        result = run_inference(ticker, date)
        return jsonify(result), 200
            
    except ValueError as e:
        return jsonify({
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'error': f'Prediction failed: {str(e)}'
        }), 500


# Add CORS headers to every response
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

from apig_wsgi import make_lambda_handler
_handler = make_lambda_handler(app)

def handler(event, context):
    print("DEBUG: HANDLER INVOKED v22")
    return _handler(event, context)

if __name__ == '__main__':
    # Pre-load data on startup if using S3
    if USE_S3 and s3_client:
        try:
            print("Pre-loading market data from S3...")
            get_market_data(use_cache=False)
            print("✓ Market data pre-loaded")
        except Exception as e:
            print(f"⚠ Warning: Could not pre-load data: {e}")
            print("  Will load on first request")
    
    app.run(host='0.0.0.0', port=5000)

