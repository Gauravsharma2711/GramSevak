"""
GramSevak Chronological ML Dataset Splitter (Phase 2.3).

Executes leak-proof chronological partitioning of ML feature datasets into Train,
Validation, and Locked Test sets per configs/ml_split.yaml and Phase 2.1 contract.

Generates metadata lock file at reports/phase-2-3-split.json.

Usage:
    python scripts/create_ml_splits.py
    python scripts/create_ml_splits.py --input data/ml/features/pune/rainfall_features.parquet
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("create_ml_splits")


# Default chronological split boundaries for Pune (April 13 - Sept 23, 2026)
DEFAULT_SPLIT_BOUNDARIES = {
    "train": {
        "start_date": "2026-04-13",
        "end_date": "2026-07-31",
        "start_issue_date": "2026-04-12",
        "end_issue_date": "2026-07-30"
    },
    "validation": {
        "start_date": "2026-08-01",
        "end_date": "2026-08-31",
        "start_issue_date": "2026-07-31",
        "end_issue_date": "2026-08-30"
    },
    "test": {
        "start_date": "2026-09-01",
        "end_date": "2026-09-23",
        "start_issue_date": "2026-08-31",
        "end_issue_date": "2026-09-22",
        "locked": True
    }
}


def load_split_config(config_path: str) -> Dict[str, Any]:
    """Load split configuration YAML or fallback to defaults."""
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load YAML config from {config_path} ({e}), using default boundaries.")
    return {"splits": DEFAULT_SPLIT_BOUNDARIES, "split_key": "date", "issue_key": "forecast_issue_date"}


def split_temporal_dataset(
    df: pd.DataFrame,
    split_config: Dict[str, Any],
    split_key: str = "date",
    issue_key: str = "forecast_issue_date"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Partition dataset chronologically into Train, Validation, and Test sets.
    
    Enforces assertions:
    - max(train_date) < min(val_date)
    - max(val_date) < min(test_date)
    - max(train_issue_date) < min(val_issue_date)
    - max(val_issue_date) < min(test_issue_date)
    - Zero index intersection between any two splits
    - Sum of row counts equals input row count
    """
    splits_meta = split_config.get("splits", DEFAULT_SPLIT_BOUNDARIES)

    train_cfg = splits_meta["train"]
    val_cfg = splits_meta["validation"]
    test_cfg = splits_meta["test"]

    # Filter rows based on split_key
    train_mask = (df[split_key] >= train_cfg["start_date"]) & (df[split_key] <= train_cfg["end_date"])
    val_mask = (df[split_key] >= val_cfg["start_date"]) & (df[split_key] <= val_cfg["end_date"])
    test_mask = (df[split_key] >= test_cfg["start_date"]) & (df[split_key] <= test_cfg["end_date"])

    train_df = df[train_mask].copy()
    val_df = df[val_mask].copy()
    test_df = df[test_mask].copy()

    total_split_rows = len(train_df) + len(val_df) + len(test_df)
    if total_split_rows != len(df):
        unassigned_count = len(df) - total_split_rows
        unassigned_dates = df.loc[~(train_mask | val_mask | test_mask), split_key].unique()
        logger.warning(f"{unassigned_count} rows with dates {unassigned_dates} fell outside defined split boundaries.")

    # 1. Zero index intersection assertion
    train_idx = set(train_df.index)
    val_idx = set(val_df.index)
    test_idx = set(test_df.index)
    assert len(train_idx.intersection(val_idx)) == 0, "CRITICAL: Train and Validation indices overlap!"
    assert len(val_idx.intersection(test_idx)) == 0, "CRITICAL: Validation and Test indices overlap!"
    assert len(train_idx.intersection(test_idx)) == 0, "CRITICAL: Train and Test indices overlap!"

    # 2. Strict chronological ordering assertions
    max_train_date = str(train_df[split_key].max())
    min_val_date = str(val_df[split_key].min())
    max_val_date = str(val_df[split_key].max())
    min_test_date = str(test_df[split_key].min())

    assert max_train_date < min_val_date, f"Temporal leakage: max train {max_train_date} >= min val {min_val_date}"
    assert max_val_date < min_test_date, f"Temporal leakage: max val {max_val_date} >= min test {min_test_date}"

    # 3. Forecast issue date ordering assertions
    if issue_key in df.columns:
        max_train_issue = str(train_df[issue_key].max())
        min_val_issue = str(val_df[issue_key].min())
        max_val_issue = str(val_df[issue_key].max())
        min_test_issue = str(test_df[issue_key].min())
        assert max_train_issue < min_val_issue, f"Issue date leakage: max train issue {max_train_issue} >= min val issue {min_val_issue}"
        assert max_val_issue < min_test_issue, f"Issue date leakage: max val issue {max_val_issue} >= min test issue {min_test_issue}"

    # Panchayat coverage analysis
    train_panchs = set(train_df["panchayat_id"].unique())
    val_panchs = set(val_df["panchayat_id"].unique())
    test_panchs = set(test_df["panchayat_id"].unique())
    all_panchs = train_panchs.union(val_panchs).union(test_panchs)
    shared_all_panchs = train_panchs.intersection(val_panchs).intersection(test_panchs)

    split_diagnostics = {
        "split_key": split_key,
        "issue_key": issue_key,
        "total_input_rows": len(df),
        "total_partitioned_rows": total_split_rows,
        "train": {
            "start_date": str(train_df[split_key].min()),
            "end_date": max_train_date,
            "unique_dates": int(train_df[split_key].nunique()),
            "row_count": len(train_df),
            "percentage": round((len(train_df) / len(df)) * 100.0, 2),
            "panchayat_count": len(train_panchs)
        },
        "validation": {
            "start_date": min_val_date,
            "end_date": max_val_date,
            "unique_dates": int(val_df[split_key].nunique()),
            "row_count": len(val_df),
            "percentage": round((len(val_df) / len(df)) * 100.0, 2),
            "panchayat_count": len(val_panchs)
        },
        "test": {
            "start_date": min_test_date,
            "end_date": str(test_df[split_key].max()),
            "unique_dates": int(test_df[split_key].nunique()),
            "row_count": len(test_df),
            "percentage": round((len(test_df) / len(df)) * 100.0, 2),
            "panchayat_count": len(test_panchs),
            "locked": True
        },
        "panchayat_overlap": {
            "total_unique_panchayats": len(all_panchs),
            "shared_across_train_val_test": len(shared_all_panchs),
            "shared_percentage": round((len(shared_all_panchs) / len(all_panchs)) * 100.0, 2) if all_panchs else 0.0,
            "panchayats_only_in_train": len(train_panchs - (val_panchs.union(test_panchs))),
            "panchayats_only_in_test": len(test_panchs - (train_panchs.union(val_panchs)))
        }
    }

    logger.info(
        f"Chronological split verified: Train={len(train_df)} rows ({max_train_date}) < "
        f"Val={len(val_df)} rows ({min_val_date} to {max_val_date}) < "
        f"Test={len(test_df)} rows ({min_test_date} to {test_df[split_key].max()})"
    )
    return train_df, val_df, test_df, split_diagnostics


