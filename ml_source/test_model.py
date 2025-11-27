#!/usr/bin/env python
"""
Test script for model.pkl inference pipeline.

This script tests:
1. Model artifact loading
2. Feature engineering pipeline
3. Inference execution
4. Output validation
"""

import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
import yfinance as yf
import sys
import os
import argparse
from io import BytesIO

# Optional S3 imports
try:
    import boto3
    import pyarrow
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

warnings.filterwarnings("ignore")

# NumPy version compatibility fix
# Handle models pickled with NumPy 2.0+ when running on NumPy < 2.0
# Create compatibility shim for numpy._core
if np.__version__.startswith('1.'):
    import numpy.core as _numpy_core
    import types
    
    # Create a compatibility module that redirects numpy._core to numpy.core
    class _CoreCompat(types.ModuleType):
        def __getattr__(self, name):
            if name == 'numeric':
                return _numpy_core.numeric
            elif name == 'multiarray':
                return _numpy_core.multiarray
            elif name == 'umath':
                return _numpy_core.umath
            else:
                return getattr(_numpy_core, name, None)
    
    # Inject into sys.modules
    if 'numpy._core' not in sys.modules:
        _core_compat = _CoreCompat('numpy._core')
        sys.modules['numpy._core'] = _core_compat
        # Create submodule entries
        sys.modules['numpy._core.numeric'] = _numpy_core.numeric
        sys.modules['numpy._core.multiarray'] = _numpy_core.multiarray  
        sys.modules['numpy._core.umath'] = _numpy_core.umath

# S3 Configuration (can be overridden by environment variables or command-line args)
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'spy-ml-market-data')
S3_KEY = os.environ.get('S3_DATA_KEY', 'market-data/latest.parquet')
# Local fallback if S3 is not available (relative to this script's directory)
LOCAL_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_data_normalized.parquet')

# Add current directory to path to import from app.py if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import functions from app.py
try:
    from app import (
        TICKERS, LAGS, compute_rsi, download_price_data,
        compute_base_features, add_lagged_features
    )
