import os
import json
import pandas as pd
import numpy as np
from ml.features.engineer import extract_features, FEATURE_COLUMNS, TARGET_COLUMN
from ml.preprocessing.cleaner import clean_weather_data
from ml.models.baseline import BlockPersistenceBaseline
from ml.models.random_forest import RandomForestDownscaler
from ml.evaluation.metrics import evaluate_predictions, compare_model_against_baseline
from ml.predictions.pipeline import DownscalingPipeline


def test_clean_weather_data():
    sample_df = pd.DataFrame([{
        "panchayat_id": 1,
        "date": "2026-09-04",
        "forecast_issue_date": "2026-09-03",
        "block_forecast_rainfall_mm": "12.5",
        "actual_rainfall_mm": "14.2",
        "panchayat_latitude": "23.5",
        "panchayat_longitude": "85.3",
        "elevation_m": "650",
        "station_distance_km": "5.2"
    }])
    cleaned = clean_weather_data(sample_df)
    assert cleaned["block_forecast_rainfall_mm"].iloc[0] == 12.5
    assert cleaned["actual_rainfall_mm"].iloc[0] == 14.2


def test_extract_features():
    sample_df = pd.DataFrame([{
        "panchayat_id": 1,
        "date": pd.to_datetime("2026-09-04"),
        "forecast_issue_date": pd.to_datetime("2026-09-03"),
        "block_forecast_rainfall_mm": 12.5,
        "actual_rainfall_mm": 14.2,
        "panchayat_latitude": 23.5,
        "panchayat_longitude": 85.3,
        "elevation_m": 650.0,
        "station_distance_km": 5.2
    }])
    X, y = extract_features(sample_df)
    for col in FEATURE_COLUMNS:
        assert col in X.columns
    assert y.iloc[0] == 14.2
    assert X["target_month"].iloc[0] == 9
    assert X["lead_days"].iloc[0] == 1


def test_baseline_model():
    baseline = BlockPersistenceBaseline()
    sample_X = pd.DataFrame({
        "block_forecast_rainfall_mm": [10.0, 25.0, 0.0]
    })
    preds = baseline.predict(sample_X)
    np.testing.assert_array_equal(preds, [10.0, 25.0, 0.0])


def test_evaluation_metrics():
    y_true = np.array([10.0, 20.0, 30.0])
    y_baseline = np.array([12.0, 25.0, 28.0])
    y_model = np.array([11.0, 21.0, 29.0])
    
    report = compare_model_against_baseline(y_true, y_baseline, y_model)
    assert "baseline" in report
    assert "downscaled_model" in report
    assert report["is_improvement"] is True


def test_downscaling_pipeline():
    pipeline = DownscalingPipeline()
    sample_df = pd.DataFrame([{
        "panchayat_id": 1,
        "date": pd.to_datetime("2026-09-04"),
        "forecast_issue_date": pd.to_datetime("2026-09-03"),
        "block_forecast_rainfall_mm": 15.0,
        "actual_rainfall_mm": 18.0,
        "panchayat_latitude": 23.5,
        "panchayat_longitude": 85.3,
        "elevation_m": 650.0,
        "station_distance_km": 5.2
    }])
    output = pipeline.run(sample_df)
    assert "downscaled_rainfall_mm" in output.columns
    assert output["downscaled_rainfall_mm"].iloc[0] == 15.0


