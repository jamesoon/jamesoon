import os
import pickle
import json
import io
import numpy as np
import pandas as pd
import boto3
from io import BytesIO
from datetime import datetime
from sagemaker_containers.beta.framework import content_types, encoders

# Configuration
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'mdaie-prml-spy-bucket')
S3_KEY = os.environ.get('S3_DATA_KEY', 'market-data/latest.parquet')

# Ticker configuration
TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GLD",
    "OIL": "USO",
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
}

def compute_rsi(series, window=14):
    """
    Compute RSI (Relative Strength Index) for a price series.
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
    # Handle both MultiIndex and flat columns
    def get_ticker_data(ticker_key, ticker_val):
        if isinstance(raw.columns, pd.MultiIndex):
            # Try to find the ticker in the top level
            if ticker_val in raw.columns.get_level_values(0):
                return raw[ticker_val]
            # Try normalized names if different
            if ticker_key in raw.columns.get_level_values(0):
                return raw[ticker_key]
            # Try to find by partial match or assume it's there
            return raw[ticker_val] # Fallback
        else:
            # Flat columns
            # Check for "Ticker" or "Ticker_Close" etc
            if ticker_val in raw.columns:
                return raw[ticker_val] # This might be a Series if flat
            return raw # Fallback, might fail later if structure is unexpected

    # Helper to get Close and Volume
    def get_close(df):
        if isinstance(df, pd.Series): return df
        if isinstance(df.columns, pd.MultiIndex):
             for col in df.columns:
                if col[1] in ["Adj Close", "Close"]: return df[col]
        if "Adj Close" in df.columns: return df["Adj Close"]
        if "Close" in df.columns: return df["Close"]
        return df # Fallback

    def get_volume(df):
        if isinstance(df, pd.Series): return df
        if isinstance(df.columns, pd.MultiIndex):
             for col in df.columns:
                if col[1] == "Volume": return df[col]
        if "Volume" in df.columns: return df["Volume"]
        return df

    # Extract data
    # Note: This logic simplifies `app_s3.py` slightly but aims to be robust
    # We assume the input `raw` is a DataFrame with MultiIndex (Ticker, Field) or similar
    
    # If raw is from S3 (parquet), it usually preserves the structure (MultiIndex)
    
    spy = raw["SPY"]
    qqq = raw["QQQ"]
    gld = raw["GLD"] if "GLD" in raw.columns else raw["GOLD"]
    uso = raw["USO"] if "USO" in raw.columns else raw["OIL"]
    tlt = raw["TLT"]
    shy = raw["SHY"]
    vix = raw["^VIX"] if "^VIX" in raw.columns else raw["VIX"]
    dxy = raw["DX-Y.NYB"] if "DX-Y.NYB" in raw.columns else raw["DXY"]

    spy_close = get_close(spy).copy()
    spy_vol = get_volume(spy).copy()
    qqq_close = get_close(qqq).copy()
    gld_close = get_close(gld).copy()
    uso_close = get_close(uso).copy()
    tlt_close = get_close(tlt).copy()
    shy_close = get_close(shy).copy()
    vix_close = get_close(vix).copy()
    dxy_close = get_close(dxy).copy()

    # Initialize features DataFrame
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

    # Rolling correlations
    spy_daily_ret = spy_close.pct_change(1)
    gld_daily_ret = gld_close.pct_change(1)
    qqq_daily_ret = qqq_close.pct_change(1)

    features["spy_corr_gold_20"] = spy_daily_ret.rolling(window=20).corr(gld_daily_ret)
    features["spy_corr_qqq_20"] = spy_daily_ret.rolling(window=20).corr(qqq_daily_ret)

    # Proxies
    features["curve_proxy_tlt_shy"] = np.log(tlt_close / shy_close)
    features["inflation_proxy_oil_minus_gold"] = features["oil_ret_5d"] - features["gold_ret_5d"]

    vix_z = (vix_close - vix_close.rolling(60).mean()) / vix_close.rolling(60).std()
    dxy_ret_5d = features["dxy_ret_5d"]
    dxy_z = (dxy_ret_5d - dxy_ret_5d.rolling(60).mean()) / dxy_ret_5d.rolling(60).std()
    features["riskoff_proxy_vix_plus_dxy"] = vix_z + dxy_z

    features = features.dropna()
    return features, spy_close

def add_lagged_features(features, lags=[1, 2, 5]):
    features_lagged = features.copy()
    for col in features.columns:
        for lag in lags:
            features_lagged[f"{col}_lag{lag}"] = features[col].shift(lag)
    return features_lagged.dropna()

def model_fn(model_dir):
    """
    Load the model from the model_dir.
    """
    print(f"Loading model from {model_dir}")
    model_path = os.path.join(model_dir, "model.pkl")
    with open(model_path, "rb") as f:
        artifact = pickle.load(f)
    
    # Handle artifact dict vs legacy model
    if isinstance(artifact, dict):
        print("Loaded model artifact (dict)")
        return artifact
    else:
        print("Loaded legacy model")
        return {"model": artifact, "feature_columns": None, "lags": [1, 2, 5]}

def input_fn(request_body, request_content_type):
    """
    Deserialize the request body.
    """
    print(f"Received request with content type: {request_content_type}")
    
    if request_content_type == content_types.JSON:
        input_data = json.loads(request_body)
        return input_data
    else:
        # Handle other types if needed, but for now assume JSON
        raise ValueError(f"Unsupported content type: {request_content_type}")

def predict_fn(input_data, model_artifact):
    """
    Make a prediction using the model and S3 data.
    """
    print("Executing prediction")
    
    # 1. Load data from S3
    print(f"Loading market data from s3://{S3_BUCKET}/{S3_KEY}")
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
    raw_prices = pd.read_parquet(BytesIO(obj['Body'].read()))
    
    # 2. Compute features
    model = model_artifact['model']
    feature_columns = model_artifact.get('feature_columns')
    lags = model_artifact.get('lags', [1, 2, 5])
    
    base_features, spy_close = compute_base_features(raw_prices)
    features_lagged = add_lagged_features(base_features, lags=lags)
    
    # 3. Align features
    if feature_columns:
        # Ensure all columns exist
        missing = [c for c in feature_columns if c not in features_lagged.columns]
        if missing:
            raise ValueError(f"Missing feature columns: {missing}")
        X = features_lagged[feature_columns]
    else:
        X = features_lagged
    
    # 4. Select row to predict
    # If date is provided in input_data, use that. Otherwise use latest.
    target_date = None
    if isinstance(input_data, dict) and 'date' in input_data:
        target_date = input_data['date']
    
    if target_date:
        if target_date not in X.index:
             # Try to find closest previous date? Or just fail.
             # For now, let's try exact match or fail
             if target_date not in X.index:
                 raise ValueError(f"Date {target_date} not found in data")
        row = X.loc[[target_date]]
        current_price = spy_close.loc[target_date]
    else:
        # Use latest
        row = X.iloc[-1:]
        current_price = spy_close.iloc[-1]
        target_date = row.index[0]

    print(f"Predicting for date: {target_date}")
    
    # 5. Predict
    pred_ret = float(model.predict(row)[0])
    prob_up = 0.5 # Default if not classifier
    if hasattr(model, "predict_proba"):
        try:
            prob_up = float(model.predict_proba(row)[:, 1][0])
        except:
            pass
            
    signal = "BUY" if pred_ret > 0 else "SELL"
    
    # Log the inference
    print(f"INFERENCE_LOG: Date={target_date}, Prediction={pred_ret}, Signal={signal}, Price={current_price}")
    
    result = {
        "signal_date": str(target_date),
        "pred_return": pred_ret,
        "signal": signal,
        "current_price": float(current_price),
        "prob_up": prob_up,
        "prediction": [1 if pred_ret > 0 else 0]
    }
    
    return result

def output_fn(prediction, response_content_type):
    """
    Serialize the prediction result.
    """
    print(f"Serializing output to {response_content_type}")
    return json.dumps(prediction), response_content_type
