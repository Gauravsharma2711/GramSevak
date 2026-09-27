"""Downscaling machine learning models."""
from ml.models.baseline import BlockPersistenceBaseline
from ml.models.random_forest import RandomForestDownscaler
from ml.models.xgboost import XGBoostDownscaler

__all__ = ["BlockPersistenceBaseline", "RandomForestDownscaler", "XGBoostDownscaler"]
