"""
GramSevak ML Baseline Evaluation Engine (Phase 2.3).

Evaluates non-ML domain baseline (Raw Block Forecast) and simple statistical baseline
(Regularized Linear Regression) across chronological Train, Validation, and Locked Test sets.

Generates:
- Comprehensive regression metrics (MAE, RMSE, Bias, Correlation, R2)
- Rainfall occurrence classification metrics (rain > 0: Precision, Recall, F1)
- Non-zero and heavy rainfall slice metrics (actual >= 35.5 mm)
- Panchayat-level spatial error distributions
- Monthly seasonal performance diagnostics
- Machine-readable report at reports/phase-2-3-baseline-results.json

Usage:
    python scripts/evaluate_baselines.py
    python scripts/evaluate_baselines.py --pune data/ml/features/pune/rainfall_features.parquet --nashik data/ml/features/nashik/rainfall_features.parquet
"""

import os
import sys
import json
import math
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.create_ml_splits import split_temporal_dataset, load_split_config
from ml.features.engineer import FEATURE_COLUMNS, TARGET_COLUMN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("evaluate_baselines")

# Features selected for simple statistical baseline (interpretable, physical)
BASELINE_MODEL_FEATURES: List[str] = [
    "block_forecast_rainfall_mm",
    "panchayat_latitude",
    "panchayat_longitude",
    "elevation_m",
    "station_distance_km",
    "lead_days",
    "target_day_of_year_sin",
    "target_day_of_year_cos",
    "historical_rainfall_prior_1d_mm",
    "has_historical_rainfall_context"
]


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """Calculate standard regression metrics, bias, correlation, and error quantiles."""
    count = len(y_true)
    if count == 0:
        return {
            "count": 0, "mae": None, "rmse": None, "bias": None,
            "median_abs_error": None, "pearson_r": None, "r2": None,
            "error_quantiles": {}
        }

    errors = y_pred - y_true
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    bias = float(np.mean(errors))
    median_abs_error = float(np.median(abs_errors))

    # Pearson correlation
    if count > 1 and np.std(y_true) > 1e-7 and np.std(y_pred) > 1e-7:
        c = float(np.corrcoef(y_true, y_pred)[0, 1])
        pearson_r = round(c, 4) if not math.isnan(c) else 0.0
    else:
        pearson_r = 0.0

    # R2 score
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot > 1e-7:
        ss_res = np.sum(errors ** 2)
        r2 = round(float(1.0 - (ss_res / ss_tot)), 4)
    else:
        r2 = 0.0

    quantiles = {
        "min": round(float(np.min(errors)), 4),
        "p25": round(float(np.percentile(errors, 25)), 4),
        "p50_median_error": round(float(np.median(errors)), 4),
        "p75": round(float(np.percentile(errors, 75)), 4),
        "p90": round(float(np.percentile(errors, 90)), 4),
        "max": round(float(np.max(errors)), 4)
    }

    return {
        "count": count,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "bias": round(bias, 4),
        "median_abs_error": round(median_abs_error, 4),
        "pearson_r": pearson_r,
        "r2": r2,
        "error_quantiles": quantiles
    }


