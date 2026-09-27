"""
GramSevak ML Model Registry (Phase 2.7).

Manages model metadata, configuration loading, and artifact resolution
without hardcoding model choices across service logic.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import yaml

logger = logging.getLogger("backend.ml.registry")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "ml_model.yaml")
DEFAULT_FEATURE_REGISTRY_PATH = os.path.join(PROJECT_ROOT, "schemas", "ml_feature_registry.json")


class ModelRegistry:
    """Configuration-based registry for downscaling ML models."""

    _instance: Optional["ModelRegistry"] = None

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
        feature_registry_path: str = DEFAULT_FEATURE_REGISTRY_PATH,
    ):
        self.config_path = config_path
        self.feature_registry_path = feature_registry_path
        self.config: Dict[str, Any] = {}
        self.feature_registry: Dict[str, Any] = {}
        self.load_configurations()

    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        """Get or initialize singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_configurations(self) -> None:
        """Load YAML model configuration and JSON feature registry."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to parse {self.config_path}: {e}")
                self.config = {}
        else:
            logger.warning(f"Config path {self.config_path} not found. Using default XGBoost config.")
            self.config = {
                "active_model": "xgboost",
                "models": {
                    "xgboost": {
                        "model_name": "xgboost_downscaler",
                        "model_version": "2.5.0",
                        "artifact_dir": "ml/models/xgboost",
                        "model_file": "best_model.joblib",
                        "preprocessor_file": "preprocessor.joblib",
                        "feature_registry_version": "1.0.0",
                        "feature_count": 20,
                        "target": "actual_rainfall_mm",
                    }
                },
                "fallback": {"enabled": True, "strategy": "block_forecast"}
            }

        if os.path.exists(self.feature_registry_path):
            try:
                with open(self.feature_registry_path, "r", encoding="utf-8") as f:
                    self.feature_registry = json.load(f)
            except Exception as e:
                logger.error(f"Failed to parse {self.feature_registry_path}: {e}")
                self.feature_registry = {}

    def get_active_model_name(self) -> str:
        """Return identifier of the active production model (e.g. 'xgboost')."""
        return os.getenv("ML_MODEL_TYPE", self.config.get("active_model", "xgboost"))

    def get_model_config(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration dictionary for specified or active model."""
        target_name = model_name or self.get_active_model_name()
        models_dict = self.config.get("models", {})
        if target_name not in models_dict:
            raise KeyError(f"Model '{target_name}' not registered in {self.config_path}. Available: {list(models_dict.keys())}")
        return models_dict[target_name]

    def get_artifact_paths(self, model_name: Optional[str] = None) -> Dict[str, str]:
        """Resolve full absolute paths for model artifact files."""
        cfg = self.get_model_config(model_name)
        artifact_dir = os.path.join(PROJECT_ROOT, cfg.get("artifact_dir", ""))
        
        return {
            "artifact_dir": artifact_dir,
            "model_path": os.path.join(artifact_dir, cfg.get("model_file", "best_model.joblib")),
            "preprocessor_path": os.path.join(artifact_dir, cfg.get("preprocessor_file", "preprocessor.joblib")),
            "metadata_path": os.path.join(artifact_dir, cfg.get("metadata_file", "metadata.json")),
            "config_path": os.path.join(artifact_dir, cfg.get("config_file", "config.json")),
        }

    def get_expected_feature_names(self) -> List[str]:
        """Return ordered list of 20 approved features from the feature registry."""
        if "features" in self.feature_registry:
            return [f["name"] for f in self.feature_registry["features"]]
        # Fallback to standard Phase 2.2 list
        return [
            "block_forecast_rainfall_mm",
            "log1p_block_forecast_rainfall_mm",
            "panchayat_latitude",
            "panchayat_longitude",
            "elevation_m",
            "station_distance_km",
            "station_latitude",
            "station_longitude",
            "lead_days",
            "target_month",
            "target_day_of_year",
            "target_day_of_year_sin",
            "target_day_of_year_cos",
            "historical_rainfall_prior_1d_mm",
            "historical_rainfall_prior_2d_mm",
            "historical_rainfall_prior_3d_mean_mm",
            "historical_rainfall_prior_3d_sum_mm",
            "historical_rainfall_prior_7d_mean_mm",
            "historical_rainfall_prior_7d_sum_mm",
            "has_historical_rainfall_context"
        ]

    def is_fallback_enabled(self) -> bool:
        """Check whether deterministic fallback is enabled."""
        fb = self.config.get("fallback", {})
        return bool(fb.get("enabled", True))