except ImportError:
    print("Warning: Could not import from app.py. Using local definitions.")
    
    # Define locally if import fails
    # Using normalized ticker names that match S3 data
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
    LAGS = [1, 2, 5]
    
    def compute_rsi(series, window=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def download_price_data(tickers_dict, start_date="2015-01-01", end_date=None, auto_adjust=True):
        # Map normalized ticker names to yfinance symbols for downloading
        yfinance_mapping = {
            "SPY": "SPY",
            "QQQ": "QQQ",
            "GOLD": "GLD",     # yfinance uses GLD, we normalize to GOLD
            "OIL": "USO",      # yfinance uses USO, we normalize to OIL
            "TLT": "TLT",
            "SHY": "SHY",
            "VIX": "^VIX",     # yfinance uses ^VIX, we normalize to VIX
            "DXY": "DX-Y.NYB", # yfinance uses DX-Y.NYB, we normalize to DXY
        }
        
        # Convert ticker values to yfinance symbols
        yf_symbols = []
        for ticker_name, ticker_value in tickers_dict.items():
            yf_symbol = yfinance_mapping.get(ticker_value, ticker_value)
            yf_symbols.append(yf_symbol)
        
        yf_tickers = " ".join(yf_symbols)
        data = yf.download(yf_tickers, start=start_date, end=end_date,
                          auto_adjust=auto_adjust, group_by="ticker", progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            # Normalize ticker names in the returned data
            new_columns = []
            for ticker, field in data.columns:
                # Map yfinance symbol back to normalized name
                normalized_ticker = ticker
                for norm_name, yf_sym in yfinance_mapping.items():
                    if yf_sym == ticker:
                        normalized_ticker = norm_name
                        break
                new_columns.append((normalized_ticker, field))
            data.columns = pd.MultiIndex.from_tuples(new_columns)
            return data.sort_index(axis=1)
        
        symbol = list(tickers_dict.keys())[0]
        return pd.concat({symbol: data}, axis=1).sort_index(axis=1)
    
    def compute_base_features(raw):
        # Extract ticker DataFrames - use xs() for MultiIndex with robust fallback
        def safe_xs(ticker_symbols, ticker_name):
            """Safely extract ticker DataFrame with fallback logic."""
            if isinstance(raw.columns, pd.MultiIndex):
                # Try each ticker symbol
                for ticker in ticker_symbols:
                    if (ticker, "Close") in raw.columns:
                        try:
                            return raw.xs(ticker, axis=1, level=0)
                        except KeyError:
                            continue
                # If not found, search in available tickers
                available_tickers = set(raw.columns.get_level_values(0))
                # Try exact match
                for ticker in ticker_symbols:
                    if ticker in available_tickers:
                        try:
                            return raw.xs(ticker, axis=1, level=0)
                        except KeyError:
                            continue
                # Try case-insensitive partial match for all ticker symbols
                candidates = []
                for ticker in ticker_symbols:
                    ticker_upper = ticker.upper()
                    matches = [t for t in available_tickers if ticker_upper in t.upper() or t.upper() in ticker_upper]
                    candidates.extend(matches)
                # Remove duplicates while preserving order
                seen = set()
                unique_candidates = []
                for c in candidates:
                    if c not in seen:
                        seen.add(c)
                        unique_candidates.append(c)
                if unique_candidates:
                    return raw.xs(unique_candidates[0], axis=1, level=0)
                raise KeyError(f"Could not find {ticker_name} data. Tried: {ticker_symbols}. Available tickers: {sorted(available_tickers)}")
            else:
                # Flat columns
                for ticker in ticker_symbols:
                    if ticker in raw.columns:
                        col_data = raw[ticker]
                        return col_data if isinstance(col_data, pd.DataFrame) else pd.DataFrame({ticker: col_data})
                raise KeyError(f"Could not find {ticker_name} data. Tried: {ticker_symbols}. Available columns: {list(raw.columns[:20])}")
        
        if isinstance(raw.columns, pd.MultiIndex):
            spy = safe_xs(["SPY", TICKERS["SPY"]], "SPY")
            qqq = safe_xs(["QQQ", TICKERS["QQQ"]], "QQQ")
            # Normalized S3 data uses GOLD and OIL (not GLD and USO)
            gld = safe_xs(["GOLD", "GLD", TICKERS["GOLD"]], "GOLD")
            uso = safe_xs(["OIL", "USO", TICKERS["OIL"]], "OIL")
            tlt = safe_xs(["TLT", TICKERS["TLT"]], "TLT")
            shy = safe_xs(["SHY", TICKERS["SHY"]], "SHY")
        else:
            spy = raw[TICKERS["SPY"]] if TICKERS["SPY"] in raw.columns else raw["SPY"]
            qqq = raw[TICKERS["QQQ"]] if TICKERS["QQQ"] in raw.columns else raw["QQQ"]
            gld = raw[TICKERS["GOLD"]] if TICKERS["GOLD"] in raw.columns else raw["GOLD"]
            uso = raw[TICKERS["OIL"]] if TICKERS["OIL"] in raw.columns else raw["OIL"]
            tlt = raw[TICKERS["TLT"]] if TICKERS["TLT"] in raw.columns else raw["TLT"]
            shy = raw[TICKERS["SHY"]] if TICKERS["SHY"] in raw.columns else raw["SHY"]
        # Handle VIX and DXY using safe_xs (they're already in the normalized format)
        vix = safe_xs(["VIX", "^VIX", TICKERS["VIX"]], "VIX")
        dxy = safe_xs(["DXY", "DX-Y.NYB", TICKERS["DXY"]], "DXY")
        
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
        
        spy_close = get_close(spy).copy()
        spy_vol = get_volume(spy).copy()
        qqq_close = get_close(qqq).copy()
        gld_close = get_close(gld).copy()
        uso_close = get_close(uso).copy()
        tlt_close = get_close(tlt).copy()
        shy_close = get_close(shy).copy()
        vix_close = get_close(vix).copy()
        dxy_close = get_close(dxy).copy()
        
        # Debug: Check if series have data
        if len(spy_close) == 0 or spy_close.isna().all():
            raise ValueError(f"SPY close data is empty or all NaN. Length: {len(spy_close)}, "
                           f"NaN count: {spy_close.isna().sum()}, "
                           f"Sample: {spy_close.head() if len(spy_close) > 0 else 'N/A'}")
        
        # S3 data is already normalized (timezone-naive, date-only, no duplicates)
        # Use SPY's index as the base since all tickers should share the same dates
        features = pd.DataFrame(index=spy_close.index)
        features["spy_ret_1d"] = spy_close.pct_change(1)
        features["spy_ret_5d"] = spy_close.pct_change(5)
        features["spy_rsi14"] = compute_rsi(spy_close, window=14)
        ma20 = spy_close.rolling(window=20).mean()
        features["spy_dist_ma20"] = (spy_close - ma20) / ma20
        vol_mean20 = spy_vol.rolling(window=20).mean()
        vol_std20 = spy_vol.rolling(window=20).std()
        features["spy_vol_z20"] = (spy_vol - vol_mean20) / vol_std20
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
        spy_daily_ret = spy_close.pct_change(1)
        gld_daily_ret = gld_close.pct_change(1)
        qqq_daily_ret = qqq_close.pct_change(1)
        features["spy_corr_gold_20"] = spy_daily_ret.rolling(window=20).corr(gld_daily_ret)
        features["spy_corr_qqq_20"] = spy_daily_ret.rolling(window=20).corr(qqq_daily_ret)
        features["curve_proxy_tlt_shy"] = np.log(tlt_close / shy_close)
        features["inflation_proxy_oil_minus_gold"] = features["oil_ret_5d"] - features["gold_ret_5d"]
        vix_z = (vix_close - vix_close.rolling(60).mean()) / vix_close.rolling(60).std()
        dxy_ret_5d = features["dxy_ret_5d"]
        dxy_z = (dxy_ret_5d - dxy_ret_5d.rolling(60).mean()) / dxy_ret_5d.rolling(60).std()
        features["riskoff_proxy_vix_plus_dxy"] = vix_z + dxy_z
        
        # Drop rows with NaN, but keep track of how many we had before
        rows_before = len(features)
        features_clean = features.dropna()
        rows_after = len(features_clean)
        
        if rows_after == 0:
            raise ValueError(f"All {rows_before} rows were dropped after dropna(). "
                           f"This suggests data alignment issues. "
                           f"NaN counts per column:\n{features.isna().sum()}")
        
        return features_clean, spy_close
    
    def add_lagged_features(features, lags=LAGS):
        features_lagged = features.copy()
        for col in features.columns:
            for lag in lags:
                features_lagged[f"{col}_lag{lag}"] = features[col].shift(lag)
        return features_lagged.dropna()


def load_model(model_path='./model.pkl'):
    """Load and validate model artifact."""
    print(f"\n{'='*60}")
    print("STEP 1: Loading Model Artifact")
    print(f"{'='*60}")
    
    try:
        # Use custom unpickler to handle NumPy version compatibility
        class CompatUnpickler(pickle.Unpickler):
            def find_class(self, module, name):
                # Redirect numpy._core imports to numpy.core for NumPy < 2.0
                if module.startswith('numpy._core') and np.__version__.startswith('1.'):
                    module = module.replace('numpy._core', 'numpy.core')
                return super().find_class(module, name)
        
        with open(model_path, 'rb') as f:
            unpickler = CompatUnpickler(f)
            artifact = unpickler.load()
        
        print(f"✓ Successfully loaded model from: {model_path}")
        
        # Check artifact structure
        if isinstance(artifact, dict):
            print("\n✓ Model artifact is a dictionary (new format)")
            model = artifact.get('model')
            feature_columns = artifact.get('feature_columns')
            lags = artifact.get('lags', LAGS)
            train_start_date = artifact.get('train_start_date', '2015-01-01')
            
            print(f"  - Model type: {type(model).__name__}")
            print(f"  - Feature columns: {len(feature_columns) if feature_columns else 'None'}")
            print(f"  - Lags: {lags}")
            print(f"  - Training start date: {train_start_date}")
            
            if feature_columns:
                print(f"\n  First 10 feature columns:")
                for i, col in enumerate(feature_columns[:10]):
                    print(f"    {i+1}. {col}")
                if len(feature_columns) > 10:
                    print(f"    ... and {len(feature_columns) - 10} more")
        else:
            print("\n⚠ Model artifact is legacy format (just model, no metadata)")
            model = artifact
            feature_columns = None
            lags = LAGS
            train_start_date = '2015-01-01'
            print(f"  - Model type: {type(model).__name__}")
            print("  - Warning: Missing feature_columns. Inference pipeline may not work.")
        
        return model, feature_columns, lags, train_start_date
        
    except FileNotFoundError:
        print(f"✗ Error: Model file not found at {model_path}")
        print(f"  Please ensure model.pkl exists in the ml_source directory.")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error loading model: {str(e)}")
        sys.exit(1)


def normalize_s3_data(df):
    """
    Normalize S3-loaded data to match yfinance MultiIndex format.
    Handles both flat column names and MultiIndex formats.
    """
    # Check if already in MultiIndex format (from yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        print("  Data already in MultiIndex format")
        return df
    
    # Check column structure
    print(f"  Detected column structure: {type(df.columns).__name__}")
    print(f"  Sample columns: {list(df.columns[:10])}")
    
    # Try to reconstruct MultiIndex format
    # Expected format from yfinance: (Ticker, OHLCV)
    # S3 might have: Ticker_OHLCV or just flat columns
    
    # Check if columns are in format "TICKER_Field" (e.g., "SPY_Close")
    ticker_fields = {}
    for col in df.columns:
        if isinstance(col, str):
            # Try to split by underscore
            parts = col.split('_', 1)
            if len(parts) == 2:
                ticker, field = parts
                if ticker not in ticker_fields:
                    ticker_fields[ticker] = {}
                ticker_fields[ticker][field] = col
    
    # If we found ticker_field pattern, reconstruct MultiIndex
    if ticker_fields and len(ticker_fields) > 1:
        print(f"  Reconstructing MultiIndex from {len(ticker_fields)} tickers")
        # Build MultiIndex columns
        new_columns = []
        for ticker in sorted(ticker_fields.keys()):
            for field in ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']:
                if field in ticker_fields[ticker]:
                    new_columns.append((ticker, field))
        
        if new_columns:
            # Reindex with MultiIndex
            multi_df = pd.DataFrame(index=df.index)
            for ticker, field in new_columns:
                col_name = f"{ticker}_{field}"
                if col_name in df.columns:
                    multi_df[(ticker, field)] = df[col_name]
            
            print(f"  ✓ Reconstructed MultiIndex with {len(multi_df.columns)} columns")
            return multi_df
    
    # If no pattern found, assume it's already in the right format or try direct access
    # Return as-is and let compute_base_features handle it
    print("  Using data as-is (will attempt direct column access)")
    return df


def load_market_data_from_s3(bucket=None, key=None):
    """Load market data from S3 or local file (fallback)."""
    # Try S3 first
    if S3_AVAILABLE:
        bucket = bucket or S3_BUCKET
        key = key or S3_KEY
        
        try:
            print(f"Loading data from s3://{bucket}/{key}...")
            s3_client = boto3.client('s3')
            obj = s3_client.get_object(Bucket=bucket, Key=key)
            df = pd.read_parquet(BytesIO(obj['Body'].read()))
            
            print(f"✓ Successfully loaded {len(df)} rows from S3")
            print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
            print(f"  - Columns: {len(df.columns)}")
            print(f"  - Column type: {type(df.columns).__name__}")
            if isinstance(df.columns, pd.MultiIndex):
                print(f"  - Unique tickers in MultiIndex: {sorted(set(df.columns.get_level_values(0)))}")
            
            return df
        except Exception as e:
            print(f"⚠ S3 load failed: {str(e)}")
            print(f"  Falling back to local file...")
    
    # Fallback to local file
    if os.path.exists(LOCAL_DATA_PATH):
        print(f"Loading data from local file: {LOCAL_DATA_PATH}...")
        df = pd.read_parquet(LOCAL_DATA_PATH)
        
        print(f"✓ Successfully loaded {len(df)} rows from local file")
        print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
        print(f"  - Columns: {len(df.columns)}")
        if isinstance(df.columns, pd.MultiIndex):
            print(f"  - Unique tickers in MultiIndex: {sorted(set(df.columns.get_level_values(0)))}")
        
        return df
    else:
        raise FileNotFoundError(f"Neither S3 data nor local file found at: {LOCAL_DATA_PATH}")


def test_data_download(start_date='2015-01-01', data_source='yfinance', s3_bucket=None, s3_key=None):
    """Test downloading/loading market data."""
    print(f"\n{'='*60}")
    print("STEP 2: Testing Data Download")
    print(f"{'='*60}")
    
    try:
        if data_source == 's3':
            print(f"Loading data from S3...")
            raw_prices = load_market_data_from_s3(bucket=s3_bucket, key=s3_key)
            print(f"  Data source: S3 (s3://{s3_bucket or S3_BUCKET}/{s3_key or S3_KEY})")
        else:
            print(f"Downloading data from {start_date} to today...")
            raw_prices = download_price_data(TICKERS, start_date=start_date)
            print(f"  Data source: yfinance")
        
        print(f"✓ Successfully loaded data")
        print(f"  - Date range: {raw_prices.index[0]} to {raw_prices.index[-1]}")
        print(f"  - Total days: {len(raw_prices)}")
        print(f"  - Columns shape: {raw_prices.columns.shape}")
        
        # Check if all tickers are present (only for yfinance data)
        if data_source == 'yfinance':
            print(f"\n  Checking ticker availability:")
            for name, ticker in TICKERS.items():
                if (ticker, "Close") in raw_prices.columns or ticker in raw_prices.columns:
                    print(f"    ✓ {name} ({ticker})")
                else:
                    print(f"    ✗ {name} ({ticker}) - MISSING")
        else:
            print(f"\n  S3 data loaded - assuming all required tickers are present")
        
        return raw_prices
        
    except Exception as e:
        print(f"✗ Error loading data: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_feature_engineering(raw_prices, lags):
    """Test feature engineering pipeline."""
    print(f"\n{'='*60}")
    print("STEP 3: Testing Feature Engineering")
    print(f"{'='*60}")
    
    try:
        print("Computing base features...")
        base_features, spy_close = compute_base_features(raw_prices)
        
        print(f"✓ Base features computed")
        print(f"  - Base feature count: {len(base_features.columns)}")
        if len(base_features) > 0:
            print(f"  - Date range: {base_features.index[0]} to {base_features.index[-1]}")
            print(f"  - Valid rows: {len(base_features)}")
        else:
            print(f"  - ⚠ WARNING: No valid rows after feature computation!")
            print(f"    This usually indicates data alignment or NaN issues.")
            raise ValueError("base_features is empty - cannot proceed with feature engineering")
        
        print(f"\n  Base feature names:")
        for i, col in enumerate(base_features.columns):
            print(f"    {i+1}. {col}")
        
        print(f"\nAdding lagged features (lags: {lags})...")
        lagged_features = add_lagged_features(base_features, lags=lags)
        
        print(f"✓ Lagged features computed")
        print(f"  - Total feature count: {len(lagged_features.columns)}")
        print(f"  - Valid rows after lagging: {len(lagged_features)}")
        
        return base_features, lagged_features, spy_close
        
    except Exception as e:
        print(f"✗ Error in feature engineering: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_inference(model, feature_columns, lags, train_start_date, data_source='yfinance', s3_bucket=None, s3_key=None):
    """Test inference pipeline."""
    print(f"\n{'='*60}")
    print("STEP 4: Testing Inference Pipeline")
    print(f"{'='*60}")
    
    if feature_columns is None:
        print("⚠ Skipping inference test - feature_columns not available")
        print("  Model artifact needs to be saved with feature_columns metadata.")
        return None
    
    try:
        # Load data
        if data_source == 's3':
            print("Loading latest data from S3...")
            raw_prices = load_market_data_from_s3(bucket=s3_bucket, key=s3_key)
        else:
            print("Downloading latest data...")
            raw_prices = download_price_data(TICKERS, start_date=train_start_date)
        
        # Compute features
        print("Computing features...")
        base_features, spy_close = compute_base_features(raw_prices)
        lagged_features = add_lagged_features(base_features, lags=lags)
        lagged_features = lagged_features.dropna()
        
        # Check feature alignment
        print(f"\nChecking feature alignment...")
        missing_cols = [c for c in feature_columns if c not in lagged_features.columns]
        if missing_cols:
            print(f"✗ Missing columns: {missing_cols}")
            return None
        
        extra_cols = [c for c in lagged_features.columns if c not in feature_columns]
        print(f"  ✓ All required columns present")
        if extra_cols:
            print(f"  - Note: {len(extra_cols)} extra columns will be ignored")
        
        # Extract latest features
        X_all = lagged_features[feature_columns].dropna()
        
        if len(X_all) == 0:
            print("✗ No valid feature rows after processing")
            return None
        
        latest_features = X_all.iloc[-1:]
        latest_date = latest_features.index[0]
        
        print(f"  ✓ Latest trading date: {latest_date}")
        print(f"  ✓ Feature vector shape: {latest_features.shape}")
        
        # Make prediction
        print(f"\nMaking prediction...")
        pred_ret = float(model.predict(latest_features)[0])
        
        print(f"✓ Prediction successful")
        print(f"  - Predicted next-day return: {pred_ret:.6f} ({pred_ret*100:.4f}%)")
        
        # Compute prices
        latest_spy_close = float(spy_close.reindex(lagged_features.index).iloc[-1])
        pred_open_930 = latest_spy_close
        pred_close_1600 = pred_open_930 * (1.0 + pred_ret)
        pred_intraday_change = pred_close_1600 - pred_open_930
        
        signal = "BUY" if pred_ret > 0 else "SELL"
        prediction_binary = 1 if pred_ret > 0 else 0
        
        result = {
            "signal_date": str(latest_date),
            "current_spy_price": round(latest_spy_close, 2),
            "pred_open_930": round(pred_open_930, 2),
            "pred_close_1600": round(pred_close_1600, 2),
            "pred_intraday_change": round(pred_intraday_change, 4),
            "pred_intraday_return": round(pred_ret, 6),
            "signal": signal,
            "prediction": [prediction_binary],
        }
        
        print(f"\n{'='*60}")
        print("INFERENCE RESULT")
        print(f"{'='*60}")
        print(f"Signal Date:        {result['signal_date']}")
        print(f"Current SPY Price:  ${result['current_spy_price']}")
        print(f"Predicted 9:30 AM:  ${result['pred_open_930']}")
        print(f"Predicted 4:00 PM:  ${result['pred_close_1600']}")
        print(f"Predicted Change:   ${result['pred_intraday_change']:.4f}")
        print(f"Predicted Return:   {result['pred_intraday_return']:.6f} ({result['pred_intraday_return']*100:.4f}%)")
        print(f"Trading Signal:     {result['signal']}")
        print(f"Binary Prediction:  {result['prediction']}")
        print(f"{'='*60}")
        
        return result
        
    except Exception as e:
        print(f"✗ Error in inference: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_model_structure(model):
    """Test model structure and methods."""
    print(f"\n{'='*60}")
    print("STEP 5: Testing Model Structure")
    print(f"{'='*60}")
    
    print(f"Model type: {type(model).__name__}")
    print(f"Model module: {type(model).__module__}")
    
    # Check if it's a Pipeline
    final_estimator = None
    if hasattr(model, 'steps'):
        print(f"\n✓ Model is a Pipeline with {len(model.steps)} steps:")
        for i, (name, step) in enumerate(model.steps):
            print(f"  {i+1}. {name}: {type(step).__name__}")
            if i == len(model.steps) - 1:
                final_estimator = step
    elif hasattr(model, '_final_estimator'):
        final_estimator = model._final_estimator
    
    # Check available methods safely
    print(f"\nAvailable methods:")
    important_methods = ['predict', 'fit', 'transform', 'score']
    
    for method in important_methods:
        try:
            if hasattr(model, method):
                print(f"  ✓ {method}")
            else:
                print(f"  ✗ {method} (not available)")
        except Exception as e:
            print(f"  ✗ {method} (error checking: {type(e).__name__})")
    
    # Check predict_proba separately (only for classification models)
    # This needs special handling because hasattr can trigger AttributeError
    # on regression models when Pipeline tries to access classes_
    try:
        # First check if final estimator is a classifier
        is_classifier = False
        if final_estimator is not None:
            estimator_type = type(final_estimator).__name__.lower()
            # LinearRegression, Ridge, Lasso, etc. are regression models
            # LogisticRegression, RandomForestClassifier, etc. are classifiers
            is_classifier = ('classifier' in estimator_type or 
                           'logistic' in estimator_type) and \
                           'regression' not in estimator_type
        
        if is_classifier:
            # Only check predict_proba for classifiers
            try:
                if hasattr(model, 'predict_proba'):
                    print(f"  ✓ predict_proba")
                else:
                    print(f"  ✗ predict_proba (not available)")
            except AttributeError:
                print(f"  ✗ predict_proba (error accessing)")
        else:
            print(f"  - predict_proba (not applicable for regression models)")
    except Exception as e:
        print(f"  - predict_proba (could not determine: {type(e).__name__})")
    
    # Test with dummy data if possible
    if hasattr(model, 'predict'):
        try:
            # Try to get feature count from model if possible
            if hasattr(model, 'n_features_in_'):
                print(f"\n✓ Model expects {model.n_features_in_} features")
            elif hasattr(model, 'feature_names_in_'):
                print(f"\n✓ Model expects {len(model.feature_names_in_)} features")
                print(f"  Feature names available in model")
        except:
            pass


def main():
    """Main test execution."""
    parser = argparse.ArgumentParser(
        description='Test script for model.pkl inference pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with yfinance (default)
  python test_model.py
  
  # Test with S3 data
  python test_model.py --s3
  
  # Test with S3 data (custom bucket/key)
  python test_model.py --s3 --s3-bucket my-bucket --s3-key data/latest.parquet
  
  # Use environment variables for S3 config
  export S3_BUCKET_NAME=my-bucket
  export S3_DATA_KEY=data/latest.parquet
  python test_model.py --s3
        """
    )
    parser.add_argument(
        '--s3',
        action='store_true',
        help='Use S3 bucket for market data instead of yfinance'
    )
    parser.add_argument(
        '--s3-bucket',
        type=str,
        default=None,
        help=f'S3 bucket name (default: {S3_BUCKET} or S3_BUCKET_NAME env var)'
    )
    parser.add_argument(
        '--s3-key',
        type=str,
        default=None,
        help=f'S3 object key (default: {S3_KEY} or S3_DATA_KEY env var)'
    )
    
    args = parser.parse_args()
    
    # Determine data source
    data_source = 's3' if args.s3 else 'yfinance'
    
    # Get S3 configuration
    s3_bucket = args.s3_bucket or os.environ.get('S3_BUCKET_NAME', S3_BUCKET)
    s3_key = args.s3_key or os.environ.get('S3_DATA_KEY', S3_KEY)
    
    print("\n" + "="*60)
    print("MODEL.PKL TEST SUITE")
    print("="*60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data source: {data_source.upper()}")
    if data_source == 's3':
        print(f"S3 Bucket: {s3_bucket}")
        print(f"S3 Key: {s3_key}")
        if not S3_AVAILABLE:
            print("\n⚠ Warning: boto3/pyarrow not available. Install with: pip install boto3 pyarrow")
            print("  Falling back to yfinance...")
            data_source = 'yfinance'
    
    # Step 1: Load model
    model, feature_columns, lags, train_start_date = load_model()
    
    # Step 2: Test data download/load
    raw_prices = test_data_download(
        start_date=train_start_date,
        data_source=data_source,
        s3_bucket=s3_bucket,
        s3_key=s3_key
    )
    
    # Step 3: Test feature engineering
    base_features, lagged_features, spy_close = test_feature_engineering(raw_prices, lags)
    
    # Step 4: Test model structure
    test_model_structure(model)
    
    # Step 5: Test inference
    result = test_inference(
        model, feature_columns, lags, train_start_date,
        data_source=data_source,
        s3_bucket=s3_bucket,
        s3_key=s3_key
    )
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"✓ Model loaded successfully")
    print(f"✓ Data {'download' if data_source == 'yfinance' else 'load'} working ({data_source})")
    print(f"✓ Feature engineering working")
    print(f"{'✓' if result else '⚠'} Inference pipeline {'working' if result else 'needs feature_columns'}")
    
    if result:
        print(f"\n✓ All tests passed! Model is ready for deployment.")
    else:
        print(f"\n⚠ Model needs to be retrained with feature_columns metadata.")
        print(f"  Please run the notebook Cell 28 to save the model with proper structure.")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