def compute_occurrence_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    threshold: float = 0.001
) -> Dict[str, Any]:
    """Calculate rain occurrence (rain > threshold) classification metrics."""
    true_bin = (y_true > threshold).astype(int)
    pred_bin = (y_pred > threshold).astype(int)

    tp = int(np.sum((true_bin == 1) & (pred_bin == 1)))
    fp = int(np.sum((true_bin == 0) & (pred_bin == 1)))
    fn = int(np.sum((true_bin == 1) & (pred_bin == 0)))
    tn = int(np.sum((true_bin == 0) & (pred_bin == 0)))

    precision = round(float(tp / (tp + fp)), 4) if (tp + fp) > 0 else 0.0
    recall = round(float(tp / (tp + fn)), 4) if (tp + fn) > 0 else 0.0
    f1 = round(float(2 * precision * recall / (precision + recall)), 4) if (precision + recall) > 0 else 0.0
    accuracy = round(float((tp + tn) / len(y_true)), 4) if len(y_true) > 0 else 0.0

    return {
        "threshold_mm": threshold,
        "true_rain_events": int(np.sum(true_bin)),
        "predicted_rain_events": int(np.sum(pred_bin)),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


def compute_comprehensive_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """Compute overall regression, occurrence, and sliced metrics across rainfall intensities."""
    overall = compute_regression_metrics(y_true, y_pred)
    occurrence = compute_occurrence_metrics(y_true, y_pred, threshold=0.001)

    # Slices
    zero_mask = (y_true == 0.0)
    nonzero_mask = (y_true > 0.0)
    moderate_mask = (y_true >= 15.5)
    heavy_mask = (y_true >= 35.5)
    vheavy_mask = (y_true >= 64.5)

    return {
        "overall": overall,
        "occurrence": occurrence,
        "zero_rainfall_slice": compute_regression_metrics(y_true[zero_mask], y_pred[zero_mask]),
        "nonzero_rainfall_slice": compute_regression_metrics(y_true[nonzero_mask], y_pred[nonzero_mask]),
        "moderate_plus_slice_gte_15_5mm": compute_regression_metrics(y_true[moderate_mask], y_pred[moderate_mask]),
        "heavy_slice_gte_35_5mm": compute_regression_metrics(y_true[heavy_mask], y_pred[heavy_mask]),
        "very_heavy_slice_gte_64_5mm": compute_regression_metrics(y_true[vheavy_mask], y_pred[vheavy_mask])
    }


def compute_panchayat_diagnostics(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    y_true_col: str = TARGET_COLUMN
) -> Dict[str, Any]:
    """Calculate spatial error distribution across Panchayats."""
    temp_df = df[["panchayat_id"]].copy()
    temp_df["abs_error"] = np.abs(df[y_true_col].values - y_pred)

    panch_mae = temp_df.groupby("panchayat_id")["abs_error"].mean()
    vals = panch_mae.values

    return {
        "panchayats_evaluated": int(len(panch_mae)),
        "min_mae": round(float(np.min(vals)), 4),
        "p25_mae": round(float(np.percentile(vals, 25)), 4),
        "median_mae": round(float(np.median(vals)), 4),
        "p75_mae": round(float(np.percentile(vals, 75)), 4),
        "max_mae": round(float(np.max(vals)), 4),
        "mean_mae": round(float(np.mean(vals)), 4),
        "std_mae": round(float(np.std(vals)), 4)
    }


def compute_monthly_diagnostics(
    df: pd.DataFrame,
    y_pred: np.ndarray,
    y_true_col: str = TARGET_COLUMN
) -> Dict[str, Any]:
    """Calculate performance metrics broken down by target month."""
    temp_df = df[["target_month"]].copy()
    temp_df["y_true"] = df[y_true_col].values
    temp_df["y_pred"] = y_pred

    monthly_results = {}
    for m in sorted(temp_df["target_month"].unique()):
        sub = temp_df[temp_df["target_month"] == m]
        sub_true = sub["y_true"].values
        sub_pred = sub["y_pred"].values
        monthly_results[str(m)] = compute_regression_metrics(sub_true, sub_pred)

    return monthly_results


class SimpleLinearBaseline:
    """
    Transparent regularized linear statistical baseline.
    Standardizes features and trains Ridge(alpha=1.0) strictly on Train split.
    Applies non-negative clip on predictions (precipitation >= 0.0 mm).
    """
    def __init__(self, feature_columns: List[str] = BASELINE_MODEL_FEATURES, alpha: float = 1.0, random_seed: int = 42):
        self.feature_columns = feature_columns
        self.alpha = alpha
        self.random_seed = random_seed
        self.pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("regressor", Ridge(alpha=self.alpha, random_state=self.random_seed))
        ])
        self.is_fitted = False
        self.coefficients_: Dict[str, float] = {}
        self.intercept_: float = 0.0

    def fit(self, train_df: pd.DataFrame, target_col: str = TARGET_COLUMN) -> "SimpleLinearBaseline":
        logger.info(f"Fitting SimpleLinearBaseline on {len(train_df)} training rows with {len(self.feature_columns)} features...")
        X_train = train_df[self.feature_columns].copy()
        y_train = train_df[target_col].values.astype(float)

        self.pipeline.fit(X_train, y_train)
        self.is_fitted = True

        reg = self.pipeline.named_steps["regressor"]
        self.intercept_ = round(float(reg.intercept_), 6)
        self.coefficients_ = {
            col: round(float(coef), 6)
            for col, coef in zip(self.feature_columns, reg.coef_)
        }
        logger.info(f"Fitted Ridge baseline. Intercept: {self.intercept_}, Top coefs: {self.coefficients_}")
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict.")
        X = df[self.feature_columns].copy()
        raw_pred = self.pipeline.predict(X)
        # Precipitation cannot be physically negative
        return np.clip(raw_pred, 0.0, None)


