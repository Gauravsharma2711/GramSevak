import os
import json
import logging
from typing import Optional, Union, List, Dict, Any
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer

logger = logging.getLogger("RandomForestDownscaler")


class RandomForestDownscaler:
    """
    Random Forest Regression model for downscaling Block-level rainfall forecasts
    to Panchayat-level hyper-local forecasts using spatial, terrain, and temporal features.
    
    Adheres strictly to the Phase 2.1 ML Data Contract and Phase 2.2 Feature Registry.
    Applies training-fitted median imputation for historical feature warm-up nulls
    and enforces a non-negative precipitation clipping constraint (>= 0.0 mm).
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: Optional[int] = 6,
        min_samples_split: int = 5,
        min_samples_leaf: int = 100,
        max_features: Union[str, float, int] = 0.2,
        random_state: int = 42,
        n_jobs: int = -1,
    ):
        self.model_name = "random_forest_downscaler"
        self.version = "2.4.0"
        self.params: Dict[str, Any] = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "min_samples_split": min_samples_split,
            "min_samples_leaf": min_samples_leaf,
            "max_features": max_features,
            "random_state": random_state,
            "n_jobs": n_jobs,
        }
        self.model: Optional[RandomForestRegressor] = None
        self.imputer: Optional[SimpleImputer] = None
        self.feature_names_: List[str] = []
        self.is_fitted: bool = False

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray], feature_names: Optional[List[str]] = None) -> "RandomForestDownscaler":
        """
        Fit the SimpleImputer (median) and RandomForestRegressor on training features X and target y.
        Strictly fitted on training fold without observing validation or test distributions.
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names_ = list(X.columns)
            X_arr = X.values
        else:
            X_arr = np.asarray(X)
            if feature_names is not None:
                self.feature_names_ = list(feature_names)
            elif not self.feature_names_:
                self.feature_names_ = [f"feature_{i}" for i in range(X_arr.shape[1])]

        y_arr = np.asarray(y, dtype=float).ravel()

        # 1. Fit median imputer on training fold
        self.imputer = SimpleImputer(strategy="median")
        X_imputed = self.imputer.fit_transform(X_arr)

        # 2. Fit RandomForestRegressor
        self.model = RandomForestRegressor(**self.params)
        self.model.fit(X_imputed, y_arr)
        self.is_fitted = True

        return self

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Predict downscaled rainfall in millimeters.
        Automatically applies fitted imputer and non-negative clamping (>= 0.0 mm).
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model has not been fitted or loaded yet.")

        if isinstance(X, pd.DataFrame):
            # Ensure columns match expected feature names if available
            if self.feature_names_ and all(c in X.columns for c in self.feature_names_):
                X_arr = X[self.feature_names_].values
            else:
                X_arr = X.values
        else:
            X_arr = np.asarray(X)

        if self.imputer is not None:
            X_imputed = self.imputer.transform(X_arr)
        else:
            X_imputed = X_arr

        preds = self.model.predict(X_imputed)
        # Rainfall cannot be physically negative
        return np.clip(preds, a_min=0.0, a_max=None)

    def get_feature_importances(self) -> List[Dict[str, Any]]:
        """
        Extract Gini feature importances ranked in descending order.
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model has not been fitted yet.")

        importances = self.model.feature_importances_
        feature_names = self.feature_names_ if self.feature_names_ else [f"feature_{i}" for i in range(len(importances))]

        ranked_indices = np.argsort(importances)[::-1]
        cumulative = 0.0
        results = []
        for rank, idx in enumerate(ranked_indices, start=1):
            imp = float(importances[idx])
            cumulative += imp
            results.append({
                "rank": rank,
                "feature": feature_names[idx],
                "importance": round(imp, 6),
                "cumulative_importance": round(cumulative, 6)
            })
        return results

    def save(self, filepath_or_dir: str, preprocessor_path: Optional[str] = None):
        """
        Serialize model and imputer artifacts to disk.
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Cannot save unfitted model.")

        if os.path.isdir(filepath_or_dir) or not filepath_or_dir.endswith(".joblib"):
            os.makedirs(filepath_or_dir, exist_ok=True)
            model_fp = os.path.join(filepath_or_dir, "best_model.joblib")
            prep_fp = os.path.join(filepath_or_dir, "preprocessor.joblib")
        else:
            model_fp = filepath_or_dir
            os.makedirs(os.path.dirname(model_fp), exist_ok=True)
            if preprocessor_path:
                prep_fp = preprocessor_path
            else:
                prep_fp = os.path.join(os.path.dirname(model_fp), "preprocessor.joblib")

        # Save model
        joblib.dump(self.model, model_fp)
        # Save imputer / feature metadata
        prep_payload = {
            "imputer": self.imputer,
            "feature_names": self.feature_names_,
            "version": self.version
        }
        joblib.dump(prep_payload, prep_fp)
        logger.info(f"Saved Random Forest model to {model_fp} and preprocessor to {prep_fp}")

    def load(self, filepath_or_dir: str, preprocessor_path: Optional[str] = None) -> "RandomForestDownscaler":
        """
        Load serialized model and preprocessor from disk.
        """
        if os.path.isdir(filepath_or_dir):
            model_fp = os.path.join(filepath_or_dir, "best_model.joblib")
            if not os.path.exists(model_fp):
                model_fp = os.path.join(filepath_or_dir, "random_forest_model.joblib")
            prep_fp = os.path.join(filepath_or_dir, "preprocessor.joblib")
            if not os.path.exists(prep_fp):
                prep_fp = os.path.join(filepath_or_dir, "random_forest_preprocessor.joblib")
        else:
            model_fp = filepath_or_dir
            if preprocessor_path:
                prep_fp = preprocessor_path
            else:
                prep_candidate = os.path.join(os.path.dirname(model_fp), "preprocessor.joblib")
                if os.path.exists(prep_candidate):
                    prep_fp = prep_candidate
                else:
                    prep_fp = os.path.join(os.path.dirname(model_fp), "random_forest_preprocessor.joblib")

        self.model = joblib.load(model_fp)
        if os.path.exists(prep_fp):
            loaded_prep = joblib.load(prep_fp)
            if isinstance(loaded_prep, dict) and "imputer" in loaded_prep:
                self.imputer = loaded_prep.get("imputer")
                self.feature_names_ = loaded_prep.get("feature_names", [])
            elif hasattr(loaded_prep, "transform"):
                self.imputer = loaded_prep
        self.is_fitted = True
        return self
