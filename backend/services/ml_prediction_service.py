"""
GramSevak ML Prediction Service (Phase 2.7).

Provides dedicated backend service layer for executing Panchayat rainfall downscaling,
integrating feature construction, in-process model caching, and fallback handling.
"""

import logging
from datetime import date, datetime
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
        db: Session,
        forecast_date: Optional[date] = None,
        forecast_issue_date: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve authoritative spatial, terrain, and administrative context from the database.
        Uses the Phase 3 administrative hierarchy and block_forecasts tables.
        """
        try:
            from backend.services.hierarchy_service import HierarchyService
            from backend.app.models.block_forecast import BlockForecast
            from sqlalchemy import func, case

            pid = int(panchayat_id) if str(panchayat_id).isdigit() else None
            hierarchy_svc = HierarchyService()
            spatial_ctx = None

            if pid is not None:
                try:
                    spatial_ctx = hierarchy_svc.resolve_panchayat_spatial_context(pid, db=db)
                except Exception:
                    spatial_ctx = None

            if spatial_ctx:
                b_name = spatial_ctx.get("block_name", "")
                d_name = spatial_ctx.get("district_name", "")

                # Resolve block-level forecast if date provided
                bf_rain = None
                if forecast_date and b_name:
                    bf_q = db.query(BlockForecast).filter(
                        func.lower(BlockForecast.block_name) == b_name.lower(),
                        func.lower(BlockForecast.district_name) == d_name.lower(),
                        BlockForecast.forecast_date == forecast_date,
                    )
                    if forecast_issue_date:
                        bf_rec = bf_q.order_by(
                            case((BlockForecast.forecast_issue_date == forecast_issue_date, 0), else_=1),
                            BlockForecast.forecast_issue_date.desc(),
                            BlockForecast.id.desc(),
                        ).first()
                    else:
                        bf_rec = bf_q.order_by(
                            BlockForecast.forecast_issue_date.desc(),
                            BlockForecast.id.desc(),
                        ).first()

                    if bf_rec is not None:
                        bf_rain = float(bf_rec.rainfall_mm)

                return {
                    "panchayat_name": spatial_ctx["panchayat_name"],
                    "block_name": spatial_ctx["block_name"],
                    "district_name": spatial_ctx["district_name"],
                    "panchayat_latitude": spatial_ctx["latitude"],
                    "panchayat_longitude": spatial_ctx["longitude"],
                    "elevation_m": spatial_ctx["elevation_m"],
                    "block_forecast_rainfall_mm": bf_rain,
                }
        except Exception as e:
            logger.debug(f"Database spatial lookup skipped for Panchayat {panchayat_id}: {e}")

        # Fallback to direct model query if hierarchy did not resolve
        try:
            from backend.app.models.panchayat import Panchayat
            p = db.query(Panchayat).filter(Panchayat.id == panchayat_id).first()
            if not p and str(panchayat_id).isdigit():
                p = db.query(Panchayat).filter(Panchayat.lgd_code == int(panchayat_id)).first()
            if p:
                return {
                    "panchayat_name": p.name,
                    "panchayat_latitude": float(p.latitude) if p.latitude is not None else None,
                    "panchayat_longitude": float(p.longitude) if p.longitude is not None else None,
                    "elevation_m": float(p.elevation_m) if p.elevation_m is not None else None,
                }
        except Exception as e:
            logger.debug(f"Panchayat model lookup failed: {e}")
        return None

    def resolve_and_enrich_request(
        self,
        request: DownscaleInferenceRequest,
        db: Session
    ) -> DownscaleInferenceRequest:
        """
        Enrich a DownscaleInferenceRequest with authoritative Panchayat metadata
        and block-level forecasts from the database if they are omitted from the request.
        """
        needs_spatial = request.panchayat_latitude is None or request.panchayat_longitude is None
        needs_bf = request.block_forecast_rainfall_mm is None

        if needs_spatial or needs_bf:
            enriched = self.enrich_from_db(
                panchayat_id=request.panchayat_id,
                db=db,
                forecast_date=request.forecast_date,
                forecast_issue_date=request.forecast_issue_date,
            )
            if enriched:
                req_dict = request.model_dump()
                if needs_spatial:
                    if enriched.get("panchayat_latitude") is not None:
                        req_dict["panchayat_latitude"] = enriched["panchayat_latitude"]
                    if enriched.get("panchayat_longitude") is not None:
                        req_dict["panchayat_longitude"] = enriched["panchayat_longitude"]
                    if req_dict.get("elevation_m") is None and enriched.get("elevation_m") is not None:
                        req_dict["elevation_m"] = enriched["elevation_m"]
                    if not req_dict.get("panchayat_name") and enriched.get("panchayat_name"):
                        req_dict["panchayat_name"] = enriched["panchayat_name"]
                    if not req_dict.get("block_name") and enriched.get("block_name"):
                        req_dict["block_name"] = enriched["block_name"]
                    if not req_dict.get("district_name") and enriched.get("district_name"):
                        req_dict["district_name"] = enriched["district_name"]

                if needs_bf and enriched.get("block_forecast_rainfall_mm") is not None:
                    req_dict["block_forecast_rainfall_mm"] = enriched["block_forecast_rainfall_mm"]

                request = DownscaleInferenceRequest(**req_dict)

        return request