def evaluate_all_baselines(
    pune_path: str,
    nashik_path: str,
    config_path: str,
    output_report_path: str
) -> Dict[str, Any]:
    """Execute complete temporal split, baseline model training, and comprehensive evaluation."""
    logger.info("Starting GramSevak Phase 2.3 Baseline Evaluation Framework...")

    # Load datasets
    df_pune = pd.read_parquet(pune_path)
    df_nashik = pd.read_parquet(nashik_path)
    cfg = load_split_config(config_path)

    # 1. Chronological split on Pune
    train_df, val_df, test_df, split_diag = split_temporal_dataset(df_pune, cfg)

    # 2. Train Simple Linear Baseline strictly on Train split
    linear_baseline = SimpleLinearBaseline()
    linear_baseline.fit(train_df, TARGET_COLUMN)

    # 3. Generate predictions for both baselines across all splits
    # A. Pune Train
    y_true_pune_train = train_df[TARGET_COLUMN].values.astype(float)
    pred_block_pune_train = train_df["block_forecast_rainfall_mm"].values.astype(float)
    pred_linear_pune_train = linear_baseline.predict(train_df)

    # B. Pune Validation
    y_true_pune_val = val_df[TARGET_COLUMN].values.astype(float)
    pred_block_pune_val = val_df["block_forecast_rainfall_mm"].values.astype(float)
    pred_linear_pune_val = linear_baseline.predict(val_df)

    # C. Pune Test (LOCKED)
    y_true_pune_test = test_df[TARGET_COLUMN].values.astype(float)
    pred_block_pune_test = test_df["block_forecast_rainfall_mm"].values.astype(float)
    pred_linear_pune_test = linear_baseline.predict(test_df)

    # D. Nashik Snapshot (Out-of-District Transferability)
    y_true_nashik = df_nashik[TARGET_COLUMN].values.astype(float)
    pred_block_nashik = df_nashik["block_forecast_rainfall_mm"].values.astype(float)
    pred_linear_nashik = linear_baseline.predict(df_nashik)

    # 4. Compute comprehensive evaluation metrics
    results = {
        "metadata": {
            "phase": "2.3",
            "title": "ML Baseline Evaluation Report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "problem_statement": "SIH 26074 - GramSevak Hyper-local Rainfall Downscaling",
            "contract_authority": "docs/phase-2-1-ml-data-contract.md"
        },
        "split_summary": split_diag,
        "models": {
            "block_forecast_baseline": {
                "id": "block_forecast",
                "name": "Raw Numerical Block Forecast Baseline",
                "formula": "y_pred = block_forecast_rainfall_mm",
                "description": "Uncalibrated regional NWP forecast issued by IMD/NCMRWF at ~20km block scale."
            },
            "linear_regression_baseline": {
                "id": "linear_regression",
                "name": "Simple Linear Regression Baseline",
                "formula": "y_pred = max(0, w^T X + b)",
                "algorithm": "Ridge(alpha=1.0)",
                "features_used": BASELINE_MODEL_FEATURES,
                "learned_intercept": linear_baseline.intercept_,
                "learned_coefficients": linear_baseline.coefficients_
            }
        },
        "evaluations": {
            "pune_validation": {
                "period": f"{split_diag['validation']['start_date']} to {split_diag['validation']['end_date']}",
                "rows_count": len(val_df),
                "block_forecast": compute_comprehensive_metrics(y_true_pune_val, pred_block_pune_val),
                "linear_regression": compute_comprehensive_metrics(y_true_pune_val, pred_linear_pune_val),
                "panchayat_diagnostics": {
                    "block_forecast": compute_panchayat_diagnostics(val_df, pred_block_pune_val),
                    "linear_regression": compute_panchayat_diagnostics(val_df, pred_linear_pune_val)
                }
            },
            "pune_test_locked": {
                "period": f"{split_diag['test']['start_date']} to {split_diag['test']['end_date']}",
                "rows_count": len(test_df),
                "status": "LOCKED TEST EVALUATION",
                "block_forecast": compute_comprehensive_metrics(y_true_pune_test, pred_block_pune_test),
                "linear_regression": compute_comprehensive_metrics(y_true_pune_test, pred_linear_pune_test),
                "panchayat_diagnostics": {
                    "block_forecast": compute_panchayat_diagnostics(test_df, pred_block_pune_test),
                    "linear_regression": compute_panchayat_diagnostics(test_df, pred_linear_pune_test)
                }
            },
            "pune_train_in_sample": {
                "period": f"{split_diag['train']['start_date']} to {split_diag['train']['end_date']}",
                "rows_count": len(train_df),
                "block_forecast": compute_comprehensive_metrics(y_true_pune_train, pred_block_pune_train),
                "linear_regression": compute_comprehensive_metrics(y_true_pune_train, pred_linear_pune_train)
            },
            "nashik_out_of_district_transferability": {
                "period": f"{df_nashik['date'].min()} to {df_nashik['date'].max()}",
                "rows_count": len(df_nashik),
                "structure": "Single-observation spatial snapshot (1,388 Panchayats)",
                "block_forecast": compute_comprehensive_metrics(y_true_nashik, pred_block_nashik),
                "linear_regression": compute_comprehensive_metrics(y_true_nashik, pred_linear_nashik),
                "panchayat_diagnostics": {
                    "block_forecast": compute_panchayat_diagnostics(df_nashik, pred_block_nashik),
                    "linear_regression": compute_panchayat_diagnostics(df_nashik, pred_linear_nashik)
                }
            }
        },
        "monthly_breakdown_pune": {
            "block_forecast": compute_monthly_diagnostics(df_pune, df_pune["block_forecast_rainfall_mm"].values.astype(float)),
            "linear_regression": compute_monthly_diagnostics(df_pune, linear_baseline.predict(df_pune))
        }
    }

    # Save machine-readable report
    os.makedirs(os.path.dirname(output_report_path), exist_ok=True)
    with open(output_report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Machine-readable baseline results written to: {output_report_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="GramSevak ML Baseline Evaluation Framework (Phase 2.3)")
    parser.add_argument("--pune", default="data/ml/features/pune/rainfall_features.parquet", help="Path to Pune features Parquet")
    parser.add_argument("--nashik", default="data/ml/features/nashik/rainfall_features.parquet", help="Path to Nashik features Parquet")
    parser.add_argument("--config", default="configs/ml_split.yaml", help="Path to split configuration YAML")
    parser.add_argument("--output-report", default="reports/phase-2-3-baseline-results.json", help="Path to output results JSON report")
    args = parser.parse_args()

    results = evaluate_all_baselines(args.pune, args.nashik, args.config, args.output_report)
    val_bf = results["evaluations"]["pune_validation"]["block_forecast"]["overall"]
    val_lr = results["evaluations"]["pune_validation"]["linear_regression"]["overall"]
    test_bf = results["evaluations"]["pune_test_locked"]["block_forecast"]["overall"]
    test_lr = results["evaluations"]["pune_test_locked"]["linear_regression"]["overall"]

    print("\n" + "=" * 90)
    print("GRAMSEVAK PHASE 2.3 — ML BASELINE EVALUATION BENCHMARK")
    print("=" * 90)
    print(f"{'Split / Metric':<25} | {'Block Forecast Baseline':<30} | {'Simple Linear Regression':<30}")
    print("-" * 90)
    print(f"{'Val MAE (August)':<25} | {val_bf['mae']:>8.4f} mm                     | {val_lr['mae']:>8.4f} mm")
    print(f"{'Val RMSE (August)':<25} | {val_bf['rmse']:>8.4f} mm                     | {val_lr['rmse']:>8.4f} mm")
    print(f"{'Val Bias (August)':<25} | {val_bf['bias']:>8.4f} mm                     | {val_lr['bias']:>8.4f} mm")
    print(f"{'Val Pearson r':<25} | {val_bf['pearson_r']:>8.4f}                        | {val_lr['pearson_r']:>8.4f}")
    print("-" * 90)
    print(f"{'Test MAE (September)':<25} | {test_bf['mae']:>8.4f} mm                     | {test_lr['mae']:>8.4f} mm")
    print(f"{'Test RMSE (September)':<25} | {test_bf['rmse']:>8.4f} mm                     | {test_lr['rmse']:>8.4f} mm")
    print(f"{'Test Bias (September)':<25} | {test_bf['bias']:>8.4f} mm                     | {test_lr['bias']:>8.4f} mm")
    print(f"{'Test Pearson r':<25} | {test_bf['pearson_r']:>8.4f}                        | {test_lr['pearson_r']:>8.4f}")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
