"""
GramSevak Downscaling Predictor (Phase 2.7).

Orchestrates input feature construction, cached model inference,
output validity checking, and deterministic fallback behavior.
"""

import time
import math
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd

from backend.ml.registry import ModelRegistry
from backend.ml.model_loader import ModelLoader, ModelArtifactNotFoundError
from backend.ml.feature_builder import FeatureBuilder
from backend.ml.schemas import DownscaleInferenceRequest, DownscaleInferenceResponse

logger = logging.getLogger("backend.ml.predictor")


class PredictionOutputError(ValueError):
    """Raised when model produces non-finite, NaN, or physically implausible output."""
    pass


class DownscalingPredictor:
    """Predictor orchestrator for micro-level weather forecast downscaling."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        loader: Optional[ModelLoader] = None,
    ):
        self.registry = registry or ModelRegistry.get_instance()
        self.loader = loader or ModelLoader.get_instance()
        self.builder = FeatureBuilder(self.registry)

    def predict(
        self,
        request: DownscaleInferenceRequest,
        model_name: Optional[str] = None
    ) -> DownscaleInferenceResponse:
        """
        Execute Panchayat-level downscaling inference with deterministic fallback support.
        """
        start_time = time.perf_counter()
        target_model = model_name or self.registry.get_active_model_name()
        model_cfg = self.registry.get_model_config(target_model)

        lead_days = request.lead_days if request.lead_days is not None else max(0, (request.forecast_date - request.forecast_issue_date).days)
        block_forecast = float(request.block_forecast_rainfall_mm)

        try:
            # 1. Load model instance from cache
            model, meta = self.loader.load_model(target_model)

            # 2. Build feature vector
            feature_df = self.builder.build_features(request)

            # 3. Execute model prediction
            raw_preds = model.predict(feature_df)
            pred_val = float(raw_preds[0])

            # 4. Validate output
            if math.isnan(pred_val) or math.isinf(pred_val):
                raise PredictionOutputError(f"Model returned non-finite output: {pred_val}")

            # Enforce physical non-negativity constraint
            downscaled_rainfall = max(0.0, round(pred_val, 4))
            prediction_mode = "ml"
            metadata_diag = {
                "inference_duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "model_family": model_cfg.get("model_family"),
                "raw_prediction_mm": round(pred_val, 4)
            }

        except (ModelArtifactNotFoundError, Exception) as e:
            if not self.registry.is_fallback_enabled():
                logger.error(f"Prediction failed for Panchayat {request.panchayat_id} and fallback is disabled: {e}")
                raise e

            # Deterministic fallback to regional numerical block forecast
            logger.warning(
                f"ML model '{target_model}' execution failed ({type(e).__name__}: {e}). "
                f"Falling back deterministically to raw block forecast ({block_forecast} mm)."
            )
            downscaled_rainfall = max(0.0, round(block_forecast, 4))
            prediction_mode = "fallback"
            metadata_diag = {
                "inference_duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "fallback_reason": f"{type(e).__name__}: {str(e)}",
                "fallback_strategy": "block_forecast"
            }

        return DownscaleInferenceResponse(
            panchayat_id=request.panchayat_id,
            forecast_date=request.forecast_date,
            forecast_issue_date=request.forecast_issue_date,
            lead_days=lead_days,
            block_forecast_rainfall_mm=block_forecast,
            downscaled_rainfall_mm=downscaled_rainfall,
            model_name=model_cfg.get("model_name", target_model),
            model_version=model_cfg.get("model_version", "unknown"),
            feature_registry_version=model_cfg.get("feature_registry_version", "1.0.0"),
            prediction_mode=prediction_mode,
            confidence=None,  # No fabricated confidence percentages
            inference_timestamp=datetime.now(timezone.utc),
            metadata=metadata_diag
        )
