#!/usr/bin/env python3
"""
SPY Buy/Sell Model Training Script

This script trains a linear regression and logistic regression model
to predict SPY next-day returns and generate BUY/SELL signals.

Usage:
    python create_buysell_model.py
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime

from sklearn.linear_model import LinearRegression
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    mean_squared_error,
    r2_score,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
from sklearn.linear_model import LogisticRegression

import pickle
import os

import yfinance as yf

plt.style.use("default")  # use a simple default style

# ============================================================================
# Configuration
# ============================================================================

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

LAGS = [1, 2, 5]  # you can tune these

# ============================================================================
# Data Download
# ============================================================================

def download_price_data(
    tickers_dict,
    start_date="2015-01-01",
    end_date=None,
    auto_adjust=True,
):
    """
    Download daily OHLCV data for all tickers using yfinance.

    Parameters
    ----------
    tickers_dict : dict
        Mapping of logical names -> yfinance tickers.
    start_date : str
        Start date 'YYYY-MM-DD'.
    end_date : str or None
        End date; None = today.
    auto_adjust : bool
        If True, adjust for splits/dividends.

    Returns
    -------
    prices : pd.DataFrame
        MultiIndex columns: (symbol, field) with a DatetimeIndex.
    """
    yf_tickers = " ".join(tickers_dict.values())
    data = yf.download(
        yf_tickers,
        start=start_date,
        end=end_date,
        auto_adjust=auto_adjust,
        group_by="ticker",
        progress=False
    )

    # Ensure MultiIndex columns even if only one ticker
    if isinstance(data.columns, pd.MultiIndex):
        prices = data
    else:
        # Single ticker case: wrap into MultiIndex
        symbol = list(tickers_dict.keys())[0]
        prices = pd.concat({symbol: data}, axis=1)

    # Sort columns for consistency
    prices = prices.sort_index(axis=1)
    return prices

# ============================================================================
# Feature Engineering
# ============================================================================

def compute_rsi(series, window=14):
    """
    Compute RSI (Relative Strength Index) for a price series.
    Uses the classic Wilder's smoothing approach.

    Parameters
    ----------
    series : pd.Series
        Price series (e.g., close).
    window : int
        Lookback period for RSI.

    Returns
    -------
    rsi : pd.Series
        RSI values (0-100).
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

    Parameters
    ----------
    raw : pd.DataFrame
        MultiIndex columns: (symbol, field).

    Returns
    -------
    features : pd.DataFrame
        Base feature matrix indexed by date.
    spy_close : pd.Series
        SPY adjusted close price (for target construction later).
    """
    # Extract per-symbol data for convenience
    spy = raw[TICKERS["SPY"]] if ("SPY", "Close") in raw.columns else raw["SPY"]
    qqq = raw[TICKERS["QQQ"]] if ("QQQ", "Close") in raw.columns else raw["QQQ"]
    gld = raw[TICKERS["GOLD"]] if ("GLD", "Close") in raw.columns else raw["GOLD"]
    uso = raw[TICKERS["OIL"]] if ("USO", "Close") in raw.columns else raw["USO"]
    tlt = raw[TICKERS["TLT"]] if ("TLT", "Close") in raw.columns else raw["TLT"]
    shy = raw[TICKERS["SHY"]] if ("SHY", "Close") in raw.columns else raw["SHY"]
    vix = raw[TICKERS["VIX"]] if ("^VIX", "Close") in raw.columns else raw["^VIX"]
    dxy = raw[TICKERS["DXY"]] if ("DX-Y.NYB", "Close") in raw.columns else raw["DX-Y.NYB"]

    def get_close(df):
        return df["Adj Close"] if "Adj Close" in df.columns else df["Close"]

    # We'll work with Adjusted Close and Volume where applicable
    spy_close = get_close(spy).copy()
    spy_vol = spy["Volume"].copy()

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

    For each column 'col' and lag k, we create 'col_lag{k}' = col.shift(k).

    Parameters
    ----------
    features : pd.DataFrame
        Base features indexed by date.
    lags : list[int]
        Lags in days.

    Returns
    -------
    features_with_lags : pd.DataFrame
        Features including original columns and their lags.
    """
    features_lagged = features.copy()
    for col in features.columns:
        for lag in lags:
            features_lagged[f"{col}_lag{lag}"] = features[col].shift(lag)
    # Drop rows with NaNs introduced by lags
    features_lagged = features_lagged.dropna()
    return features_lagged


