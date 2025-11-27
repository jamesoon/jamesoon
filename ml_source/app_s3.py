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
S3_KEY = os.environ.get('S3_DATA_KEY', 'market-data/latest.parquet')
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
    "GOLD": "GLD",
    "OIL": "USO",
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",  # US Dollar Index on Yahoo
}

# Default lags (will be overridden by model artifact if present)
LAGS = [1, 2, 5]

# Global cache for market data
_market_data_cache = None
_cache_timestamp = None

# Load the model artifact
try:
    with open('ml_source/model.pkl', 'rb') as f:
        artifact = pickle.load(f)
    
    # Handle both old format (just model) and new format (artifact dict)
    if isinstance(artifact, dict):
        model = artifact.get('model')
        feature_columns = artifact.get('feature_columns')
        lags = artifact.get('lags', LAGS)
        train_start_date = artifact.get('train_start_date', '2015-01-01')
    else:
        # Legacy format: just the model
        model = artifact
        feature_columns = None
        lags = LAGS
        train_start_date = '2015-01-01'
except FileNotFoundError:
    model = None
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
    spy = raw[TICKERS["SPY"]] if ("SPY", "Close") in raw.columns else raw["SPY"]
    qqq = raw[TICKERS["QQQ"]] if ("QQQ", "Close") in raw.columns else raw["QQQ"]
    gld = raw[TICKERS["GOLD"]] if ("GLD", "Close") in raw.columns else raw["GOLD"]
    uso = raw[TICKERS["OIL"]] if ("USO", "Close") in raw.columns else raw["OIL"]
    tlt = raw[TICKERS["TLT"]] if ("TLT", "Close") in raw.columns else raw["TLT"]
    shy = raw[TICKERS["SHY"]] if ("SHY", "Close") in raw.columns else raw["SHY"]
    vix = raw[TICKERS["VIX"]] if ("^VIX", "Close") in raw.columns else raw["^VIX"]
    dxy = raw[TICKERS["DXY"]] if ("DX-Y.NYB", "Close") in raw.columns else raw["DX-Y.NYB"]

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
    # Drop rows with NaNs introduced by lags
    features_lagged = features_lagged.dropna()
    return features_lagged


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
            raw_prices = raw_prices[raw_prices.index <= pd.to_datetime(date)]
        
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
    
    # Make prediction
    try:
        pred_ret = float(model.predict(latest_features)[0])
    except Exception as e:
        raise ValueError(f"Failed to make prediction: {str(e)}")
    
    # Map predicted return to prices
    latest_spy_close = float(recent_spy_close.reindex(recent_lagged.index).iloc[-1])
    pred_open_930 = latest_spy_close
    pred_close_1600 = pred_open_930 * (1.0 + pred_ret)
    pred_intraday_change = pred_close_1600 - pred_open_930
    
    # BUY/SELL signal based on predicted return
    signal = "BUY" if pred_ret > 0 else "SELL"
    
    # Convert prediction to binary (0 = DOWN/SELL, 1 = UP/BUY)
    prediction_binary = 1 if pred_ret > 0 else 0
    
    return {
        "signal_date": latest_date.strftime("%Y-%m-%d") if hasattr(latest_date, 'strftime') else str(latest_date),
        "pred_open_930": round(pred_open_930, 2),
        "pred_close_1600": round(pred_close_1600, 2),
        "pred_intraday_change": round(pred_intraday_change, 4),
        "pred_intraday_return": round(pred_ret, 6),
        "signal": signal,
        "prediction": [prediction_binary],  # For backward compatibility with frontend
    }


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
        
        result = run_inference(ticker=ticker, date=date)
        return jsonify(result), 200
            
    except ValueError as e:
        return jsonify({
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'error': f'Prediction failed: {str(e)}'
        }), 500


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

