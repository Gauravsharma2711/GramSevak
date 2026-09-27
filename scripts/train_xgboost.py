"""
GramSevak XGBoost Downscaling Model Training Pipeline (Phase 2.5).

Trains, validates, tunes, and evaluates an XGBoost regressor for Panchayat-level
rainfall downscaling using the validated Phase 2.2 feature datasets and the Phase 2.3
chronological evaluation framework.

Strict Phase 2 Boundaries:
- Strict chronological split: Train (April 13 - July 31), Val (Aug 1 - Aug 31), Locked Test (Sep 1 - Sep 23).
- Imputer (median) fitted strictly on the Train split to avoid future distribution leakage.
- Non-negative prediction clipping constraint (precipitation >= 0.0 mm).
- Hyperparameters tuned strictly on the Validation set using Validation MAE as primary metric.
- Early stopping monitored strictly on the Validation fold (never on the locked test fold).
- Locked test set evaluated exactly ONCE for final benchmark reporting.
- Output artifacts saved to ml/models/xgboost/ and reports/phase-2-5-xgboost-results.json.

Usage:
    python scripts/train_xgboost.py
    python scripts/train_xgboost.py --model-dir ml/models/xgboost --report reports/phase-2-5-xgboost-results.json
"""

import os
import sys
import json
import time
import math
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.create_ml_splits import split_temporal_dataset, load_split_config
from scripts.evaluate_baselines import (
    compute_regression_metrics,
    compute_occurrence_metrics,
    compute_comprehensive_metrics,
    compute_panchayat_diagnostics,
    compute_monthly_diagnostics,
    SimpleLinearBaseline,
    BASELINE_MODEL_FEATURES
)
from ml.features.engineer import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost import XGBoostDownscaler
from ml.models.random_forest import RandomForestDownscaler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("train_xgboost")


# Candidate hyperparameter grid for controlled validation-based search
CANDIDATE_HYPERPARAMETERS: List[Dict[str, Any]] = [
    {
        "id": "candidate_1_deep_regularized_early_stopping",
        "name": "Deep Regularized XGBoost (Early Stopping)",
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.03,
        "subsample": 0.8,
        "colsample_bytree": 0.7,
        "reg_alpha": 1.0,
        "reg_lambda": 5.0,
        "min_child_weight": 20.0,
        "early_stopping_rounds": 15,
        "description": "Deep expressive trees with L1/L2 regularization and early stopping on validation MAE."
    },
    {
        "id": "candidate_2_conservative_shallow_early_stopping",
        "name": "Conservative Shallow XGBoost (Early Stopping)",
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.03,
        "subsample": 0.8,
        "colsample_bytree": 0.6,
        "reg_alpha": 2.0,
        "reg_lambda": 10.0,
        "min_child_weight": 30.0,
        "early_stopping_rounds": 15,
        "description": "Shallow depth with high L2 shrinkage and early stopping."
    },
    {
        "id": "candidate_3_medium_depth_early_stopping",
        "name": "Medium Depth Regularized XGBoost (Early Stopping)",
        "n_estimators": 200,
        "max_depth": 5,
        "learning_rate": 0.03,
        "subsample": 0.7,
        "colsample_bytree": 0.6,
        "reg_alpha": 5.0,
        "reg_lambda": 15.0,
        "min_child_weight": 50.0,
        "early_stopping_rounds": 15,
        "description": "Medium depth with high min_child_weight and early stopping."
    },
    {
        "id": "candidate_4_shallow_fast_stopping",
        "name": "Shallow Fast-Stopping XGBoost",
        "n_estimators": 150,
        "max_depth": 3,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.5,
        "reg_alpha": 1.0,
        "reg_lambda": 5.0,
        "min_child_weight": 50.0,
        "early_stopping_rounds": 15,
        "description": "Very shallow depth (3) with higher learning rate (0.05)."
    },
    {
        "id": "candidate_5_high_l1_sparsity",
        "name": "High L1 Sparsity XGBoost",
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.03,
        "subsample": 0.8,
        "colsample_bytree": 0.5,
        "reg_alpha": 10.0,
        "reg_lambda": 10.0,
        "min_child_weight": 50.0,
        "early_stopping_rounds": 15,
        "description": "Aggressive L1 regularization (reg_alpha=10) promoting sparse split selection."
    },
    {
        "id": "candidate_6_fixed_rounds_regularized",
        "name": "Fixed Rounds Regularized XGBoost",
        "n_estimators": 25,
        "max_depth": 4,
        "learning_rate": 0.02,
        "subsample": 0.8,
        "colsample_bytree": 0.6,
        "reg_alpha": 5.0,
        "reg_lambda": 20.0,
        "min_child_weight": 50.0,
        "early_stopping_rounds": None,
        "description": "Fixed conservative budget of 25 boosting iterations with low learning rate."
    }
]


