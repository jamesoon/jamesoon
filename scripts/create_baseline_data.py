import pandas as pd
import numpy as np
import os
import pickle

def compute_rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def create_baseline():
    # Load the normalized data (raw prices)
    data_path = "ml_source/market_data_normalized.parquet"
    model_path = "ml_source/model.pkl"
    
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return

    if not os.path.exists(model_path):
        print(f"Error: {model_path} not found.")
        return

    # Read raw prices (MultiIndex columns: Ticker, Field)
    prices = pd.read_parquet(data_path)
    
    # --- Feature Engineering (Copied from notebook) ---
    # We need to reconstruct the features_df
    
    # Helper to access columns easily
    # The parquet columns are MultiIndex: (Ticker, Field)
    # e.g. ('SPY', 'Close')
    
    def get_col(ticker, field="Close"):
        if (ticker, field) in prices.columns:
            return prices[(ticker, field)]
        # Fallback if levels are swapped or different structure
        elif (field, ticker) in prices.columns:
            return prices[(field, ticker)]
        else:
            # Try to find it
            raise ValueError(f"Column {ticker} {field} not found")

    spy_close = get_col("SPY", "Close")
    spy_vol = get_col("SPY", "Volume")
    
    features = pd.DataFrame(index=prices.index)
    
    # Base Features
    features['spy_ret_1d'] = spy_close.pct_change(1)
    features['spy_ret_5d'] = spy_close.pct_change(5)
    features['spy_rsi14'] = compute_rsi(spy_close, 14)
    
    ma20 = spy_close.rolling(20).mean()
    features['spy_dist_ma20'] = (spy_close - ma20) / ma20
    
    vol_mean20 = spy_vol.rolling(20).mean()
    vol_std20 = spy_vol.rolling(20).std()
    features['spy_vol_z20'] = (spy_vol - vol_mean20) / vol_std20
    
    # Cross-asset
    qqq_close = get_col("QQQ", "Close")
    gold_close = get_col("GOLD", "Close")
    oil_close = get_col("OIL", "Close")
    tlt_close = get_col("TLT", "Close")
    shy_close = get_col("SHY", "Close")
    vix_close = get_col("VIX", "Close")
    dxy_close = get_col("DXY", "Close")
    
    features['qqq_ret_5d'] = qqq_close.pct_change(5)
    features['qqq_over_spy_ratio'] = qqq_close / spy_close
    features['gold_ret_5d'] = gold_close.pct_change(5)
    features['oil_ret_5d'] = oil_close.pct_change(5)
    features['tlt_ret_5d'] = tlt_close.pct_change(5)
    features['shy_ret_5d'] = shy_close.pct_change(5)
    features['tlt_shy_spread'] = features['tlt_ret_5d'] - features['shy_ret_5d']
    
    features['vix_lvl'] = vix_close
    features['vix_chg_5d'] = vix_close.pct_change(5)
    features['dxy_ret_5d'] = dxy_close.pct_change(5)
    
    features['spy_corr_gold_20'] = spy_close.rolling(20).corr(gold_close)
    features['spy_corr_qqq_20'] = spy_close.rolling(20).corr(qqq_close)
    
    features['curve_proxy_tlt_shy'] = np.log(tlt_close / shy_close)
    features['inflation_proxy_oil_minus_gold'] = features['oil_ret_5d'] - features['gold_ret_5d']
    
    # Risk-off proxy
    vix_z = (vix_close - vix_close.rolling(60).mean()) / vix_close.rolling(60).std()
    dxy_z = (dxy_close - dxy_close.rolling(60).mean()) / dxy_close.rolling(60).std()
    features['riskoff_proxy_vix_plus_dxy'] = vix_z + dxy_z

    # Add Lags
    # The model expects lags: [1, 2, 5] for ALL base features
    # We need to know exactly which columns are "base features" to lag.
    # Based on the error message, it seems ALL the above are lagged.
    
    base_cols = features.columns.tolist()
    lags = [1, 2, 5]
    
    for col in base_cols:
        for lag in lags:
            features[f"{col}_lag{lag}"] = features[col].shift(lag)
            
    # Drop NaN
    features = features.dropna()
    
    # Load model to check expected columns
    with open(model_path, "rb") as f:
        model_data = pickle.load(f)
    
    feature_columns = model_data.get('feature_columns')
    if not feature_columns:
        print("Error: feature_columns not found in model artifact.")
        return

    # Ensure we have all columns
    missing_cols = [c for c in feature_columns if c not in features.columns]
    if missing_cols:
        print(f"Error: Still missing columns: {missing_cols}")
        return

    # Select and order columns
    features_df = features[feature_columns]
    
    # Save as CSV without header for SageMaker Model Monitor baseline
    output_dir = "ml_source/baseline_data"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "baseline.csv")
    features_df.to_csv(output_path, index=False, header=False)
    
    # Save with header for reference
    features_df.to_csv(os.path.join(output_dir, "baseline_with_header.csv"), index=False)
    
    print(f"Baseline data created at {output_path}")
    print(f"Rows: {len(features_df)}, Columns: {len(features_df.columns)}")

if __name__ == "__main__":
    create_baseline()
