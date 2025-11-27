

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import os
import pickle
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, precision_score

# --- Configuration ---
TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GOLD": "GLD",
    "OIL": "USO",
    "TLT": "TLT",
    "SHY": "SHY",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB"
}
LAGS = [1, 2, 5]

# --- 1. Data Ingestion ---
def download_price_data(tickers_dict, start_date="2015-01-01", end_date=None):
    """Downloads daily OHLCV data for the given tickers."""
    print(f"Downloading data for {list(tickers_dict.values())}...")
    yf_tickers = " ".join(tickers_dict.values())
    data = yf.download(
        yf_tickers,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        group_by="ticker",
        progress=False
    )
    
    # Handle MultiIndex columns if multiple tickers
    if isinstance(data.columns, pd.MultiIndex):
        prices = data
    else:
        symbol = list(tickers_dict.keys())[0]
        prices = pd.concat({symbol: data}, axis=1)
        
    return prices.sort_index(axis=1)

# --- 2. Feature Engineering ---
def compute_rsi(series, window=14):
    """Computes Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_base_features(raw):
    """Computes standard returns and volume features."""
    # Helper to handle column access
    def get_col(ticker, col="Close"):
        if (TICKERS[ticker], col) in raw.columns:
            return raw[TICKERS[ticker]][col]
        return raw[TICKERS[ticker]]

    spy_close = get_col("SPY")
    
    # Handle Volume column which might be top-level or under ticker
    if (TICKERS["SPY"], "Volume") in raw.columns:
        spy_vol = raw[TICKERS["SPY"]]["Volume"]
    else:
        spy_vol = raw["Volume"]

    features = pd.DataFrame(index=spy_close.index)
    
    # Returns & Momentum
    features["spy_ret_1d"] = spy_close.pct_change(1)
    features["spy_ret_5d"] = spy_close.pct_change(5)
    features["spy_rsi14"] = compute_rsi(spy_close)
    
    # Volume Z-Score
    vol_mean20 = spy_vol.rolling(20).mean()
    vol_std20 = spy_vol.rolling(20).std()
    features["spy_vol_z20"] = (spy_vol - vol_mean20) / vol_std20

    # Cross-Asset correlations/returns
    qqq_close = get_col("QQQ")
    gld_close = get_col("GOLD")
    vix_close = get_col("VIX")
    dxy_close = get_col("DXY")
    
    features["qqq_ret_5d"] = qqq_close.pct_change(5)
    features["gold_ret_5d"] = gld_close.pct_change(5)
    features["vix_lvl"] = vix_close
    features["dxy_ret_5d"] = dxy_close.pct_change(5)
    
    return features.dropna(), spy_close

def add_technical_indicators(features, price_series):
    """Adds MACD, Bollinger Bands, and Volatility."""
    df = features.copy()
    price = price_series.reindex(df.index)
    
    # MACD
    ema12 = price.ewm(span=12, adjust=False).mean()
    ema26 = price.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df['macd_hist'] = macd - signal
    
    # Bollinger Bands
    ma20 = price.rolling(20).mean()
    std20 = price.rolling(20).std()
    upper = ma20 + (2 * std20)
    lower = ma20 - (2 * std20)
    df['bb_position'] = (price - lower) / (upper - lower)
    
    # Rolling Volatility
    df['volatility_20d'] = std20 / price
    
    return df.dropna()

def add_lagged_features(features, lags=[1, 2, 5]):
    """Adds time-lagged versions of features."""
    df = features.copy()
    for col in features.columns:
        for lag in lags:
            df[f"{col}_lag{lag}"] = features[col].shift(lag)
    return df.dropna()

# --- 3. Dataset Construction ---
def build_classification_dataset(features, spy_close, forward_horizon=1):
    """Creates target variable (1 if return > 0 else 0)."""
    spy_aligned = spy_close.reindex(features.index)
    fwd_ret = spy_aligned.pct_change(forward_horizon).shift(-forward_horizon)
    
    full_df = features.copy()
    full_df["target_return"] = fwd_ret
    full_df["target_class"] = (fwd_ret > 0).astype(int)
    
    full_df = full_df.dropna(subset=["target_return"])
    
    X = full_df.drop(columns=["target_return", "target_class"])
    y = full_df["target_class"]
    
    return X, y

# --- 4. Inference Pipeline ---
def run_inference_rf(model, feature_columns, tickers, start_date="2020-01-01"):
    """Runs the full pipeline to get the latest signal."""
    print("\n--- Running Inference ---")
    # 1. Download & Process
    raw = download_price_data(tickers, start_date=start_date)
    base, close = compute_base_features(raw)
    augmented = add_technical_indicators(base, close)
    lagged = add_lagged_features(augmented, lags=LAGS)
    
    # 2. Align Columns (Ensure feature order matches training)
    final_X = lagged[feature_columns].dropna()
    latest_row = final_X.iloc[-1:]
    latest_date = latest_row.index[0]
    
    # 3. Predict
    prob_buy = model.predict_proba(latest_row)[0][1]
    
    # 4. Signal Logic
    threshold = 0.55
    if prob_buy >= threshold:
        signal = "BUY"
    elif prob_buy <= (1 - threshold):
        signal = "SELL"
    else:
        signal = "HOLD/CASH"
        
    return latest_date, prob_buy, signal

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting SPY Trading Model...")
    
    # 1. Prepare Data
    raw_prices = download_price_data(TICKERS)
    base_features, spy_close = compute_base_features(raw_prices)
    augmented_features = add_technical_indicators(base_features, spy_close)
    final_features = add_lagged_features(augmented_features, lags=LAGS)
    
    X, y = build_classification_dataset(final_features, spy_close)
    
    # 2. Train/Test Split (Chronological)
    test_size = 0.2
    split_idx = int(len(X) * (1 - test_size))
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Training on {len(X_train)} days, Testing on {len(X_test)} days.")
    
    # 3. Train Model
    print("Training Random Forest Classifier...")
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=5,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_train, y_train)
    
    # 4. Evaluate
    y_pred = clf.predict(X_test)
    print("\n--- Model Evaluation Report ---")
    print(classification_report(y_test, y_pred))
    
    # Threshold Evaluation
    probs = clf.predict_proba(X_test)[:, 1]
    threshold = 0.55
    y_pred_filtered = (probs >= threshold).astype(int)
    win_rate = precision_score(y_test, y_pred_filtered, zero_division=0)
    
    print(f"--- High Conviction Stats (Threshold > {threshold}) ---")
    print(f"Trades Taken: {sum(y_pred_filtered)}")
    print(f"Win Rate:     {win_rate:.2%}")
    
    # 5. Run Inference
    feature_cols = X_train.columns.tolist()
    date, prob, signal = run_inference_rf(clf, feature_cols, TICKERS)
    
    print(f"\n=== Signal for {date.date()} ===")
    print(f"Probability of Up Day: {prob:.2%}")
    print(f"Signal: {signal}")
    
    # 6. Save Model
    artifact = {
        "model": clf,
        "feature_columns": feature_cols,
        "created_at": datetime.utcnow().isoformat()
    }
    with open("spy_rf_model.pkl", "wb") as f:
        pickle.dump(artifact, f)
    print("\nModel saved as spy_rf_model.pkl")