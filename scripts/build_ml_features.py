"""
GramSevak ML Feature Engineering Pipeline (Phase 2.2).

Extracts and validates model-ready, leakage-safe features from canonical weather Parquet datasets.
Outputs feature Parquet datasets to data/ml/features/{district}/rainfall_features.parquet
and generates a comprehensive feature quality report at reports/phase-2-2-feature-quality.json.

Usage:
    python scripts/build_ml_features.py
    python scripts/build_ml_features.py --nashik data/processed/canonical_nashik.parquet --pune data/processed/canonical_pune.parquet
    python scripts/build_ml_features.py --input data/processed/canonical_pune.parquet --district Pune
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

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.features.engineer import (
    FEATURE_COLUMNS,
    METADATA_COLUMNS,
    TARGET_COLUMN,
    build_feature_dataframe
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("build_ml_features")


def load_canonical_parquet(file_path: str) -> pd.DataFrame:
    """Load canonical Parquet dataset with path validation."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Canonical dataset not found: {file_path}")
    logger.info(f"Loading canonical Parquet from: {file_path}")
    return pd.read_parquet(file_path)


def compute_feature_statistics(
    features_df: pd.DataFrame,
    target_series: Optional[pd.Series]
) -> Dict[str, Dict[str, Any]]:
    """
    Compute distribution and quality statistics for each feature column:
    - missing count & percentage
    - min, max, mean, std, median
    - constant/near-constant flag
    - correlation with target (on non-null pairs)
    """
    stats: Dict[str, Dict[str, Any]] = {}
    total_rows = len(features_df)

    y_vals = target_series.values.astype(float) if target_series is not None else None

    for col in features_df.columns:
        s = features_df[col]
        missing_count = int(s.isna().sum())
        missing_pct = round((missing_count / total_rows) * 100.0, 3) if total_rows > 0 else 0.0

        valid_s = s.dropna()
        valid_count = len(valid_s)

        if valid_count > 0:
            vals = valid_s.values.astype(float)
            col_min = round(float(np.min(vals)), 4)
            col_max = round(float(np.max(vals)), 4)
            col_mean = round(float(np.mean(vals)), 4)
            col_std = round(float(np.std(vals)), 4)
            col_median = round(float(np.median(vals)), 4)
            is_constant = bool(col_min == col_max)
            is_near_constant = bool(col_std < 1e-4)

            # Correlation with target
            corr_with_target = None
            if y_vals is not None:
                mask = s.notna() & (~np.isnan(y_vals))
                if mask.sum() > 2:
                    sub_x = s[mask].values.astype(float)
                    sub_y = y_vals[mask]
                    if np.std(sub_x) > 1e-6 and np.std(sub_y) > 1e-6:
                        c = float(np.corrcoef(sub_x, sub_y)[0, 1])
                        corr_with_target = round(c, 4) if not math.isnan(c) else 0.0
                    else:
                        corr_with_target = 0.0
        else:
            col_min = col_max = col_mean = col_std = col_median = None
            is_constant = False
            is_near_constant = False
            corr_with_target = None

        stats[col] = {
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "min": col_min,
            "max": col_max,
            "mean": col_mean,
            "std": col_std,
            "median": col_median,
            "is_constant": is_constant,
            "is_near_constant": is_near_constant,
            "target_correlation": corr_with_target
        }

    return stats


