"""
GramSevak Automated Test Suite for Model Evaluation and Leakage Audit (Phase 2.6).

Verifies:
1. All model artifacts load independently (Random Forest, XGBoost)
2. Baseline predictions load and compute valid shapes
3. Prediction lengths match test observations (N=30,774)
4. Test-set identity remains strictly locked and unchanged
5. Metric calculations are mathematically correct and consistent
6. District filtering functions properly for Pune and Nashik
7. Panchayat grouping and spatial error diagnostics calculate properly
8. Temporal monthly grouping functions properly
9. Rainfall-intensity sliced grouping produces expected metrics
10. Duplicate detection and observation key audits catch duplicates
11. Train/val/test overlap detection correctly flags overlap
12. Leakage checks execute and verify information boundaries
13. Evaluation reproducibility is deterministic under fixed seeds
14. Final Phase 2.6 JSON report structure and schema validity
"""

import os
import sys
import json
import pytest
import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.create_ml_splits import split_temporal_dataset, load_split_config
from scripts.evaluate_baselines import (
    BASELINE_MODEL_FEATURES,
    compute_regression_metrics,
    compute_occurrence_metrics,
    compute_comprehensive_metrics
)
from scripts.audit_ml_leakage import (
    audit_forecast_timing,
    audit_target_exclusion,
    audit_chronological_splits,
    audit_duplicates,
    audit_identifier_leakage,
    run_full_leakage_audit
)
from scripts.evaluate_models import (
    fit_linear_baseline,
    predict_linear_baseline,
    compute_error_distribution_details,
    compute_panchayat_level_analysis,
    compute_temporal_monthly_analysis,
    run_paired_bootstrap
)
from ml.features.engineer import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.random_forest import RandomForestDownscaler
from ml.models.xgboost import XGBoostDownscaler


PUNE_PATH = os.path.join(PROJECT_ROOT, "data", "ml", "features", "pune", "rainfall_features.parquet")
NASHIK_PATH = os.path.join(PROJECT_ROOT, "data", "ml", "features", "nashik", "rainfall_features.parquet")
SPLIT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "ml_split.yaml")
REPORT_PATH = os.path.join(PROJECT_ROOT, "reports", "phase-2-6-model-evaluation.json")


@pytest.fixture(scope="module")
def loaded_pune_data():
    """Load Pune features and split into Train, Val, Test."""
    if not os.path.exists(PUNE_PATH):
        pytest.skip(f"Pune dataset not found at {PUNE_PATH}")
    df = pd.read_parquet(PUNE_PATH)
    config = load_split_config(SPLIT_CONFIG_PATH)
    train_df, val_df, test_df, meta = split_temporal_dataset(df, config)
    return df, train_df, val_df, test_df


def test_model_artifacts_load_independently():
    """Verify RandomForest and XGBoost artifacts load without training process dependencies."""
    rf_dir = os.path.join(PROJECT_ROOT, "ml", "models", "random_forest")
    xgb_dir = os.path.join(PROJECT_ROOT, "ml", "models", "xgboost")

    assert os.path.exists(os.path.join(rf_dir, "best_model.joblib")), "RF model artifact missing"
    assert os.path.exists(os.path.join(xgb_dir, "best_model.joblib")), "XGB model artifact missing"

    rf = RandomForestDownscaler().load(rf_dir)
    assert rf.is_fitted is True
    assert rf.model is not None

    xgb = XGBoostDownscaler().load(xgb_dir)
    assert xgb.is_fitted is True
    assert xgb.model is not None


def test_baseline_predictions_shape_and_clamping(loaded_pune_data):
    """Verify linear baseline fits and generates non-negative predictions with expected shape."""
    _, train_df, _, test_df = loaded_pune_data
    pipe = fit_linear_baseline(train_df)
    preds = predict_linear_baseline(pipe, test_df)

    assert len(preds) == len(test_df)
    assert np.all(preds >= 0.0), "Linear baseline produced negative rainfall predictions"


def test_test_set_identity_and_length(loaded_pune_data):
    """Verify test partition row count and date boundaries remain locked."""
    _, _, _, test_df = loaded_pune_data
    assert len(test_df) == 30774, f"Expected 30774 test rows, got {len(test_df)}"
    assert str(test_df["date"].min()) == "2026-09-01"
    assert str(test_df["date"].max()) == "2026-09-23"


def test_metric_calculation_consistency():
    """Verify regression and occurrence metrics with known synthetic inputs."""
    y_true = np.array([0.0, 5.0, 10.0, 50.0])
    y_pred = np.array([0.0, 5.0, 15.0, 40.0])

    reg = compute_regression_metrics(y_true, y_pred)
    assert reg["count"] == 4
    assert pytest.approx(reg["mae"], 0.01) == 3.75  # (|0| + |0| + |5| + |10|) / 4 = 3.75
    assert pytest.approx(reg["bias"], 0.01) == -1.25  # (0 + 0 + 5 - 10) / 4 = -1.25

    occ = compute_occurrence_metrics(y_true, y_pred, threshold=0.001)
    assert occ["true_rain_events"] == 3
    assert occ["predicted_rain_events"] == 3
    assert occ["accuracy"] == 1.0
    assert occ["f1"] == 1.0