def build_dataset(features, spy_close, forward_horizon=1):
    """
    Build feature matrix X and target vector y for next-day returns.

    We define target as:
        y_t = (C_{t+forward_horizon} / C_t) - 1

    Features at date t use info up to date t (including lags),
    and are used to predict y_t for the next forward_horizon days.

    Parameters
    ----------
    features : pd.DataFrame
        Features indexed by date (including lags).
    spy_close : pd.Series
        SPY adjusted close prices indexed by date.
    forward_horizon : int
        How many days ahead to predict.

    Returns
    -------
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series
        Target next-day (or horizon) return.
    full_df : pd.DataFrame
        Combined DataFrame with features and target.
    """
    # Align spy_close to features index
    spy_close_aligned = spy_close.reindex(features.index)

    # Forward return: (C_{t+h} / C_t - 1), then shift -h
    fwd_ret = spy_close_aligned.pct_change(forward_horizon).shift(-forward_horizon)

    full_df = features.copy()
    full_df["target_spy_fwd_ret"] = fwd_ret

    # Drop rows where target is NaN
    full_df = full_df.dropna(subset=["target_spy_fwd_ret"])

    X = full_df.drop(columns=["target_spy_fwd_ret"])
    y = full_df["target_spy_fwd_ret"]

    return X, y, full_df

# ============================================================================
# Model Training
# ============================================================================

def train_test_split_time_series(X, y, test_size=0.2):
    """
    Chronological train-test split for time series.

    Parameters
    ----------
    X : pd.DataFrame
    y : pd.Series
    test_size : float
        Fraction of data to use for the test set.

    Returns
    -------
    X_train, X_test, y_train, y_test
    """
    n_samples = len(X)
    n_test = int(n_samples * test_size)
    split_idx = n_samples - n_test

    X_train = X.iloc[:split_idx]
    y_train = y.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_test = y.iloc[split_idx:]

    return X_train, X_test, y_train, y_test


def create_linear_model():
    """
    Create a scikit-learn Pipeline with standardization + LinearRegression.
    """
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("linreg", LinearRegression())
        ]
    )
    return model