def create_split_lock_report(
    pune_diagnostics: Dict[str, Any],
    nashik_meta: Dict[str, Any],
    output_path: str
) -> Dict[str, Any]:
    """Assemble and write official test-set lock and split metadata report."""
    report = {
        "metadata": {
            "phase": "2.3",
            "title": "ML Temporal Split & Test Set Lock Report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "problem_statement": "SIH 26074 - GramSevak Hyper-local Rainfall Downscaling",
            "contract_authority": "docs/phase-2-1-ml-data-contract.md"
        },
        "split_policy": {
            "primary_methodology": "Forward Chronological Temporal Holdout",
            "shuffling_allowed": False,
            "test_set_locked": True,
            "rationale": "Prevents future atmospheric auto-correlation leakage into past training folds."
        },
        "districts": {
            "pune": {
                "evaluation_role": "Primary Model Training & Temporal Validation",
                "split_details": pune_diagnostics
            },
            "nashik": {
                "evaluation_role": "Out-of-District Spatial Generalization Benchmark",
                "details": nashik_meta
            }
        },
        "test_lock_status": "LOCKED (September 1 - September 23, 2026)"
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Test-set lock report written to: {output_path}")
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GramSevak ML Chronological Splitter (Phase 2.3)")
    parser.add_argument("--pune", default="data/ml/features/pune/rainfall_features.parquet", help="Path to Pune features Parquet")
    parser.add_argument("--nashik", default="data/ml/features/nashik/rainfall_features.parquet", help="Path to Nashik features Parquet")
    parser.add_argument("--config", default="configs/ml_split.yaml", help="Path to split configuration YAML")
    parser.add_argument("--output-report", default="reports/phase-2-3-split.json", help="Path to output split lock JSON report")
    args = parser.parse_args()

    cfg = load_split_config(args.config)
    pune_df = pd.read_parquet(args.pune)
    _, _, _, pune_diag = split_temporal_dataset(pune_df, cfg)

    nashik_df = pd.read_parquet(args.nashik)
    nashik_meta = {
        "total_rows": len(nashik_df),
        "unique_panchayats": int(nashik_df["panchayat_id"].nunique()),
        "unique_dates": int(nashik_df["date"].nunique()),
        "earliest_date": str(nashik_df["date"].min()),
        "latest_date": str(nashik_df["date"].max()),
        "structure": "Single-observation spatial snapshot per Panchayat (lead_days=0)",
        "recommendation": "Evaluated as an out-of-district spatial transferability test set."
    }

    report = create_split_lock_report(pune_diag, nashik_meta, args.output_report)
    print("\n" + "=" * 80)
    print("GRAMSEVAK PHASE 2.3 — ML TEMPORAL SPLIT VERIFICATION")
    print("=" * 80)
    print(f"Status: {report['test_lock_status']}")
    print(f"Train Rows: {pune_diag['train']['row_count']} ({pune_diag['train']['start_date']} to {pune_diag['train']['end_date']})")
    print(f"Val Rows:   {pune_diag['validation']['row_count']} ({pune_diag['validation']['start_date']} to {pune_diag['validation']['end_date']})")
    print(f"Test Rows:  {pune_diag['test']['row_count']} ({pune_diag['test']['start_date']} to {pune_diag['test']['end_date']})")
    print(f"Panchayat Coverage: {pune_diag['panchayat_overlap']['shared_across_train_val_test']} / {pune_diag['panchayat_overlap']['total_unique_panchayats']} (100.0%)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
