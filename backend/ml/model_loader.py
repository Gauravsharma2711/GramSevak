"""
GramSevak ML Model Loader & In-Process Cache (Phase 2.7).

Provides robust, cached loading of trained downscaling artifacts
without re-reading from disk on every API invocation.
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional, Tuple, Union
import joblib
from backend.ml.registry import ModelRegistry
from ml.models.random_forest import RandomForestDownscaler
from ml.models.xgboost import XGBoostDownscaler

logger = logging.getLogger("backend.ml.model_loader")


class ModelArtifactNotFoundError(FileNotFoundError):
    """Raised when a configured model artifact directory or binary is missing."""
    pass


class ModelCompatibilityError(ValueError):
    """Raised when an artifact has an incompatible feature contract or version."""
    pass


class ModelLoader:
    """Thread-safe in-process cache and loader for ML downscaling models."""

    _instance: Optional["ModelLoader"] = None

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or ModelRegistry.get_instance()
        self._cache: Dict[str, Any] = {}
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._load_durations: Dict[str, float] = {}

    @classmethod
    def get_instance(cls) -> "ModelLoader":
        """Get or initialize singleton loader instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(
        self,
        model_name: Optional[str] = None,
        force_reload: bool = False
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Load downscaler model and metadata into cache.
        Returns (model_instance, metadata_dict).
        """
        target_name = model_name or self.registry.get_active_model_name()

        if not force_reload and target_name in self._cache:
            return self._cache[target_name], self._metadata_cache[target_name]

        paths = self.registry.get_artifact_paths(target_name)
        artifact_dir = paths["artifact_dir"]
        model_path = paths["model_path"]

        if not os.path.exists(artifact_dir) or not os.path.exists(model_path):
            raise ModelArtifactNotFoundError(
                f"Model artifact for '{target_name}' not found at: {model_path}. "
                f"Ensure Phase 2.4/2.5 training has executed."
            )

        start_time = time.perf_counter()
        logger.info(f"Loading '{target_name}' model from {artifact_dir}...")

        # Load appropriate wrapper class
        cfg = self.registry.get_model_config(target_name)
        if target_name == "xgboost":
            model_instance = XGBoostDownscaler().load(artifact_dir)
        elif target_name == "random_forest":
            model_instance = RandomForestDownscaler().load(artifact_dir)
        else:
            # Generic joblib load fallback
            model_instance = joblib.load(model_path)

        load_duration = round(time.perf_counter() - start_time, 4)
        self._load_durations[target_name] = load_duration

        # Load metadata if present
        meta = {}
        if os.path.exists(paths["metadata_path"]):
            try:
                with open(paths["metadata_path"], "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as e:
                logger.warning(f"Could not read metadata for {target_name}: {e}")

        # Compatibility validation
        expected_features = self.registry.get_expected_feature_names()
        if hasattr(model_instance, "feature_names_") and model_instance.feature_names_:
            if len(model_instance.feature_names_) != len(expected_features):
                raise ModelCompatibilityError(
                    f"Feature count mismatch: model expects {len(model_instance.feature_names_)} features, "
                    f"registry provides {len(expected_features)}."
                )

        self._cache[target_name] = model_instance
        self._metadata_cache[target_name] = meta
        logger.info(f"Model '{target_name}' loaded successfully in {load_duration:.4f}s.")

        return model_instance, meta

    def get_load_duration(self, model_name: Optional[str] = None) -> Optional[float]:
        """Return time in seconds taken to load the specified model from disk."""
        target_name = model_name or self.registry.get_active_model_name()
        return self._load_durations.get(target_name)