def test_ml_preprocessing_module():
    from ml.preprocessing import prepare_training_features, prepare_inference_features, FEATURE_COLUMNS, METADATA_COLUMNS
    sample_df = pd.DataFrame([{
        "panchayat_id": 1001,
        "lgd_code": 182597,
        "panchayat_name": "Test",
        "block_name": "Baglan",
        "district_name": "Nashik",
        "station_id": "Satana AWS",
        "date": "2026-09-04",
        "forecast_issue_date": "2026-09-04",
        "block_forecast_rainfall_mm": 10.0,
        "panchayat_latitude": 20.65,
        "panchayat_longitude": 74.05,
        "elevation_m": 580.0,
        "station_distance_km": 9.5,
        "lead_days": 0,
        "month": 9,
        "day_of_year": 247,
        "actual_rainfall_mm": 8.5
    }])
    X, y, meta = prepare_training_features(sample_df)
    assert list(X.columns) == FEATURE_COLUMNS
    assert y.iloc[0] == 8.5
    assert "panchayat_id" not in X.columns
    assert "panchayat_id" in meta.columns

    X_inf, meta_inf = prepare_inference_features(sample_df)
    assert list(X_inf.columns) == FEATURE_COLUMNS
    assert "panchayat_id" in meta_inf.columns


def test_ml_compute_regression_metrics():
    from ml.evaluate import compute_regression_metrics
    y_true = np.array([5.0, 10.0, 15.0])
    y_pred = np.array([5.0, 10.0, 15.0])
    metrics = compute_regression_metrics(y_true, y_pred)
    assert metrics["mae_mm"] == 0.0
    assert metrics["rmse_mm"] == 0.0
    assert metrics["r2_score"] == 1.0


def test_weather_data_preprocessor_pipeline():
    from ml.preprocessing import WeatherDataPreprocessor, preprocess_train_test_data, get_train_test_data
    
    # 1. Test median imputation learned strictly on train
    train_syn = pd.DataFrame({
        "block_forecast_rainfall_mm": [10.0, 20.0, 30.0, np.nan],
        "panchayat_latitude": [20.1, 20.2, 20.3, 20.4],
        "panchayat_longitude": [74.1, 74.2, 74.3, 74.4],
        "elevation_m": [500.0, 600.0, 700.0, 800.0],
        "station_distance_km": [5.0, 10.0, 15.0, 20.0],
        "lead_days": [0, 1, 2, 3],
        "month": [1, 2, 3, 4],
        "day_of_year": [10, 20, 30, 40],
        "actual_rainfall_mm": [12.0, 18.0, 25.0, 35.0]
    })
    test_syn = pd.DataFrame({
        "block_forecast_rainfall_mm": [np.nan, 100.0, 200.0],
        "panchayat_latitude": [20.5, 20.6, 20.7],
        "panchayat_longitude": [74.5, 74.6, 74.7],
        "elevation_m": [550.0, 650.0, 750.0],
        "station_distance_km": [6.0, 11.0, 16.0],
        "lead_days": [0, 1, 2],
        "month": [5, 6, 7],
        "day_of_year": [50, 60, 70],
        "actual_rainfall_mm": [15.0, 90.0, 180.0]
    })
    X_tr, X_te, y_tr, y_te = preprocess_train_test_data(train_syn, test_syn)
    assert X_tr.loc[3, "block_forecast_rainfall_mm"] == 20.0  # Train median
    assert X_te.loc[0, "block_forecast_rainfall_mm"] == 20.0  # Must be imputed with train median (not 150)
    assert len(X_tr) == 4
    assert len(X_te) == 3

    # 2. Test get_train_test_data on actual Nashik train/test files
    X_train_real, X_test_real, y_train_real, y_test_real = get_train_test_data(
        train_path="data/features/nashik_train.csv",
        test_path="data/features/nashik_test.csv"
    )
    assert len(X_train_real) == 1110
    assert len(X_test_real) == 278
    assert len(y_train_real) == 1110
    assert len(y_test_real) == 278
    assert X_train_real.isnull().sum().sum() == 0
    assert X_test_real.isnull().sum().sum() == 0


def test_train_random_forest_execution(tmp_path):
    from ml.train import train_random_forest
    model_file = tmp_path / "rf_model.joblib"
    prep_file = tmp_path / "rf_prep.joblib"
    conf_file = tmp_path / "rf_conf.json"

    res = train_random_forest(
        train_path="data/features/nashik_train.csv",
        model_output_path=str(model_file),
        preprocessor_output_path=str(prep_file),
        config_output_path=str(conf_file),
        n_estimators=10,  # fast test
        max_depth=4,
        random_state=42
    )

    assert os.path.exists(str(model_file))
    assert os.path.exists(str(prep_file))
    assert os.path.exists(str(conf_file))
    assert res["train_rows"] == 1110
    assert "feature_importances" in res
    assert len(res["feature_importances"]) == 8


