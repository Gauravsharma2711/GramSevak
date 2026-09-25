"""Data preprocessing and validation module."""
from ml.preprocessing.cleaner import clean_weather_data


# Defined ML Feature columns (8 numerical predictors)
FEATURE_COLUMNS = [
    "block_forecast_rainfall_mm",
    "panchayat_latitude",
    "panchayat_longitude",
    "elevation_m",
    "station_distance_km",
    "lead_days",
    "month",
    "day_of_year",
]

# Target column (1 continuous variable in mm)
TARGET_COLUMN = "actual_rainfall_mm"

# Metadata columns (strictly excluded from numerical ML features)
METADATA_COLUMNS = [
    "panchayat_id",
    "lgd_code",
    "panchayat_name",
    "block_name",
    "district_name",
    "station_id",
    "date",
    "forecast_issue_date",
]

import os
import pandas as pd
from typing import Tuple, List, Optional
from sklearn.impute import SimpleImputer


class WeatherDataPreprocessor:
    """
    Reproducible preprocessing pipeline for Panchayat-level weather downscaling.
    """
    def __init__(self, feature_columns: Optional[List[str]] = None):
        self.feature_columns = feature_columns or list(FEATURE_COLUMNS)
        self.imputer = SimpleImputer(strategy="median")
        self.is_fitted: bool = False
        self.medians_ = {}

    def fit(self, X_train: pd.DataFrame) -> "WeatherDataPreprocessor":
        missing_cols = [c for c in self.feature_columns if c not in X_train.columns]
        if missing_cols:
            raise ValueError(f"Missing feature columns in training data: {missing_cols}")
        X_num = X_train[self.feature_columns].copy()
        self.imputer.fit(X_num)
        self.medians_ = dict(zip(self.feature_columns, self.imputer.statistics_.tolist()))
        self.is_fitted = True
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self.is_fitted:
            raise RuntimeError("WeatherDataPreprocessor must be fitted on training data before transforming.")
        missing_cols = [c for c in self.feature_columns if c not in X.columns]
        if missing_cols:
            raise ValueError(f"Missing feature columns in input data: {missing_cols}")
        X_num = X[self.feature_columns].copy()
        imputed_array = self.imputer.transform(X_num)
        return pd.DataFrame(imputed_array, columns=self.feature_columns, index=X.index)

    def fit_transform(self, X_train: pd.DataFrame) -> pd.DataFrame:
        return self.fit(X_train).transform(X_train)

    def get_imputation_statistics(self) -> dict:
        if not self.is_fitted:
            raise RuntimeError("Preprocessor must be fitted before retrieving statistics.")
        return dict(self.medians_)


def load_dataset(dataset_path: str) -> pd.DataFrame:
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    if dataset_path.endswith(".parquet"):
        return pd.read_parquet(dataset_path)
    df = pd.read_csv(dataset_path, encoding="utf-8")
    return df


def split_dataset_by_time(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    date_col: str = "date"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Split dataset strictly chronologically into Train, Validation, and Test partitions.
    """
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found in dataset.")

    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    unique_dates = df_sorted[date_col].unique()
    n_dates = len(unique_dates)

    if n_dates < 3:
        raise ValueError(f"Insufficient unique dates ({n_dates}) for time-aware 3-way split.")

    train_idx = int(n_dates * train_ratio)
    val_idx = int(n_dates * (train_ratio + val_ratio))

    train_cutoff_date = unique_dates[train_idx]
    val_cutoff_date = unique_dates[val_idx]

    df_train = df_sorted[df_sorted[date_col] < train_cutoff_date].copy()
    df_val = df_sorted[(df_sorted[date_col] >= train_cutoff_date) & (df_sorted[date_col] < val_cutoff_date)].copy()
    df_test = df_sorted[df_sorted[date_col] >= val_cutoff_date].copy()

    split_info = {
        "total_rows": len(df_sorted),
        "total_unique_dates": int(n_dates),
        "train_rows": len(df_train),
        "train_start_date": str(df_train[date_col].min()),
        "train_end_date": str(df_train[date_col].max()),
        "train_unique_dates": int(df_train[date_col].nunique()),
        "val_rows": len(df_val),
        "val_start_date": str(df_val[date_col].min()),
        "val_end_date": str(df_val[date_col].max()),
        "val_unique_dates": int(df_val[date_col].nunique()),
        "test_rows": len(df_test),
        "test_start_date": str(df_test[date_col].min()),
        "test_end_date": str(df_test[date_col].max()),
        "test_unique_dates": int(df_test[date_col].nunique()),
    }

    return df_train, df_val, df_test, split_info



def prepare_training_features(
    df: pd.DataFrame,
    features: Optional[List[str]] = None,
    target: str = TARGET_COLUMN
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    feature_cols = features or FEATURE_COLUMNS
    missing_feats = [col for col in feature_cols if col not in df.columns]
    if missing_feats:
        raise ValueError(f"Missing required feature columns in dataset: {missing_feats}")
    if target not in df.columns:
        raise ValueError(f"Target column '{target}' not found in dataset.")
    clean_df = df.dropna(subset=[target]).copy()
    meta_cols = [col for col in METADATA_COLUMNS if col in clean_df.columns]
    X = clean_df[feature_cols].copy()
    y = clean_df[target].copy()
    metadata = clean_df[meta_cols].copy()
    return X, y, metadata


def prepare_inference_features(
    df: pd.DataFrame,
    features: Optional[List[str]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    feature_cols = features or FEATURE_COLUMNS
    missing_feats = [col for col in feature_cols if col not in df.columns]
    if missing_feats:
        raise ValueError(f"Missing required feature columns for inference: {missing_feats}")
    meta_cols = [col for col in METADATA_COLUMNS if col in df.columns]
    X = df[feature_cols].copy()
    metadata = df[meta_cols].copy()
    return X, metadata


def get_train_test_data(
    train_path: str = "data/features/nashik_train.csv",
    test_path: str = "data/features/nashik_test.csv",
    features: Optional[List[str]] = None,
    target: str = TARGET_COLUMN
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    df_train = load_dataset(train_path)
    df_test = load_dataset(test_path)
    return preprocess_train_test_data(df_train, df_test, features=features, target=target)


def preprocess_train_test_data(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    features: Optional[List[str]] = None,
    target: str = TARGET_COLUMN
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    feature_cols = features or FEATURE_COLUMNS
    X_train_raw, y_train, _ = prepare_training_features(df_train, features=feature_cols, target=target)
    X_test_raw, y_test, _ = prepare_training_features(df_test, features=feature_cols, target=target)
    preprocessor = WeatherDataPreprocessor(feature_columns=feature_cols)
    preprocessor.fit(X_train_raw)
    X_train = preprocessor.transform(X_train_raw)
    X_test = preprocessor.transform(X_test_raw)
    return X_train, X_test, y_train, y_test


__all__ = [
    "clean_weather_data",
    "FEATURE_COLUMNS",
    "TARGET_COLUMN",
    "METADATA_COLUMNS",
    "WeatherDataPreprocessor",
    "load_dataset",
    "prepare_training_features",
    "prepare_inference_features",
    "get_train_test_data",
    "preprocess_train_test_data",
]