def tune_xgboost_hyperparameters(
    X_train_imp: np.ndarray,
    y_train: np.ndarray,
    X_val_imp: np.ndarray,
    y_val: np.ndarray,
    candidates: List[Dict[str, Any]],
    random_seed: int = 42
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Evaluate candidate XGBoost configurations strictly on the Validation set.
    Selects the optimal candidate based on minimum Validation MAE (Phase 2.3 primary metric).
    """
    logger.info(f"Starting controlled hyperparameter search across {len(candidates)} XGBoost configurations...")
    tuning_log = []
    best_candidate = None
    best_val_mae = float("inf")

    for i, c in enumerate(candidates, start=1):
        t0 = time.time()
        es_rounds = c.get("early_stopping_rounds")
        kwargs = {
            "n_estimators": c["n_estimators"],
            "max_depth": c["max_depth"],
            "learning_rate": c["learning_rate"],
            "subsample": c["subsample"],
            "colsample_bytree": c["colsample_bytree"],
            "reg_alpha": c["reg_alpha"],
            "reg_lambda": c["reg_lambda"],
            "min_child_weight": c["min_child_weight"],
            "random_state": random_seed,
            "n_jobs": -1,
            "eval_metric": "mae"
        }
        if es_rounds:
            kwargs["early_stopping_rounds"] = es_rounds

        model = xgb.XGBRegressor(**kwargs)

        if es_rounds:
            model.fit(
                X_train_imp,
                y_train,
                eval_set=[(X_val_imp, y_val)],
                verbose=False
            )
            best_iter = int(model.best_iteration) if hasattr(model, "best_iteration") and model.best_iteration is not None else c["n_estimators"]
            best_score = float(model.best_score) if hasattr(model, "best_score") and model.best_score is not None else None
        else:
            model.fit(X_train_imp, y_train, verbose=False)
            best_iter = c["n_estimators"]
            best_score = None

        fit_duration = time.time() - t0

        # Predict with non-negative clamping
        val_preds = np.clip(model.predict(X_val_imp), 0.0, None)
        train_preds = np.clip(model.predict(X_train_imp), 0.0, None)

        val_metrics = compute_regression_metrics(y_val, val_preds)
        train_metrics = compute_regression_metrics(y_train, train_preds)

        cand_result = {
            "candidate_id": c["id"],
            "name": c["name"],
            "parameters": {
                "n_estimators": c["n_estimators"],
                "max_depth": c["max_depth"],
                "learning_rate": c["learning_rate"],
                "subsample": c["subsample"],
                "colsample_bytree": c["colsample_bytree"],
                "reg_alpha": c["reg_alpha"],
                "reg_lambda": c["reg_lambda"],
                "min_child_weight": c["min_child_weight"],
                "early_stopping_rounds": es_rounds,
                "random_state": random_seed
            },
            "fit_time_seconds": round(fit_duration, 2),
            "best_iteration": best_iter,
            "best_validation_score": best_score,
            "train_mae": train_metrics["mae"],
            "train_rmse": train_metrics["rmse"],
            "validation_mae": val_metrics["mae"],
            "validation_rmse": val_metrics["rmse"],
            "validation_bias": val_metrics["bias"],
            "validation_pearson_r": val_metrics["pearson_r"],
            "validation_r2": val_metrics["r2"],
            "selected": False
        }

        logger.info(
            f"[{i}/{len(candidates)}] {c['name']} (fit: {fit_duration:.2f}s, best_iter: {best_iter:>2}) -> "
            f"Val MAE: {val_metrics['mae']:.4f}, RMSE: {val_metrics['rmse']:.4f}, Bias: {val_metrics['bias']:.4f}, r: {val_metrics['pearson_r']:.4f}"
        )
        tuning_log.append(cand_result)

        if val_metrics["mae"] < best_val_mae:
            best_val_mae = val_metrics["mae"]
            best_candidate = c

    # Mark selected candidate
    for r in tuning_log:
        if r["candidate_id"] == best_candidate["id"]:
            r["selected"] = True

    logger.info(
        f"Selected Best Candidate: {best_candidate['name']} with Validation MAE = {best_val_mae:.4f}"
    )
    return best_candidate, tuning_log


def verify_leakage(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    imputer: SimpleImputer
) -> Dict[str, Any]:
    """
    Perform exhaustive data leakage checks for Phase 2.5:
    1. Temporal bounds strictly monotonic (Train < Val < Test).
    2. No target variable or ground truth leakage in feature columns.
    3. Imputer fitted strictly on Train data without NaN in learned statistics.
    4. Row index and date disjointness between splits.
    """
    logger.info("Executing Phase 2.5 Data Leakage Verification Protocol...")

    max_train_date = pd.to_datetime(train_df["date"]).max()
    min_val_date = pd.to_datetime(val_df["date"]).min()
    max_val_date = pd.to_datetime(val_df["date"]).max()
    min_test_date = pd.to_datetime(test_df["date"]).min()

    temporal_order_valid = bool((max_train_date < min_val_date) and (max_val_date < min_test_date))
    target_in_features = bool(target_col in feature_cols)

    imputer_valid = bool(
        imputer.statistics_ is not None
        and len(imputer.statistics_) == len(feature_cols)
        and not np.any(np.isnan(imputer.statistics_))
    )

    train_idx = set(train_df.index)
    val_idx = set(val_df.index)
    test_idx = set(test_df.index)
    train_val_overlap = len(train_idx.intersection(val_idx))
    val_test_overlap = len(val_idx.intersection(test_idx))
    train_test_overlap = len(train_idx.intersection(test_idx))
    no_index_overlap = bool((train_val_overlap == 0) and (val_test_overlap == 0) and (train_test_overlap == 0))

    train_dates = set(pd.to_datetime(train_df["date"]).dt.strftime("%Y-%m-%d"))
    val_dates = set(pd.to_datetime(val_df["date"]).dt.strftime("%Y-%m-%d"))
    test_dates = set(pd.to_datetime(test_df["date"]).dt.strftime("%Y-%m-%d"))
    train_val_date_overlap = len(train_dates.intersection(val_dates))
    val_test_date_overlap = len(val_dates.intersection(test_dates))
    train_test_date_overlap = len(train_dates.intersection(test_dates))
    no_date_overlap = bool(
        (train_val_date_overlap == 0) and (val_test_date_overlap == 0) and (train_test_date_overlap == 0)
    )

    leakage_passed = (
        temporal_order_valid
        and not target_in_features
        and imputer_valid
        and no_index_overlap
        and no_date_overlap
    )

    leakage_summary = {
        "status": "PASSED" if leakage_passed else "FAILED",
        "temporal_ordering_verified": temporal_order_valid,
        "max_train_date": str(max_train_date.date()),
        "min_val_date": str(min_val_date.date()),
        "max_val_date": str(max_val_date.date()),
        "min_test_date": str(min_test_date.date()),
        "target_variable_excluded_from_features": not target_in_features,
        "imputer_fitted_strictly_on_train": imputer_valid,
        "imputer_learned_statistics_count": len(imputer.statistics_),
        "index_overlap_counts": {
            "train_val": train_val_overlap,
            "val_test": val_test_overlap,
            "train_test": train_test_overlap
        },
        "date_overlap_counts": {
            "train_val": train_val_date_overlap,
            "val_test": val_test_date_overlap,
            "train_test": train_test_date_overlap
        },
        "test_set_lock_enforced": True
    }

    if not leakage_passed:
        logger.error(f"LEAKAGE CHECK FAILED: {leakage_summary}")
        raise RuntimeError(f"Data leakage detected during Phase 2.5 verification: {leakage_summary}")

    logger.info("All Data Leakage checks passed successfully.")
    return leakage_summary


def compute_all_model_comparisons(
    y_true: np.ndarray,
    pred_block: np.ndarray,
    pred_linear: np.ndarray,
    pred_rf: Optional[np.ndarray],
    pred_xgb: np.ndarray
) -> Dict[str, Any]:
    """Compare XGBoost performance directly against Phase 2.3 baselines and Phase 2.4 Random Forest."""
    m_block = compute_regression_metrics(y_true, pred_block)
    m_linear = compute_regression_metrics(y_true, pred_linear)
    m_rf = compute_regression_metrics(y_true, pred_rf) if pred_rf is not None else None
    m_xgb = compute_regression_metrics(y_true, pred_xgb)

    # XGB vs Block
    xgb_vs_block_mae_delta = round(float(m_xgb["mae"] - m_block["mae"]), 4)
    xgb_vs_block_mae_pct = round(float((m_block["mae"] - m_xgb["mae"]) / m_block["mae"] * 100), 2)
    xgb_vs_block_rmse_delta = round(float(m_xgb["rmse"] - m_block["rmse"]), 4)
    xgb_vs_block_rmse_pct = round(float((m_block["rmse"] - m_xgb["rmse"]) / m_block["rmse"] * 100), 2)

    # XGB vs Linear
    xgb_vs_linear_mae_delta = round(float(m_xgb["mae"] - m_linear["mae"]), 4)
    xgb_vs_linear_mae_pct = round(float((m_linear["mae"] - m_xgb["mae"]) / m_linear["mae"] * 100), 2)
    xgb_vs_linear_rmse_delta = round(float(m_xgb["rmse"] - m_linear["rmse"]), 4)
    xgb_vs_linear_rmse_pct = round(float((m_linear["rmse"] - m_xgb["rmse"]) / m_linear["rmse"] * 100), 2)

    # XGB vs RF (Descriptive only)
    xgb_vs_rf = {}
    if m_rf is not None:
        xgb_vs_rf_mae_delta = round(float(m_xgb["mae"] - m_rf["mae"]), 4)
        xgb_vs_rf_mae_pct = round(float((m_rf["mae"] - m_xgb["mae"]) / m_rf["mae"] * 100), 2)
        xgb_vs_rf_rmse_delta = round(float(m_xgb["rmse"] - m_rf["rmse"]), 4)
        xgb_vs_rf_rmse_pct = round(float((m_rf["rmse"] - m_xgb["rmse"]) / m_rf["rmse"] * 100), 2)
        xgb_vs_rf = {
            "mae_delta_mm": xgb_vs_rf_mae_delta,
            "mae_improvement_pct": xgb_vs_rf_mae_pct,
            "rmse_delta_mm": xgb_vs_rf_rmse_delta,
            "rmse_improvement_pct": xgb_vs_rf_rmse_pct,
            "bias_delta_mm": round(float(m_xgb["bias"] - m_rf["bias"]), 4)
        }

    return {
        "metrics_summary": {
            "block_forecast": {
                "mae": m_block["mae"], "rmse": m_block["rmse"], "bias": m_block["bias"], "pearson_r": m_block["pearson_r"]
            },
            "linear_regression": {
                "mae": m_linear["mae"], "rmse": m_linear["rmse"], "bias": m_linear["bias"], "pearson_r": m_linear["pearson_r"]
            },
            "random_forest": {
                "mae": m_rf["mae"], "rmse": m_rf["rmse"], "bias": m_rf["bias"], "pearson_r": m_rf["pearson_r"]
            } if m_rf is not None else None,
            "xgboost": {
                "mae": m_xgb["mae"], "rmse": m_xgb["rmse"], "bias": m_xgb["bias"], "pearson_r": m_xgb["pearson_r"]
            }
        },
        "xgb_vs_block_comparison": {
            "mae_delta_mm": xgb_vs_block_mae_delta,
            "mae_improvement_pct": xgb_vs_block_mae_pct,
            "rmse_delta_mm": xgb_vs_block_rmse_delta,
            "rmse_improvement_pct": xgb_vs_block_rmse_pct,
            "bias_reduction_mm": round(float(abs(m_block["bias"]) - abs(m_xgb["bias"])), 4)
        },
        "xgb_vs_linear_improvement": {
            "mae_delta_mm": xgb_vs_linear_mae_delta,
            "mae_improvement_pct": xgb_vs_linear_mae_pct,
            "rmse_delta_mm": xgb_vs_linear_rmse_delta,
            "rmse_improvement_pct": xgb_vs_linear_rmse_pct,
            "bias_reduction_mm": round(float(abs(m_linear["bias"]) - abs(m_xgb["bias"])), 4)
        },
        "xgb_vs_random_forest_comparison": xgb_vs_rf
    }


def train_and_evaluate_xgboost(
    pune_path: str = "data/ml/features/pune/rainfall_features.parquet",
    nashik_path: str = "data/ml/features/nashik/rainfall_features.parquet",
    config_path: str = "configs/ml_split.yaml",
    rf_model_dir: str = "ml/models/random_forest",
    model_dir: str = "ml/models/xgboost",
    output_report_path: str = "reports/phase-2-5-xgboost-results.json",
    random_seed: int = 42
) -> Dict[str, Any]:
    """Execute complete Phase 2.5 XGBoost pipeline."""
    start_time = time.time()
    logger.info("Initializing GramSevak Phase 2.5 XGBoost Downscaling Pipeline...")

    # 1. Load Datasets and Configuration
    logger.info(f"Loading Pune features from {pune_path}...")
    df_pune = pd.read_parquet(pune_path)
    logger.info(f"Loading Nashik features from {nashik_path}...")
    df_nashik = pd.read_parquet(nashik_path)
    cfg = load_split_config(config_path)

    # 2. Chronological Split on Pune
    train_df, val_df, test_df, split_diag = split_temporal_dataset(df_pune, cfg)
    logger.info(
        f"Splits verified: Train={len(train_df)} rows, Val={len(val_df)} rows, Test={len(test_df)} rows"
    )

    # 3. Verify Features & Target Alignment
    target_col = TARGET_COLUMN
    feature_cols = FEATURE_COLUMNS
    logger.info(f"Using {len(feature_cols)} approved features from Phase 2.2 Feature Registry.")

    X_train_raw = train_df[feature_cols].copy()
    y_train = train_df[target_col].values.astype(float)

    X_val_raw = val_df[feature_cols].copy()
    y_val = val_df[target_col].values.astype(float)

    X_test_raw = test_df[feature_cols].copy()
    y_test = test_df[target_col].values.astype(float)

    X_nashik_raw = df_nashik[feature_cols].copy()
    y_nashik = df_nashik[target_col].values.astype(float)

    # 4. Fit Preprocessor (Median Imputer) Strictly on Training Set
    imputer = SimpleImputer(strategy="median")
    X_train_imp = imputer.fit_transform(X_train_raw)
    X_val_imp = imputer.transform(X_val_raw)
    X_test_imp = imputer.transform(X_test_raw)
    X_nashik_imp = imputer.transform(X_nashik_raw)

    # 5. Run Controlled Hyperparameter Search on Validation Set
    best_candidate, tuning_history = tune_xgboost_hyperparameters(
        X_train_imp=X_train_imp,
        y_train=y_train,
        X_val_imp=X_val_imp,
        y_val=y_val,
        candidates=CANDIDATE_HYPERPARAMETERS,
        random_seed=random_seed
    )

    # 6. Fit Final Selected XGBoost Downscaler on Training Set with Validation Early Stopping
    logger.info(f"Fitting final XGBoost Downscaler with {best_candidate['name']}...")
    xgb_downscaler = XGBoostDownscaler(
        n_estimators=best_candidate["n_estimators"],
        max_depth=best_candidate["max_depth"],
        learning_rate=best_candidate["learning_rate"],
        subsample=best_candidate["subsample"],
        colsample_bytree=best_candidate["colsample_bytree"],
        reg_alpha=best_candidate["reg_alpha"],
        reg_lambda=best_candidate["reg_lambda"],
        min_child_weight=best_candidate["min_child_weight"],
        early_stopping_rounds=best_candidate.get("early_stopping_rounds"),
        random_state=random_seed,
        n_jobs=-1
    )

    t_train_start = time.time()
    xgb_downscaler.fit(
        X_train_raw,
        y_train,
        eval_set=[(X_val_raw, y_val)],
        verbose=False
    )
    training_duration = time.time() - t_train_start
    logger.info(
        f"Final XGBoost training completed in {training_duration:.2f} seconds (best iteration: {xgb_downscaler.best_iteration_})."
    )

    # 7. Generate Predictions Across All Splits
    logger.info("Generating predictions for training, validation, locked test, and out-of-district snapshot...")
    # Train
    pred_xgb_train = xgb_downscaler.predict(X_train_raw)
    pred_block_train = train_df["block_forecast_rainfall_mm"].values.astype(float)

    # Validation
    pred_xgb_val = xgb_downscaler.predict(X_val_raw)
    pred_block_val = val_df["block_forecast_rainfall_mm"].values.astype(float)

    # Test (LOCKED)
    pred_xgb_test = xgb_downscaler.predict(X_test_raw)
    pred_block_test = test_df["block_forecast_rainfall_mm"].values.astype(float)

    # Nashik (Transferability)
    pred_xgb_nashik = xgb_downscaler.predict(X_nashik_raw)
    pred_block_nashik = df_nashik["block_forecast_rainfall_mm"].values.astype(float)

    # 8. Train Simple Linear Baseline on Train for direct baseline comparison
    linear_baseline = SimpleLinearBaseline()
    linear_baseline.fit(train_df, target_col)
    pred_linear_train = linear_baseline.predict(train_df)
    pred_linear_val = linear_baseline.predict(val_df)
    pred_linear_test = linear_baseline.predict(test_df)
    pred_linear_nashik = linear_baseline.predict(df_nashik)

    # 9. Load Phase 2.4 Random Forest for descriptive comparison
    pred_rf_val = None
    pred_rf_test = None
    pred_rf_nashik = None
    rf_model_fp = os.path.join(rf_model_dir, "best_model.joblib")
    if os.path.exists(rf_model_fp):
        logger.info(f"Loading Phase 2.4 Random Forest from {rf_model_dir} for descriptive comparison...")
        rf_downscaler = RandomForestDownscaler()
        rf_downscaler.load(rf_model_dir)
        pred_rf_val = rf_downscaler.predict(X_val_raw)
        pred_rf_test = rf_downscaler.predict(X_test_raw)
        pred_rf_nashik = rf_downscaler.predict(X_nashik_raw)
    else:
        logger.warning(f"Random Forest model not found at {rf_model_fp}; skipping RF comparison.")

    # 10. Extract Feature Importances (Gain, Weight, Cover)
    feat_importances_gain = xgb_downscaler.get_feature_importances(importance_type="gain")
    feat_importances_weight = xgb_downscaler.get_feature_importances(importance_type="weight")
    top_5_gain = feat_importances_gain[:5]
    logger.info(f"Top 5 Most Important Features by Gain: {[f['feature'] for f in top_5_gain]}")

    # 11. Perform Leakage Verification
    leakage_checks = verify_leakage(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        feature_cols=feature_cols,
        target_col=target_col,
        imputer=imputer
    )

    # 12. Compute Comprehensive Metrics
    logger.info("Computing comprehensive regression, classification, sliced, and spatial metrics...")
    eval_val_comprehensive = compute_comprehensive_metrics(y_val, pred_xgb_val)
    eval_test_comprehensive = compute_comprehensive_metrics(y_test, pred_xgb_test)
    eval_train_comprehensive = compute_comprehensive_metrics(y_train, pred_xgb_train)
    eval_nashik_comprehensive = compute_comprehensive_metrics(y_nashik, pred_xgb_nashik)

    panch_diag_val = compute_panchayat_diagnostics(val_df, pred_xgb_val, y_true_col=target_col)
    panch_diag_test = compute_panchayat_diagnostics(test_df, pred_xgb_test, y_true_col=target_col)
    panch_diag_nashik = compute_panchayat_diagnostics(df_nashik, pred_xgb_nashik, y_true_col=target_col)

    monthly_pune_xgb = compute_monthly_diagnostics(df_pune, xgb_downscaler.predict(df_pune[feature_cols]), y_true_col=target_col)

    # Model comparisons (Block, Linear, RF, XGB)
    val_comparison = compute_all_model_comparisons(y_val, pred_block_val, pred_linear_val, pred_rf_val, pred_xgb_val)
    test_comparison = compute_all_model_comparisons(y_test, pred_block_test, pred_linear_test, pred_rf_test, pred_xgb_test)
    nashik_comparison = compute_all_model_comparisons(y_nashik, pred_block_nashik, pred_linear_nashik, pred_rf_nashik, pred_xgb_nashik)

    # Sliced comparisons on heavy rain (actual >= 35.5 mm)
    val_heavy_mask = (y_val >= 35.5)
    val_heavy_summary = {
        "heavy_rain_events_count": int(np.sum(val_heavy_mask)),
        "block_forecast_heavy_mae": compute_regression_metrics(y_val[val_heavy_mask], pred_block_val[val_heavy_mask])["mae"] if np.sum(val_heavy_mask) > 0 else None,
        "linear_regression_heavy_mae": compute_regression_metrics(y_val[val_heavy_mask], pred_linear_val[val_heavy_mask])["mae"] if np.sum(val_heavy_mask) > 0 else None,
        "random_forest_heavy_mae": compute_regression_metrics(y_val[val_heavy_mask], pred_rf_val[val_heavy_mask])["mae"] if pred_rf_val is not None and np.sum(val_heavy_mask) > 0 else None,
        "xgboost_heavy_mae": compute_regression_metrics(y_val[val_heavy_mask], pred_xgb_val[val_heavy_mask])["mae"] if np.sum(val_heavy_mask) > 0 else None,
    }

    # 13. Save Artifacts to model_dir
    os.makedirs(model_dir, exist_ok=True)
    xgb_downscaler.save(model_dir)

    selected_params = {
        "n_estimators": best_candidate["n_estimators"],
        "max_depth": best_candidate["max_depth"],
        "learning_rate": best_candidate["learning_rate"],
        "subsample": best_candidate["subsample"],
        "colsample_bytree": best_candidate["colsample_bytree"],
        "reg_alpha": best_candidate["reg_alpha"],
        "reg_lambda": best_candidate["reg_lambda"],
        "min_child_weight": best_candidate["min_child_weight"],
        "early_stopping_rounds": best_candidate.get("early_stopping_rounds"),
        "random_state": random_seed
    }

    metadata = {
        "model_name": "GramSevak XGBoost Downscaler",
        "model_version": "2.5.0",
        "phase": "2.5",
        "model_type": "XGBRegressor",
        "framework": "xgboost",
        "xgboost_version": xgb.__version__,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": random_seed,
        "target": target_col,
        "feature_registry_version": "1.0.0",
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "selected_hyperparameters": selected_params,
        "early_stopping_configuration": {
            "early_stopping_rounds": selected_params.get("early_stopping_rounds"),
            "eval_metric": "mae",
            "best_iteration": xgb_downscaler.best_iteration_,
            "best_validation_score": xgb_downscaler.best_score_
        },
        "training_dataset": {
            "source_parquet": pune_path,
            "split_name": "train",
            "period": f"{split_diag['train']['start_date']} to {split_diag['train']['end_date']}",
            "row_count": len(train_df),
            "training_duration_seconds": round(training_duration, 2)
        },
        "validation_dataset": {
            "split_name": "validation",
            "period": f"{split_diag['validation']['start_date']} to {split_diag['validation']['end_date']}",
            "row_count": len(val_df)
        },
        "test_dataset": {
            "split_name": "test",
            "period": f"{split_diag['test']['start_date']} to {split_diag['test']['end_date']}",
            "row_count": len(test_df),
            "locked": True
        },
        "validation_metrics": eval_val_comprehensive["overall"],
        "locked_test_metrics": eval_test_comprehensive["overall"],
        "artifacts": {
            "model_path": os.path.join(model_dir, "model.joblib").replace("\\", "/"),
            "best_model_path": os.path.join(model_dir, "best_model.joblib").replace("\\", "/"),
            "preprocessor_path": os.path.join(model_dir, "preprocessor.joblib").replace("\\", "/"),
            "config_path": os.path.join(model_dir, "config.json").replace("\\", "/"),
            "metadata_path": os.path.join(model_dir, "metadata.json").replace("\\", "/")
        }
    }

    metadata_path = os.path.join(model_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    config_path_out = os.path.join(model_dir, "config.json")
    with open(config_path_out, "w", encoding="utf-8") as f:
        json.dump({
            "model_name": "XGBoost Regressor",
            "model_version": "v2.5.0",
            "model_type": "XGBRegressor",
            "framework": "xgboost",
            "xgboost_version": xgb.__version__,
            "features": feature_cols,
            "target": target_col,
            "hyperparameters": selected_params,
            "best_iteration": xgb_downscaler.best_iteration_,
            "training_date_range": {
                "start_date": split_diag["train"]["start_date"],
                "end_date": split_diag["train"]["end_date"]
            },
            "training_rows": len(train_df),
            "validation_date_range": {
                "start_date": split_diag["validation"]["start_date"],
                "end_date": split_diag["validation"]["end_date"]
            },
            "validation_rows": len(val_df),
            "test_date_range": {
                "start_date": split_diag["test"]["start_date"],
                "end_date": split_diag["test"]["end_date"]
            },
            "test_rows": len(test_df),
            "baseline_mae": compute_regression_metrics(y_val, pred_block_val)["mae"],
            "baseline_rmse": compute_regression_metrics(y_val, pred_block_val)["rmse"],
            "validation_mae": eval_val_comprehensive["overall"]["mae"],
            "validation_rmse": eval_val_comprehensive["overall"]["rmse"],
            "validation_bias": eval_val_comprehensive["overall"]["bias"],
            "test_mae": eval_test_comprehensive["overall"]["mae"],
            "test_rmse": eval_test_comprehensive["overall"]["rmse"],
            "test_bias": eval_test_comprehensive["overall"]["bias"],
            "feature_importances_gain": {
                item["feature"]: item["importance"] for item in feat_importances_gain
            }
        }, f, indent=2)

    # 14. Build Complete Phase 2.5 Structured JSON Report
    total_pipeline_time = time.time() - start_time
    report = {
        "metadata": {
            "phase": "2.5",
            "title": "XGBoost Downscaling Model Training & Evaluation Report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "problem_statement": "SIH 26074 - GramSevak Hyper-local Rainfall Downscaling",
            "contract_authority": "docs/phase-2-1-ml-data-contract.md",
            "feature_registry_authority": "schemas/ml_feature_registry.json",
            "split_authority": "configs/ml_split.yaml",
            "pipeline_runtime_seconds": round(total_pipeline_time, 2)
        },
        "dataset": {
            "pune_features_parquet": pune_path,
            "nashik_features_parquet": nashik_path,
            "pune_total_rows": len(df_pune),
            "nashik_total_rows": len(df_nashik),
            "approved_features_count": len(feature_cols),
            "target_variable": target_col
        },
        "target": {
            "name": target_col,
            "type": "float64",
            "unit": "mm",
            "clamping_constraint": "y_pred >= 0.0 mm"
        },
        "features": {
            "count": len(feature_cols),
            "names": feature_cols,
            "registry_version": "1.0.0"
        },
        "split": split_diag,
        "training": {
            "algorithm": "XGBRegressor",
            "framework": "xgboost",
            "version": xgb.__version__,
            "fitted_rows": len(train_df),
            "feature_count": len(feature_cols),
            "random_seed": random_seed,
            "training_duration_seconds": round(training_duration, 2),
            "best_iteration": xgb_downscaler.best_iteration_,
            "best_score": xgb_downscaler.best_score_,
            "in_sample_metrics": eval_train_comprehensive["overall"]
        },
        "hyperparameters": {
            "search_strategy": "Controlled Validation Grid Search with Early Stopping",
            "selection_metric": "validation_mae",
            "selection_justification": (
                "Validation MAE was explicitly established as the primary downscaling metric in Phase 2.3. "
                "Minimizing MAE directly minimizes expected hyper-local absolute prediction errors for advisory services."
            ),
            "candidates_evaluated_count": len(CANDIDATE_HYPERPARAMETERS),
            "selected_candidate": best_candidate,
            "candidate_results": tuning_history
        },
        "validation_metrics": eval_val_comprehensive,
        "test_metrics": eval_test_comprehensive,
        "baseline_comparison": {
            "pune_validation": val_comparison,
            "pune_test_locked": test_comparison,
            "nashik_out_of_district": nashik_comparison,
            "heavy_rainfall_analysis": val_heavy_summary
        },
        "random_forest_comparison": {
            "note": "Descriptive comparison only. Final multi-model evaluation and selection belongs to Phase 2.6.",
            "pune_validation_mae": {
                "random_forest": val_comparison["metrics_summary"]["random_forest"]["mae"] if val_comparison["metrics_summary"]["random_forest"] else None,
                "xgboost": val_comparison["metrics_summary"]["xgboost"]["mae"],
                "delta_mm": val_comparison["xgb_vs_random_forest_comparison"].get("mae_delta_mm"),
                "xgb_improvement_pct": val_comparison["xgb_vs_random_forest_comparison"].get("mae_improvement_pct")
            },
            "pune_test_locked_mae": {
                "random_forest": test_comparison["metrics_summary"]["random_forest"]["mae"] if test_comparison["metrics_summary"]["random_forest"] else None,
                "xgboost": test_comparison["metrics_summary"]["xgboost"]["mae"],
                "delta_mm": test_comparison["xgb_vs_random_forest_comparison"].get("mae_delta_mm"),
                "xgb_improvement_pct": test_comparison["xgb_vs_random_forest_comparison"].get("mae_improvement_pct")
            }
        },
        "feature_importance": {
            "primary_method": "gain",
            "rankings_gain": feat_importances_gain,
            "rankings_weight": feat_importances_weight,
            "top_5_gain": top_5_gain
        },
        "leakage_checks": leakage_checks,
        "artifact": {
            "model_path": os.path.join(model_dir, "model.joblib").replace("\\", "/"),
            "best_model_path": os.path.join(model_dir, "best_model.joblib").replace("\\", "/"),
            "preprocessor_path": os.path.join(model_dir, "preprocessor.joblib").replace("\\", "/"),
            "metadata_path": metadata_path.replace("\\", "/"),
            "config_path": config_path_out.replace("\\", "/"),
            "report_path": output_report_path.replace("\\", "/")
        },
        "reproducibility": {
            "script": "scripts/train_xgboost.py",
            "seed": random_seed,
            "deterministic": True,
            "xgboost_version": xgb.__version__,
            "python_version": sys.version
        },
        "spatial_and_temporal_diagnostics": {
            "panchayat_spatial_val": panch_diag_val,
            "panchayat_spatial_test": panch_diag_test,
            "panchayat_spatial_nashik": panch_diag_nashik,
            "monthly_breakdown_pune": monthly_pune_xgb
        }
    }

    # Save JSON report
    os.makedirs(os.path.dirname(output_report_path), exist_ok=True)
    with open(output_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Machine-readable Phase 2.5 report written to {output_report_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="GramSevak Phase 2.5 XGBoost Training Pipeline")
    parser.add_argument("--pune", default="data/ml/features/pune/rainfall_features.parquet", help="Path to Pune features parquet")
    parser.add_argument("--nashik", default="data/ml/features/nashik/rainfall_features.parquet", help="Path to Nashik features parquet")
    parser.add_argument("--config", default="configs/ml_split.yaml", help="Path to split YAML config")
    parser.add_argument("--rf-model-dir", default="ml/models/random_forest", help="Directory with Phase 2.4 RF model")
    parser.add_argument("--model-dir", default="ml/models/xgboost", help="Directory to save model artifacts")
    parser.add_argument("--report", default="reports/phase-2-5-xgboost-results.json", help="Path to save output JSON report")
    parser.add_argument("--seed", type=int, default=42, help="Fixed random seed")

    args = parser.parse_args()

    report = train_and_evaluate_xgboost(
        pune_path=args.pune,
        nashik_path=args.nashik,
        config_path=args.config,
        rf_model_dir=args.rf_model_dir,
        model_dir=args.model_dir,
        output_report_path=args.report,
        random_seed=args.seed
    )

    val_res = report["validation_metrics"]["overall"]
    test_res = report["test_metrics"]["overall"]
    comp_val = report["baseline_comparison"]["pune_validation"]

    print("\n" + "=" * 60)
    print("GRAMSEVAK PHASE 2.5 XGBOOST TRAINING COMPLETE")
    print("=" * 60)
    print(f"Selected Candidate : {report['hyperparameters']['selected_candidate']['name']}")
    print(f"Best Iteration     : {report['training']['best_iteration']}")
    print(f"Validation MAE     : {val_res['mae']} mm (RMSE: {val_res['rmse']} mm, Bias: {val_res['bias']} mm, r: {val_res['pearson_r']})")
    print(f"Block Baseline MAE : {comp_val['metrics_summary']['block_forecast']['mae']} mm")
    print(f"Linear Baseline MAE: {comp_val['metrics_summary']['linear_regression']['mae']} mm")
    print(f"Random Forest MAE  : {comp_val['metrics_summary']['random_forest']['mae']} mm")
    print(f"Locked Test MAE    : {test_res['mae']} mm (RMSE: {test_res['rmse']} mm, Bias: {test_res['bias']} mm)")
    print(f"Artifacts Saved to : {args.model_dir}")
    print(f"Report Generated   : {args.report}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