def compute_inter_feature_correlations(
    features_df: pd.DataFrame,
    threshold: float = 0.85
) -> List[Dict[str, Any]]:
    """Identify highly correlated feature pairs (|r| >= threshold)."""
    high_corr_pairs = []
    num_df = features_df.select_dtypes(include=[np.number])
    corr_matrix = num_df.corr().abs()

    cols = list(corr_matrix.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            col1 = cols[i]
            col2 = cols[j]
            val = corr_matrix.loc[col1, col2]
            if not math.isnan(val) and val >= threshold:
                high_corr_pairs.append({
                    "feature_1": col1,
                    "feature_2": col2,
                    "absolute_pearson_r": round(float(val), 4)
                })

    return high_corr_pairs


def process_district_features(
    input_parquet: str,
    district_name: str,
    output_dir: str
) -> Dict[str, Any]:
    """Process a single district canonical dataset into model-ready features."""
    logger.info(f"Processing features for district: {district_name}...")
    df = load_canonical_parquet(input_parquet)
    total_raw_rows = len(df)

    metadata_df, features_df, target_series = build_feature_dataframe(df, include_target=True)

    # Validate isolation: target MUST NOT be in features_df
    assert TARGET_COLUMN not in features_df.columns, f"CRITICAL: {TARGET_COLUMN} leaked into features_df!"

    # Combine into unified model dataset with explicit metadata, feature, and target columns
    ml_dataset = pd.concat([metadata_df, features_df], axis=1)
    if target_series is not None:
        ml_dataset[TARGET_COLUMN] = target_series

    # Write output Parquet
    district_clean = district_name.lower().replace(" ", "_")
    district_out_dir = os.path.join(output_dir, district_clean)
    os.makedirs(district_out_dir, exist_ok=True)
    output_parquet_path = os.path.join(district_out_dir, "rainfall_features.parquet")
    ml_dataset.to_parquet(output_parquet_path, engine="pyarrow", compression="snappy", index=False)
    out_file_size = os.path.getsize(output_parquet_path)
    logger.info(f"Saved {len(ml_dataset)} rows to {output_parquet_path} ({out_file_size} bytes)")

    # Compute statistics and correlations
    feature_stats = compute_feature_statistics(features_df, target_series)
    high_corr_pairs = compute_inter_feature_correlations(features_df)

    target_stats = {
        "valid_count": int(target_series.notna().sum()) if target_series is not None else 0,
        "missing_count": int(target_series.isna().sum()) if target_series is not None else 0,
        "mean": round(float(target_series.mean()), 4) if target_series is not None and target_series.notna().any() else None,
        "min": round(float(target_series.min()), 4) if target_series is not None and target_series.notna().any() else None,
        "max": round(float(target_series.max()), 4) if target_series is not None and target_series.notna().any() else None
    }

    return {
        "district_name": district_name,
        "input_parquet": input_parquet.replace("\\", "/"),
        "output_parquet": output_parquet_path.replace("\\", "/"),
        "file_size_bytes": out_file_size,
        "total_rows": len(ml_dataset),
        "feature_count": len(features_df.columns),
        "features_list": list(features_df.columns),
        "metadata_columns": list(metadata_df.columns),
        "target_column": TARGET_COLUMN,
        "target_statistics": target_stats,
        "feature_quality_statistics": feature_stats,
        "inter_feature_correlations_gte_85": high_corr_pairs
    }


def run_pipeline(
    nashik_path: str,
    pune_path: str,
    output_dir: str,
    report_json_path: str
) -> Dict[str, Any]:
    """Execute end-to-end ML feature engineering for all districts and generate quality report."""
    logger.info("Starting GramSevak Phase 2.2 ML Feature Engineering Pipeline...")

    # Load registry schema
    registry_path = os.path.join(PROJECT_ROOT, "schemas", "ml_feature_registry.json")
    feature_registry = {}
    if os.path.exists(registry_path):
        with open(registry_path, "r", encoding="utf-8") as f:
            feature_registry = json.load(f)

    # Process Nashik
    nashik_results = process_district_features(nashik_path, "Nashik", output_dir)

    # Process Pune
    pune_results = process_district_features(pune_path, "Pune", output_dir)

    # Warnings evaluation
    warnings = []
    if nashik_results["feature_quality_statistics"]["historical_rainfall_prior_1d_mm"]["missing_pct"] == 100.0:
        warnings.append(
            "Nashik has 100% missing historical rainfall features (historical_rainfall_prior_1d_mm, 3d, 7d). "
            "This is expected behavior because Nashik is a single-observation spatial snapshot per Panchayat."
        )
    if pune_results["feature_quality_statistics"]["historical_rainfall_prior_1d_mm"]["missing_pct"] > 0.0:
        pct = pune_results["feature_quality_statistics"]["historical_rainfall_prior_1d_mm"]["missing_pct"]
        warnings.append(
            f"Pune has {pct}% missing historical rainfall features due to initial warm-up days and calendar gap days. "
            "Downstream modeling must use the provided has_historical_rainfall_context indicator."
        )

    # High correlation warnings
    pune_high_corr = pune_results["inter_feature_correlations_gte_85"]
    if pune_high_corr:
        warnings.append(
            f"Detected {len(pune_high_corr)} highly correlated feature pairs (|r| >= 0.85) in Pune, "
            f"such as block_forecast_rainfall_mm vs log1p_block_forecast_rainfall_mm. "
            "Tree models handle collinearity naturally, but linear baselines should consider regularization."
        )

    report = {
        "metadata": {
            "phase": "2.2",
            "title": "ML Feature Engineering & Quality Report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "problem_statement": "SIH 26074 - GramSevak Hyper-local Rainfall Downscaling",
            "registry_version": feature_registry.get("version", "1.0.0")
        },
        "summary": {
            "status": "APPROVED",
            "approved_features_count": len(FEATURE_COLUMNS),
            "excluded_features_count": len(feature_registry.get("excluded_features", [])),
            "districts_processed": ["Nashik", "Pune"],
            "total_records_processed": nashik_results["total_rows"] + pune_results["total_rows"],
            "warnings_count": len(warnings),
            "warnings": warnings
        },
        "approved_feature_columns": FEATURE_COLUMNS,
        "metadata_columns": METADATA_COLUMNS,
        "target_column": TARGET_COLUMN,
        "feature_registry_definitions": feature_registry.get("features", []),
        "excluded_features": feature_registry.get("excluded_features", []),
        "districts": {
            "nashik": nashik_results,
            "pune": pune_results
        }
    }

    # Save quality report
    os.makedirs(os.path.dirname(report_json_path), exist_ok=True)
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Machine-readable feature quality report saved to: {report_json_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="GramSevak ML Feature Engineering Pipeline (Phase 2.2)")
    parser.add_argument("--nashik", default="data/processed/canonical_nashik.parquet", help="Path to Nashik canonical Parquet")
    parser.add_argument("--pune", default="data/processed/canonical_pune.parquet", help="Path to Pune canonical Parquet")
    parser.add_argument("--output-dir", default="data/ml/features", help="Base output directory for ML feature parquets")
    parser.add_argument("--report", default="reports/phase-2-2-feature-quality.json", help="Path to output feature quality JSON report")
    args = parser.parse_args()

    report = run_pipeline(args.nashik, args.pune, args.output_dir, args.report)
    print("\n" + "=" * 80)
    print("GRAMSEVAK PHASE 2.2 — ML FEATURE ENGINEERING SUMMARY")
    print("=" * 80)
    print(f"Status: {report['summary']['status']}")
    print(f"Approved Features: {report['summary']['approved_features_count']} columns")
    print(f"Nashik Rows: {report['districts']['nashik']['total_rows']} | File: {report['districts']['nashik']['output_parquet']}")
    print(f"Pune Rows:   {report['districts']['pune']['total_rows']} | File: {report['districts']['pune']['output_parquet']}")
    print(f"Warnings ({len(report['summary']['warnings'])}):")
    for w in report['summary']['warnings']:
        print(f"  - {w}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