def test_generate_test_predictions(tmp_path):
    from ml.predict import generate_test_predictions
    output_file = tmp_path / "test_predictions.csv"
    
    df_preds = generate_test_predictions(
        test_path="data/features/nashik_test.csv",
        model_path="ml/models/random_forest_model.joblib",
        preprocessor_path="ml/models/random_forest_preprocessor.joblib",
        output_path=str(output_file)
    )
    
    assert os.path.exists(str(output_file))
    assert len(df_preds) == 278
    
    expected_cols = [
        "panchayat_id",
        "panchayat_name",
        "block_name",
        "date",
        "forecast_issue_date",
        "lead_days",
        "block_forecast_rainfall_mm",
        "actual_rainfall_mm",
        "raw_predicted_rainfall_mm",
        "predicted_rainfall_mm",
        "prediction_error",
        "absolute_error",
        "squared_error",
    ]
    assert list(df_preds.columns) == expected_cols
    
    # Verify mathematical accuracy of error metrics
    np.testing.assert_allclose(
        df_preds["prediction_error"],
        df_preds["predicted_rainfall_mm"] - df_preds["actual_rainfall_mm"],
        atol=1e-3
    )
    np.testing.assert_allclose(
        df_preds["absolute_error"],
        np.abs(df_preds["predicted_rainfall_mm"] - df_preds["actual_rainfall_mm"]),
        atol=1e-3
    )
    np.testing.assert_allclose(
        df_preds["squared_error"],
        df_preds["prediction_error"] ** 2,
        atol=1e-3
    )


def test_evaluate_random_forest(tmp_path):
    from ml.evaluate import evaluate_random_forest
    metrics_file = tmp_path / "model_metrics.csv"
    comp_file = tmp_path / "model_comparison.csv"
    
    metrics_df, comp_df, summary = evaluate_random_forest(
        predictions_path="ml/validation/random_forest_predictions.csv",
        output_metrics_path=str(metrics_file),
        output_comparison_path=str(comp_file)
    )
    
    assert os.path.exists(str(metrics_file))
    assert os.path.exists(str(comp_file))
    assert summary["test_samples"] == 278
    assert "baseline_mae" in summary
    assert "model_mae" in summary
    assert "mae_improvement_pct" in summary
    assert "rmse_improvement_pct" in summary
    
    # Check all required dimensions
    dimensions = set(comp_df["dimension"].unique())
    assert {"overall", "lead_days", "block", "month"}.issubset(dimensions)


def test_generate_prediction_diagnostics(tmp_path):
    from ml.evaluate import generate_prediction_diagnostics
    diag_file = tmp_path / "diagnostics.csv"
    
    diag_df, slices = generate_prediction_diagnostics(
        predictions_path="ml/validation/random_forest_predictions.csv",
        output_diagnostics_path=str(diag_file)
    )
    
    assert os.path.exists(str(diag_file))
    assert len(diag_df) == 60
    assert len(slices["random_20"]) == 20
    assert len(slices["best_10"]) == 10
    assert len(slices["worst_10"]) == 10
    assert len(slices["largest_over"]) == 10
    assert len(slices["largest_under"]) == 10
    
    required_cols = [
        "panchayat_name",
        "block_name",
        "date",
        "block_forecast_rainfall_mm",
        "predicted_rainfall_mm",
        "actual_rainfall_mm",
        "absolute_error"
    ]
    for col in required_cols:
        assert col in diag_df.columns