def time_series_cv_evaluation(X_train, y_train, n_splits=5):
    """
    Perform time-series cross-validation using TimeSeriesSplit.

    For each split:
        - Train a fresh model on the training fold.
        - Evaluate on the validation fold with MSE and R^2.

    Parameters
    ----------
    X_train : pd.DataFrame
    y_train : pd.Series
    n_splits : int
        Number of splits.

    Returns
    -------
    results : list[dict]
        List of metrics for each CV fold.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    results = []

    fold = 1
    for train_idx, val_idx in tscv.split(X_train):
        X_tr_fold = X_train.iloc[train_idx]
        y_tr_fold = y_train.iloc[train_idx]
        X_val_fold = X_train.iloc[val_idx]
        y_val_fold = y_train.iloc[val_idx]

        model = create_linear_model()
        model.fit(X_tr_fold, y_tr_fold)
        y_val_pred = model.predict(X_val_fold)

        mse = mean_squared_error(y_val_fold, y_val_pred)
        r2 = r2_score(y_val_fold, y_val_pred)

        results.append({"fold": fold, "mse": mse, "r2": r2})
        print(f"Fold {fold}: MSE={mse:.6f}, R^2={r2:.4f}")
        fold += 1

    return results


def evaluate_on_test(model, X_test, y_test):
    """
    Evaluate a fitted model on the test set and compute SSE, MSE, RMSE, R^2.

    Parameters
    ----------
    model : fitted sklearn estimator
    X_test : pd.DataFrame
    y_test : pd.Series

    Returns
    -------
    metrics : dict
        Dictionary with SSE, MSE, RMSE, R2, and y_pred.
    """
    y_pred = model.predict(X_test)

    residuals = y_test - y_pred
    sse = np.sum(residuals ** 2)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)

    print("=== Test Set Evaluation ===")
    print(f"SSE:  {sse:.6f}")
    print(f"MSE:  {mse:.6f}")
    print(f"RMSE: {rmse:.6f}")
    print(f"R^2:  {r2:.4f}")

    return {
        "SSE": sse,
        "MSE": mse,
        "RMSE": rmse,
        "R2": r2,
        "y_pred": y_pred,
    }

# ============================================================================
# Classification Evaluation
# ============================================================================

def evaluate_buy_sell_classification(model, X, y, dataset_name=""):
    """Evaluate BUY/SELL decisions based on the sign of predicted vs actual returns.

    Parameters
    ----------
    model : fitted sklearn estimator
        Regression model that predicts next-day returns.
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series or array-like
        True next-day returns.
    dataset_name : str
        Label for printing (e.g. 'Train' or 'Test').

    Returns
    -------
    result : dict
        Dictionary containing predictions, labels, confusion matrix and metrics.
    """
    # 1) Get regression predictions
    y_reg = model.predict(X)

    # 2) Convert to binary BUY/SELL labels
    # BUY (1) if return > 0, SELL (0) otherwise
    y_true_cls = (y > 0).astype(int)
    y_pred_cls = (y_reg > 0).astype(int)

    # 3) Confusion matrix and basic counts
    cm = confusion_matrix(y_true_cls, y_pred_cls, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    # 4) Metrics
    accuracy = accuracy_score(y_true_cls, y_pred_cls)
    precision = precision_score(y_true_cls, y_pred_cls, zero_division=0)
    recall = recall_score(y_true_cls, y_pred_cls, zero_division=0)   # sensitivity / TPR
    specificity = tn / (tn + fp) if (tn + fp) > 0 else float("nan")  # TNR
    f1 = f1_score(y_true_cls, y_pred_cls, zero_division=0)

    # 5) Format as tables
    cm_df = pd.DataFrame(
        cm,
        index=pd.Index(["Actual SELL (0)", "Actual BUY (1)"], name="Actual"),
        columns=pd.Index(["Pred SELL (0)", "Pred BUY (1)"], name="Predicted"),
    )

    metrics_df = pd.DataFrame(
        {
            "Metric": [
                "Accuracy",
                "Precision (PPV)",
                "Sensitivity (Recall / TPR)",
                "Specificity (TNR)",
                "F1-score",
            ],
            "Value": [
                accuracy,
                precision,
                recall,
                specificity,
                f1,
            ],
        }
    ).set_index("Metric")

    print(f"\n=== BUY/SELL Classification Evaluation ({dataset_name}) ===")
    print("\nConfusion Matrix:")
    print(cm_df)
    print("\nMetrics:")
    print(metrics_df)

    return {
        "y_reg": y_reg,
        "y_true_cls": y_true_cls,
        "y_pred_cls": y_pred_cls,
        "confusion_matrix": cm_df,
        "metrics": metrics_df,
    }


def create_logistic_pipeline():
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("logreg", LogisticRegression(
                penalty="l2",
                max_iter=2000,
                class_weight="balanced",  # helps if UP vs DOWN is imbalanced
                solver="lbfgs"
            ))
        ]
    )


def evaluate_logistic_buy_sell(model, X, y_cls, dataset_name="", threshold=0.5):
    """
    Evaluate a logistic regression directional model (BUY/SELL) at a given threshold.

    Parameters
    ----------
    model : fitted sklearn Pipeline with LogisticRegression
    X : pd.DataFrame
    y_cls : pd.Series (0/1)
        True class labels: 1 = UP (BUY), 0 = DOWN (SELL).
    dataset_name : str
        Label for printing (e.g. 'Train' or 'Test').
    threshold : float
        Probability cutoff for predicting class 1 (BUY).

    Returns
    -------
    result : dict
        Contains probabilities, labels, confusion matrix and metrics.
    """
    # Predicted probability of class 1 (UP)
    proba = model.predict_proba(X)[:, 1]
    y_pred = (proba >= threshold).astype(int)

    cm = confusion_matrix(y_cls, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    accuracy = accuracy_score(y_cls, y_pred)
    precision = precision_score(y_cls, y_pred, zero_division=0)
    recall = recall_score(y_cls, y_pred, zero_division=0)   # sensitivity / TPR
    specificity = tn / (tn + fp) if (tn + fp) > 0 else float("nan")
    f1 = f1_score(y_cls, y_pred, zero_division=0)

    cm_df = pd.DataFrame(
        cm,
        index=pd.Index(["Actual SELL (0)", "Actual BUY (1)"], name="Actual"),
        columns=pd.Index(["Pred SELL (0)", "Pred BUY (1)"], name="Predicted"),
    )

    metrics_df = pd.DataFrame(
        {
            "Metric": [
                "Accuracy",
                "Precision (PPV)",
                "Sensitivity (Recall / TPR)",
                "Specificity (TNR)",
                "F1-score",
            ],
            "Value": [
                accuracy,
                precision,
                recall,
                specificity,
                f1,
            ],
        }
    ).set_index("Metric")

    print(f"\n=== Logistic BUY/SELL Evaluation ({dataset_name}) @ threshold={threshold:.2f} ===")
    print("\nConfusion Matrix:")
    print(cm_df)
    print("\nMetrics:")
    print(metrics_df)

    return {
        "proba": proba,
        "y_true_cls": y_cls,
        "y_pred_cls": y_pred,
        "confusion_matrix": cm_df,
        "metrics": metrics_df,
    }


def find_best_threshold(y_true_cls, proba, metric="f1", thresholds=None):
    """
    Search over thresholds and find the one that maximizes a chosen metric.

    Parameters
    ----------
    y_true_cls : array-like (0/1)
    proba : array-like
        Predicted probabilities for class 1 (BUY).
    metric : str
        'f1' or 'accuracy'.
    thresholds : array-like or None
        Thresholds to search. If None, uses np.linspace(0.3, 0.7, 41).

    Returns
    -------
    best_thr : float
    best_val : float
    """
    if thresholds is None:
        thresholds = np.linspace(0.3, 0.7, 41)  # focus around 0.5

    best_thr = 0.5
    best_val = -np.inf

    for thr in thresholds:
        y_pred = (proba >= thr).astype(int)
        if metric == "f1":
            val = f1_score(y_true_cls, y_pred, zero_division=0)
        elif metric == "accuracy":
            val = accuracy_score(y_true_cls, y_pred)
        else:
            raise ValueError("Unsupported metric: use 'f1' or 'accuracy'.")

        if val > best_val:
            best_val = val
            best_thr = thr

    return best_thr, best_val

# ============================================================================
# Inference
# ============================================================================

def run_inference_v2(
    linear_model,
    logistic_model,
    feature_columns,
    threshold,
    tickers=TICKERS,
    start_date="2015-01-01",
    end_date=None,
    lags=LAGS,
    require_positive_return=True,
):
    """
    Inference pipeline (v2):
      - Linear regression --> next-day return magnitude.
      - Logistic regression --> probability next day is UP.
      - BUY/SELL decided from logistic prob (and optionally sign of linear prediction).

    Parameters
    ----------
    linear_model : fitted sklearn estimator
        Regression model for next-day return (final_model).
    logistic_model : fitted sklearn estimator
        Classification model for UP/DOWN (best_log_model).
    feature_columns : list[str]
        Column names used for training.
    threshold : float
        Probability cutoff for predicting BUY (class 1).
    tickers : dict
        Ticker mapping.
    start_date, end_date : str
        History window for features.
    lags : list[int]
        Lags used when training.
    require_positive_return : bool
        If True, require BOTH prob_up >= threshold AND predicted return > 0
        to issue BUY; otherwise SELL.

    Returns
    -------
    result : dict
        Prediction summary and signal.
    """
    # 1) Download fresh data
    recent_raw = download_price_data(
        tickers,
        start_date=start_date,
        end_date=end_date,
        auto_adjust=True
    )
    
    # 2) Recompute base + lagged features
    recent_base, recent_spy_close = compute_base_features(recent_raw)
    recent_lagged = add_lagged_features(recent_base, lags=lags)
    recent_lagged = recent_lagged.dropna()

    # 3) Align to training feature columns
    missing_cols = [c for c in feature_columns if c not in recent_lagged.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in inference features: {missing_cols}")

    X_all = recent_lagged[feature_columns].dropna()

    # Latest row = most recent trading day
    latest_features = X_all.iloc[-1:]
    latest_date = latest_features.index[0]

    # 4) Linear regression prediction for next-day return
    pred_ret = float(linear_model.predict(latest_features)[0])

    # 5) Logistic prediction for probability of UP (BUY)
    prob_up = float(logistic_model.predict_proba(latest_features)[0, 1])

    # 6) Map predicted return to prices (as before)
    latest_spy_close = float(recent_spy_close.reindex(recent_lagged.index).iloc[-1])
    pred_open_930 = latest_spy_close
    pred_close_1600 = pred_open_930 * (1.0 + pred_ret)
    pred_intraday_change = pred_close_1600 - pred_open_930

    # 7) Decide signal
    if require_positive_return:
        if (prob_up >= threshold) and (pred_ret > 0):
            signal = "BUY"
        else:
            signal = "SELL"
    else:
        signal = "BUY" if prob_up >= threshold else "SELL"

    # 8) Package result
    result = {
        "signal_date": latest_date,
        "prob_up": prob_up,
        "threshold": threshold,
        "pred_open_930": pred_open_930,
        "pred_close_1600": pred_close_1600,
        "pred_intraday_change": pred_intraday_change,
        "pred_intraday_return": pred_ret,
        "signal": signal,
    }

    return result

# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Main training pipeline."""
    print("=" * 60)
    print("SPY Buy/Sell Model Training")
    print("=" * 60)
    print()

    # 1. Download data
    print("Step 1: Downloading market data...")
    start_date = "2015-01-01"
    raw_prices = download_price_data(TICKERS, start_date=start_date)
    print(f"Downloaded {len(raw_prices)} days of data")
    print()

    # 2. Compute features
    print("Step 2: Computing features...")
    base_features, spy_close = compute_base_features(raw_prices)
    print(f"Base features shape: {base_features.shape}")
    
    lagged_features = add_lagged_features(base_features, lags=LAGS)
    print(f"Lagged features shape: {lagged_features.shape}")
    print()

    # 3. Build dataset
    print("Step 3: Building supervised dataset...")
    X, y, supervised_df = build_dataset(lagged_features, spy_close, forward_horizon=1)
    print(f"Feature matrix shape: {X.shape}, Target shape: {y.shape}")
    print()

    # 4. Train/test split
    print("Step 4: Splitting into train/test sets...")
    X_train, X_test, y_train, y_test = train_test_split_time_series(X, y, test_size=0.2)
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")
    print()

    # 5. Cross-validation
    print("Step 5: Running time-series cross-validation...")
    cv_results = time_series_cv_evaluation(X_train, y_train, n_splits=5)
    print()

    # 6. Train final linear model
    print("Step 6: Training final linear regression model...")
    final_model = create_linear_model()
    final_model.fit(X_train, y_train)
    feature_columns = X_train.columns.tolist()
    print("✓ Model trained")
    print()

    # 7. Evaluate linear model
    print("Step 7: Evaluating linear model on test set...")
    test_metrics = evaluate_on_test(final_model, X_test, y_test)
    y_test_pred = test_metrics["y_pred"]
    print()

    # 8. Classification evaluation (linear model)
    print("Step 8: Evaluating BUY/SELL classification (linear model)...")
    train_class_results = evaluate_buy_sell_classification(
        final_model, X_train, y_train, dataset_name="Train"
    )
    test_class_results = evaluate_buy_sell_classification(
        final_model, X_test, y_test, dataset_name="Test"
    )
    print()

    # 9. Train logistic regression
    print("Step 9: Training logistic regression model...")
    y_train_cls = (y_train > 0).astype(int)
    y_test_cls = (y_test > 0).astype(int)
    
    print("Class balance (Train):")
    print(y_train_cls.value_counts(normalize=True).rename("proportion"))
    print("\nClass balance (Test):")
    print(y_test_cls.value_counts(normalize=True).rename("proportion"))
    print()

    tscv = TimeSeriesSplit(n_splits=5)
    param_grid = {
        "logreg__C": [0.01, 0.1, 1.0, 10.0, 100.0],
    }

    logreg_grid = GridSearchCV(
        estimator=create_logistic_pipeline(),
        param_grid=param_grid,
        cv=tscv,
        scoring="f1",      # optimise balanced precision/recall
        n_jobs=-1,
        refit=True         # refit best model on full training set
    )

    logreg_grid.fit(X_train, y_train_cls)
    best_log_model = logreg_grid.best_estimator_
    print(f"\nBest logistic C (from CV): {logreg_grid.best_params_['logreg__C']}")
    print(f"Best mean CV F1: {logreg_grid.best_score_:.6f}")
    print()

    # 10. Evaluate logistic model
    print("Step 10: Evaluating logistic model...")
    log_train_results = evaluate_logistic_buy_sell(
        best_log_model, X_train, y_train_cls, dataset_name="Train", threshold=0.5
    )
    log_test_results = evaluate_logistic_buy_sell(
        best_log_model, X_test, y_test_cls, dataset_name="Test", threshold=0.5
    )
    print()

    # 11. Find best threshold
    print("Step 11: Finding optimal threshold...")
    best_thr, best_f1 = find_best_threshold(
        y_true_cls=log_train_results["y_true_cls"],
        proba=log_train_results["proba"],
        metric="f1"
    )
    print(f"\nBest threshold on TRAIN (by F1): {best_thr:.3f}, F1={best_f1:.4f}")
    print()

    log_train_results_tuned = evaluate_logistic_buy_sell(
        best_log_model, X_train, y_train_cls,
        dataset_name="Train (tuned)", threshold=best_thr
    )
    log_test_results_tuned = evaluate_logistic_buy_sell(
        best_log_model, X_test, y_test_cls,
        dataset_name="Test (tuned)", threshold=best_thr
    )
    print()

    # 12. Run inference
    print("Step 12: Running inference on latest data...")
    inference_result_v2 = run_inference_v2(
        linear_model=final_model,
        logistic_model=best_log_model,
        feature_columns=feature_columns,
        threshold=best_thr,
        start_date="2018-01-01",
        require_positive_return=True
    )

    print("=== Inference Result v2 (Educational) ===")
    print(f"Signal date (features as of): {inference_result_v2['signal_date'].date()}")
    print(f"Probability next day is UP:  {inference_result_v2['prob_up']:.3f}")
    print(f"Threshold used:              {inference_result_v2['threshold']:.3f}")
    print(f"Predicted 9:30 price:        {inference_result_v2['pred_open_930']:.2f}")
    print(f"Predicted 16:00 price:       {inference_result_v2['pred_close_1600']:.2f}")
    print(f"Predicted intraday change:   {inference_result_v2['pred_intraday_change']:.4f}")
    print(f"Predicted intraday return:   {inference_result_v2['pred_intraday_return']:.6f}")
    print(f"Final trading signal:        {inference_result_v2['signal']}")
    print()

    # 13. Save model
    print("Step 13: Saving model artifacts...")
    artifact = {
        "linear_model": final_model,
        "logistic_model": best_log_model,
        "feature_columns": feature_columns,
        "lags": LAGS,
        "threshold": best_thr,
        "train_start_date": start_date,
        "tickers": TICKERS,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    artifact_filename = "model.pkl"
    with open(artifact_filename, "wb") as f:
        pickle.dump(artifact, f)

    print(f"Saved model artifact to: {os.path.abspath(artifact_filename)}")
    print()

    # 14. Generate requirements
    required_packages = [
        "pandas",
        "numpy",
        "scikit-learn",
        "matplotlib",
        "yfinance"
    ]

    req_filename = "requirements.txt"
    with open(req_filename, "w") as f:
        f.write("\n".join(required_packages))

    print(f"Generated requirements file at: {os.path.abspath(req_filename)}")
    print()

    print("=" * 60)
    print("Training Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