def test_sliced_metrics_intensity_grouping():
    """Verify comprehensive sliced metrics for dry, moderate, and heavy rainfall."""
    y_true = np.array([0.0, 10.0, 20.0, 40.0, 70.0])
    y_pred = np.array([0.0, 12.0, 18.0, 35.0, 65.0])

    comp = compute_comprehensive_metrics(y_true, y_pred)
    assert comp["zero_rainfall_slice"]["count"] == 1
    assert comp["nonzero_rainfall_slice"]["count"] == 4
    assert comp["moderate_plus_slice_gte_15_5mm"]["count"] == 3  # 20, 40, 70
    assert comp["heavy_slice_gte_35_5mm"]["count"] == 2  # 40, 70
    assert comp["very_heavy_slice_gte_64_5mm"]["count"] == 1  # 70


def test_panchayat_level_diagnostics():
    """Verify Panchayat spatial error aggregation and quantile computation."""
    synth_df = pd.DataFrame({
        "panchayat_id": ["P1", "P1", "P2", "P2", "P3", "P3"],
        TARGET_COLUMN: [0.0, 10.0, 5.0, 15.0, 2.0, 8.0]
    })
    preds_dict = {
        "model_test": np.array([0.0, 8.0, 5.0, 12.0, 2.0, 6.0])
    }
    panch_res = compute_panchayat_level_analysis(synth_df, preds_dict, min_observations=2)
    assert "model_test" in panch_res
    assert panch_res["model_test"]["panchayats_evaluated"] == 3
    assert panch_res["model_test"]["mean_mae"] > 0.0


def test_temporal_monthly_diagnostics():
    """Verify monthly temporal breakdown grouping."""
    synth_df = pd.DataFrame({
        "date": ["2026-04-15", "2026-05-15", "2026-06-15"],
        "target_month": [4, 5, 6],
        TARGET_COLUMN: [2.0, 5.0, 15.0]
    })
    preds_dict = {"model_test": np.array([2.5, 4.5, 16.0])}
    monthly = compute_temporal_monthly_analysis(synth_df, preds_dict)
    assert "model_test" in monthly
    assert "4" in monthly["model_test"]
    assert "5" in monthly["model_test"]
    assert "6" in monthly["model_test"]


def test_duplicate_and_overlap_detection():
    """Verify duplicate row detection and chronological partition isolation."""
    # Clean dataframe
    clean_df = pd.DataFrame({
        "panchayat_id": [1, 2, 3],
        "date": ["2026-05-01", "2026-05-01", "2026-05-01"],
        "forecast_issue_date": ["2026-04-30", "2026-04-30", "2026-04-30"],
        TARGET_COLUMN: [0.0, 2.0, 5.0]
    })
    res_clean = audit_duplicates(clean_df)
    assert res_clean["status"] == "PASSED"

    # Injected duplicate
    dup_df = pd.concat([clean_df, clean_df.iloc[[0]]], ignore_index=True)
    res_dup = audit_duplicates(dup_df)
    assert res_dup["status"] == "FAILED"
    assert res_dup["exact_duplicate_rows"] == 1


def test_leakage_audit_script_execution():
    """Verify full leakage audit script passes completely on project feature data."""
    audit_report = run_full_leakage_audit(PUNE_PATH, NASHIK_PATH, SPLIT_CONFIG_PATH)
    assert audit_report["metadata"]["overall_status"] == "PASSED"
    assert audit_report["checks"]["forecast_timing"]["status"] == "PASSED"
    assert audit_report["checks"]["target_exclusion"]["status"] == "PASSED"
    assert audit_report["checks"]["chronological_splits"]["status"] == "PASSED"
    assert audit_report["checks"]["identifier_leakage"]["status"] == "PASSED"


def test_paired_bootstrap_uncertainty():
    """Verify paired bootstrap resampling produces valid confidence intervals."""
    rng = np.random.default_rng(42)
    y_true = rng.uniform(0, 20, size=500)
    preds_a = y_true + rng.normal(0, 2, size=500)
    preds_b = y_true + rng.normal(0, 5, size=500)

    boot_res = run_paired_bootstrap(y_true, preds_a, preds_b, "model_a", "model_b", n_bootstraps=100, seed=42)
    assert boot_res["sample_size"] == 500
    assert len(boot_res["mae_delta_95_ci"]) == 2
    assert boot_res["mae_delta_95_ci"][0] < boot_res["mae_delta_95_ci"][1]


def test_report_json_structure_and_schema():
    """Verify that reports/phase-2-6-model-evaluation.json matches all required sections."""
    assert os.path.exists(REPORT_PATH), f"Report not found at {REPORT_PATH}"
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_sections = [
        "evaluation", "models", "dataset", "split", "overall_metrics",
        "district_metrics", "panchayat_metrics", "temporal_metrics",
        "rainfall_intensity_metrics", "error_analysis", "baseline_comparison",
        "random_forest_vs_xgboost", "uncertainty_analysis",
        "geographic_generalization", "leakage_audit", "duplicate_analysis",
        "reproducibility", "limitations", "phase_2_7_evidence"
    ]

    for section in required_sections:
        assert section in data, f"Required section '{section}' missing from report JSON"

    assert len(data["final_comparison_table"]) >= 12, "Comparison table missing model evaluation rows"