def test_check_predictions_sanity():
    from ml.evaluate import check_predictions_sanity
    df_preds = pd.read_csv("ml/validation/random_forest_predictions.csv")
    sanity = check_predictions_sanity(df_preds)
    
    assert sanity["total_records"] == 278
    assert sanity["negative_predictions_before_clipping"] == 0
    assert sanity["extremely_large_predictions_gt_200mm"] == 0
    assert sanity["nan_predictions"] == 0
    assert sanity["infinite_predictions"] == 0
    assert sanity["missing_predictions"] == 0
    assert sanity["clipping_contract_valid"] is True


def test_export_feature_importance(tmp_path):
    from ml.evaluate import export_feature_importance
    csv_file = tmp_path / "feat_imp.csv"
    png_file = tmp_path / "feat_imp.png"
    
    df_imp = export_feature_importance(
        model_path="ml/models/random_forest_model.joblib",
        output_csv_path=str(csv_file),
        output_png_path=str(png_file)
    )
    
    assert os.path.exists(str(csv_file))
    assert os.path.exists(str(png_file))
    assert list(df_imp.columns) == ["feature", "importance", "rank"]
    assert len(df_imp) == 8
    assert list(df_imp["rank"]) == list(range(1, 9))
    assert df_imp["importance"].is_monotonic_decreasing
    assert df_imp.iloc[0]["feature"] == "block_forecast_rainfall_mm"


def test_train_and_predict_xgboost(tmp_path):
    from ml.train import train_xgboost
    from ml.predict import generate_xgboost_predictions
    
    xgb_model_file = tmp_path / "xgb_model.joblib"
    xgb_config_file = tmp_path / "xgb_config.json"
    xgb_preds_file = tmp_path / "xgb_preds.csv"
    
    summary = train_xgboost(
        train_path="data/features/nashik_train.csv",
        model_output_path=str(xgb_model_file),
        config_output_path=str(xgb_config_file),
        n_estimators=15,
        max_depth=3,
        random_state=42
    )
    
    assert os.path.exists(str(xgb_model_file))
    assert os.path.exists(str(xgb_config_file))
    assert summary["train_rows"] == 1110
    assert "feature_importances" in summary
    
    preds_df = generate_xgboost_predictions(
        test_path="data/features/nashik_test.csv",
        model_path=str(xgb_model_file),
        preprocessor_path="ml/models/random_forest_preprocessor.joblib",
        output_path=str(xgb_preds_file)
    )
    
    assert os.path.exists(str(xgb_preds_file))
    assert len(preds_df) == 278
    assert "raw_predicted_rainfall_mm" in preds_df.columns
    assert "predicted_rainfall_mm" in preds_df.columns
    assert "absolute_error" in preds_df.columns


def test_compare_all_models(tmp_path):
    from ml.evaluate import compare_all_models
    comp_file = tmp_path / "model_comp.csv"
    
    df_comp, summary = compare_all_models(
        rf_predictions_path="ml/validation/random_forest_predictions.csv",
        xgb_predictions_path="ml/validation/xgboost_predictions.csv",
        output_comparison_path=str(comp_file)
    )
    
    assert os.path.exists(str(comp_file))
    assert len(df_comp) == 3
    assert list(df_comp.columns) == [
        "model",
        "mae",
        "rmse",
        "mae_improvement_percent",
        "rmse_improvement_percent"
    ]
    assert df_comp.iloc[2]["model"] == "XGBoost"
    assert "verdict" in summary
    assert "recommended_model" in summary


def test_evaluate_block_spatial_performance(tmp_path):
    from ml.evaluate import evaluate_block_spatial_performance
    block_file = tmp_path / "block_perf.csv"
    
    df_block, cats = evaluate_block_spatial_performance(
        predictions_path="ml/validation/random_forest_predictions.csv",
        output_path=str(block_file)
    )
    
    assert os.path.exists(str(block_file))
    assert len(df_block) == 7
    expected_cols = [
        "block_name",
        "test_observations",
        "baseline_mae",
        "model_mae",
        "baseline_rmse",
        "model_rmse",
        "mae_improvement_percentage",
        "rmse_improvement_percentage"
    ]
    assert list(df_block.columns) == expected_cols
    assert df_block["mae_improvement_percentage"].is_monotonic_decreasing
    assert "Dindori" in cats["improved"]
    assert "Chandwad" in cats["worse"]


