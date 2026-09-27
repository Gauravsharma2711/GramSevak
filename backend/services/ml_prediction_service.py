"""
GramSevak ML Prediction Service (Phase 2.7).

Provides dedicated backend service layer for executing Panchayat rainfall downscaling,
integrating feature construction, in-process model caching, and fallback handling.
"""

import logging
from typing import Optional, Dict, Any, Union
from sqlalchemy.orm import Session

from backend.ml.registry import ModelRegistry
from backend.ml.model_loader import ModelLoader
from backend.ml.predictor import DownscalingPredictor
from backend.ml.schemas import DownscaleInferenceRequest, DownscaleInferenceResponse

logger = logging.getLogger("backend.services.ml_prediction_service")


class MLPredictionService:
    """Production service for ML-driven weather downscaling."""

    _instance: Optional["MLPredictionService"] = None

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        loader: Optional[ModelLoader] = None,
    ):
        self.registry = registry or ModelRegistry.get_instance()
        self.loader = loader or ModelLoader.get_instance()
        self.predictor = DownscalingPredictor(self.registry, self.loader)

    @classmethod
    def get_instance(cls) -> "MLPredictionService":
        """Get or initialize singleton prediction service instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def predict_rainfall(
        self,
        request: DownscaleInferenceRequest,
        model_name: Optional[str] = None
    ) -> DownscaleInferenceResponse:
        """
        Execute downscaling prediction for a single Panchayat forecast request.
        """
        logger.info(
            f"Executing downscaling for Panchayat={request.panchayat_id}, "
            f"date={request.forecast_date}, issue_date={request.forecast_issue_date}, "
            f"block_forecast={request.block_forecast_rainfall_mm}mm"
        )

        response = self.predictor.predict(request, model_name=model_name)

        logger.info(
            f"Downscaling complete: Panchayat={response.panchayat_id}, "
            f"predicted={response.downscaled_rainfall_mm}mm, mode={response.prediction_mode}, "
            f"model={response.model_name}:{response.model_version}"
        )
        return response

    def enrich_from_db(
        self,
        panchayat_id: Union[int, str],
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Optional helper to resolve spatial coordinates from local database if available.
        """
        try:
            from backend.app.models.panchayat import Panchayat
            p = db.query(Panchayat).filter(Panchayat.id == panchayat_id).first()
            if not p:
                try:
                    p = db.query(Panchayat).filter(Panchayat.lgd_code == int(panchayat_id)).first()
                except (ValueError, TypeError):
                    pass
            if p:
                return {
                    "panchayat_name": p.name,
                    "panchayat_latitude": float(p.latitude) if p.latitude is not None else None,
                    "panchayat_longitude": float(p.longitude) if p.longitude is not None else None,
                    "elevation_m": float(p.elevation_m) if p.elevation_m is not None else None,
                }
        except Exception as e:
            logger.debug(f"Database spatial lookup skipped for Panchayat {panchayat_id}: {e}")
        return None
