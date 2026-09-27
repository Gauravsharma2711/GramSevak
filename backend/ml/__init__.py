"""
GramSevak ML Inference Packaging Module (Phase 2.7).

Provides modular, robust, and reproducible inference components for
Panchayat-level rainfall downscaling:
- Model Registry & Config: backend.ml.registry
- Input & Output Schemas: backend.ml.schemas
- Feature Builder: backend.ml.feature_builder
- Model Loader & Cache: backend.ml.model_loader
- Predictor Orchestrator: backend.ml.predictor
"""

from backend.ml.registry import ModelRegistry
from backend.ml.schemas import DownscaleInferenceRequest, DownscaleInferenceResponse
from backend.ml.feature_builder import FeatureBuilder
from backend.ml.model_loader import ModelLoader
from backend.ml.predictor import DownscalingPredictor

__all__ = [
    "ModelRegistry",
    "DownscaleInferenceRequest",
    "DownscaleInferenceResponse",
    "FeatureBuilder",
    "ModelLoader",
    "DownscalingPredictor",
]