def test_evaluate_lead_day_performance(tmp_path):
    from ml.evaluate import evaluate_lead_day_performance
    lead_file = tmp_path / "lead_perf.csv"
    
    df_lead, summary = evaluate_lead_day_performance(
        predictions_path="ml/validation/random_forest_predictions.csv",
        output_path=str(lead_file)
    )
    
    assert os.path.exists(str(lead_file))
    assert len(df_lead) >= 1
    expected_cols = [
        "lead_days",
        "observation_count",
        "baseline_mae",
        "model_mae",
        "baseline_rmse",
        "model_rmse",
        "mae_improvement_percentage",
        "rmse_improvement_percentage"
    ]
    assert list(df_lead.columns) == expected_cols
    assert "lead_days_evaluated" in summary
    assert "benefiting_lead_days" in summary
    assert "non_benefiting_lead_days" in summary


def test_analyze_rainfall_distribution(tmp_path):
    from ml.evaluate import analyze_rainfall_distribution
    dist_file = tmp_path / "rainfall_dist.csv"
    
    df_dist, summary = analyze_rainfall_distribution(
        predictions_path="ml/validation/random_forest_predictions.csv",
        output_path=str(dist_file)
    )
    
    assert os.path.exists(str(dist_file))
    assert len(df_dist) == 3
    assert set(df_dist["column_name"]) == {
        "actual_rainfall_mm",
        "block_forecast_rainfall_mm",
        "predicted_rainfall_mm"
    }
    for col in ["minimum_mm", "maximum_mm", "median_mm", "mean_mm", "zero_percentage", "nonzero_percentage"]:
        assert col in df_dist.columns
    assert "Actual Ground Rainfall" in summary
    assert summary["Actual Ground Rainfall"]["minimum_mm"] == 1.2
    assert summary["Actual Ground Rainfall"]["maximum_mm"] == 45.2


def test_freeze_v1_model(tmp_path):
    from ml.train import freeze_v1_model
    best_model_file = tmp_path / "best_model.joblib"
    best_config_file = tmp_path / "best_model_config.json"
    
    result = freeze_v1_model(
        selected_model_source="ml/models/xgboost_model.joblib",
        model_output_path=str(best_model_file),
        config_output_path=str(best_config_file)
    )
    
    assert os.path.exists(str(best_model_file))
    assert os.path.exists(str(best_config_file))
    
    with open(str(best_config_file), "r") as f:
        config = json.load(f)
        
    expected_fields = [
        "model_name",
        "model_version",
        "feature_list",
        "training_date_range",
        "training_rows",
        "test_date_range",
        "test_rows",
        "baseline_mae",
        "baseline_rmse",
        "model_mae",
        "model_rmse",
        "mae_improvement_percent",
        "rmse_improvement_percent"
    ]
    for field in expected_fields:
        assert field in config
    assert config["model_name"] == "XGBoost Regressor"
    assert config["training_rows"] == 1110
    assert config["test_rows"] == 278


def test_predict_downscaled_rainfall():
    from ml.predict import predict_downscaled_rainfall
    
    result = predict_downscaled_rainfall(
        block_forecast_rainfall_mm=10.0,
        panchayat_latitude=20.20,
        panchayat_longitude=73.80,
        elevation_m=600.0,
        station_distance_km=5.0,
        lead_days=0,
        month=9,
        day_of_year=247
    )
    
    assert isinstance(result, dict)
    assert "downscaled_rainfall_mm" in result
    assert "raw_predicted_rainfall_mm" in result
    assert "model_name" in result
    assert "model_version" in result
    assert isinstance(result["downscaled_rainfall_mm"], (int, float))
    assert result["downscaled_rainfall_mm"] >= 0.0
    assert result["model_name"] == "XGBoost Regressor"
    assert result["model_version"] == "v1.0.0"
