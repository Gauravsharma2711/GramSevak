"""
GramSevak Feature Builder (Phase 2.7).

Constructs model-ready 20-feature input matrices for downscaling models
conforming strictly to the Phase 2.2 Feature Registry v1.0.0.
"""

import math
from datetime import date
from typing import List, Dict, Any, Union
import numpy as np
import pandas as pd
from backend.ml.schemas import DownscaleInferenceRequest
from backend.ml.registry import ModelRegistry


class FeatureBuilder:
    """Transforms raw inference request payloads into ordered feature vectors."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.expected_feature_names: List[str] = registry.get_expected_feature_names()

    def build_features(self, request: DownscaleInferenceRequest) -> pd.DataFrame:
        """
        Transform a single DownscaleInferenceRequest into a 1-row DataFrame
        with exactly the 20 approved features in the exact registry order.
        """
        f_date: date = request.forecast_date
        i_date: date = request.forecast_issue_date

        # 1. Lead time calculation
        if request.lead_days is not None:
            lead_days = int(request.lead_days)
        else:
            lead_days = max(0, (f_date - i_date).days)

        # 2. Block forecast transformations
        block_rain = float(request.block_forecast_rainfall_mm)
        log1p_block_rain = float(np.log1p(block_rain))

        # 3. Temporal harmonics
        month = int(f_date.month)
        day_of_year = int(f_date.timetuple().tm_yday)
        doy_sin = float(np.sin(2.0 * math.pi * day_of_year / 365.25))
        doy_cos = float(np.cos(2.0 * math.pi * day_of_year / 365.25))

        # 4. Context indicator
        hist_1d = request.historical_rainfall_prior_1d_mm
        hist_2d = request.historical_rainfall_prior_2d_mm
        hist_3d_mean = request.historical_rainfall_prior_3d_mean_mm
        hist_3d_sum = request.historical_rainfall_prior_3d_sum_mm
        hist_7d_mean = request.historical_rainfall_prior_7d_mean_mm
        hist_7d_sum = request.historical_rainfall_prior_7d_sum_mm

        if request.has_historical_rainfall_context is not None:
            has_context = int(request.has_historical_rainfall_context)
        else:
            has_context = 1 if any(v is not None for v in [hist_1d, hist_2d, hist_3d_mean, hist_7d_mean]) else 0

        # Construct raw row dict
        row = {
            "block_forecast_rainfall_mm": block_rain,
            "log1p_block_forecast_rainfall_mm": log1p_block_rain,
            "panchayat_latitude": float(request.panchayat_latitude),
            "panchayat_longitude": float(request.panchayat_longitude),
            "elevation_m": float(request.elevation_m) if request.elevation_m is not None else np.nan,
            "station_distance_km": float(request.station_distance_km) if request.station_distance_km is not None else np.nan,
            "station_latitude": float(request.station_latitude) if request.station_latitude is not None else np.nan,
            "station_longitude": float(request.station_longitude) if request.station_longitude is not None else np.nan,
            "lead_days": float(lead_days),
            "target_month": float(month),
            "target_day_of_year": float(day_of_year),
            "target_day_of_year_sin": doy_sin,
            "target_day_of_year_cos": doy_cos,
            "historical_rainfall_prior_1d_mm": float(hist_1d) if hist_1d is not None else np.nan,
            "historical_rainfall_prior_2d_mm": float(hist_2d) if hist_2d is not None else np.nan,
            "historical_rainfall_prior_3d_mean_mm": float(hist_3d_mean) if hist_3d_mean is not None else np.nan,
            "historical_rainfall_prior_3d_sum_mm": float(hist_3d_sum) if hist_3d_sum is not None else np.nan,
            "historical_rainfall_prior_7d_mean_mm": float(hist_7d_mean) if hist_7d_mean is not None else np.nan,
            "historical_rainfall_prior_7d_sum_mm": float(hist_7d_sum) if hist_7d_sum is not None else np.nan,
            "has_historical_rainfall_context": float(has_context),
        }

        # Build DataFrame with exact ordered columns
        df = pd.DataFrame([row], columns=self.expected_feature_names)
        return df

    def build_batch_features(self, requests: List[DownscaleInferenceRequest]) -> pd.DataFrame:
        """Batch construct features for multiple requests."""
        dfs = [self.build_features(r) for r in requests]
        return pd.concat(dfs, ignore_index=True)
