"""
GramSevak XGBoost Downscaling Model Class (Phase 2.5).

Implements extreme gradient boosting regression for downscaling regional NWP block forecasts
to hyper-local Panchayat-level rainfall predictions.
Strictly adheres to the Phase 2.1 ML Data Contract, Phase 2.2 Feature Registry, and Phase 2.3 evaluation framework.
Enforces training-fold median imputation and non-negative precipitation clamping (>= 0.0 mm).
"""

import os
import json
import logging
from typing import Optional, Union, List, Dict, Any, Tuple
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.impute import SimpleImputer

logger = logging.getLogger("XGBoostDownscaler")


class XGBoostDownscaler:
    """
    XGBoost Regression model for downscaling Block-level rainfall forecasts
    to Panchayat-level hyper-local forecasts using spatial, terrain, and temporal features.
    
    Supports gradient boosting with early stopping on validation sets, training-fold
    median imputation for antecedent rainfall warm-up nulls, and non-negative precipitation clamping.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.03,
        subsample: float = 0.8,
        colsample_bytree: float = 0.7,
        reg_alpha: float = 1.0,
        reg_lambda: float = 5.0,
        min_child_weight: float = 20.0,
        early_stopping_rounds: Optional[int] = 15,
        random_state: int = 42,
        n_jobs: int = -1,
    ):
        self.model_name = "xgboost_downscaler"
        self.version = "2.5.0"
        self.params: Dict[str, Any] = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "min_child_weight": min_child_weight,
            "random_state": random_state,
            "n_jobs": n_jobs,
            "eval_metric": "mae"
        }
        self.early_stopping_rounds = early_stopping_rounds
        if early_stopping_rounds:
            self.params["early_stopping_rounds"] = early_stopping_rounds

        self.model: Optional[xgb.XGBRegressor] = None
        self.imputer: Optional[SimpleImputer] = None
        self.feature_names_: List[str] = []
        self.best_iteration_: Optional[int] = None
        self.best_score_: Optional[float] = None
        self.is_fitted: bool = False

    def fit(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        eval_set: Optional[List[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]]] = None,
        feature_names: Optional[List[str]] = None,
        verbose: bool = False
    ) -> "XGBoostDownscaler":
        """
        Fit SimpleImputer on training features X and train XGBRegressor.
        If eval_set is provided (e.g. validation fold), applies early stopping.
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

        # 2. Prepare validation evaluation set if provided
        formatted_eval_set = None
        if eval_set:
            formatted_eval_set = []
            for e_X, e_y in eval_set:
                if isinstance(e_X, pd.DataFrame):
                    e_X_arr = e_X[self.feature_names_].values if all(c in e_X.columns for c in self.feature_names_) else e_X.values
                else:
                    e_X_arr = np.asarray(e_X)
                e_X_imp = self.imputer.transform(e_X_arr)
                e_y_arr = np.asarray(e_y, dtype=float).ravel()
                formatted_eval_set.append((e_X_imp, e_y_arr))

        # 3. Fit XGBRegressor
        fit_params = dict(self.params)
        if not formatted_eval_set and "early_stopping_rounds" in fit_params:
            del fit_params["early_stopping_rounds"]

        self.model = xgb.XGBRegressor(**fit_params)
        self.model.fit(
            X_imputed,
            y_arr,
            eval_set=formatted_eval_set,
            verbose=verbose
        )

        if hasattr(self.model, "best_iteration") and self.model.best_iteration is not None:
            self.best_iteration_ = int(self.model.best_iteration)
        else:
            self.best_iteration_ = self.params.get("n_estimators", 100)

        if hasattr(self.model, "best_score") and self.model.best_score is not None:
            self.best_score_ = float(self.model.best_score)

        self.is_fitted = True
        return self

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Predict downscaled rainfall in millimeters.
        Automatically applies fitted median imputer and non-negative clamping (>= 0.0 mm).
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model has not been fitted or loaded yet.")

        if isinstance(X, pd.DataFrame):
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

    def get_feature_importances(self, importance_type: str = "gain") -> List[Dict[str, Any]]:
        """
        Extract feature importances ranked in descending order.
        Supports 'gain', 'weight', and 'cover'.
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model has not been fitted yet.")

        booster = self.model.get_booster()
        score_dict = booster.get_score(importance_type=importance_type)

        feature_names = self.feature_names_ if self.feature_names_ else [f"f{i}" for i in range(len(self.model.feature_importances_))]

        # Booster feature names are f0, f1... if fitted with numpy array
        mapped_scores: Dict[str, float] = {}
        for i, name in enumerate(feature_names):
            # Check direct name or f{i}
            val = score_dict.get(name, score_dict.get(f"f{i}", 0.0))
            mapped_scores[name] = float(val)

        total_score = sum(mapped_scores.values())
        if total_score > 0:
            norm_scores = {k: v / total_score for k, v in mapped_scores.items()}
        else:
            norm_scores = {k: 0.0 for k in mapped_scores}

        # Sort descending
        sorted_feats = sorted(norm_scores.items(), key=lambda x: x[1], reverse=True)
        cumulative = 0.0
        results = []
        for rank, (feat, score) in enumerate(sorted_feats, start=1):
            cumulative += score
            results.append({
                "rank": rank,
                "feature": feat,
                "importance": round(score, 6),
                "cumulative_importance": round(cumulative, 6),
                "raw_score": round(mapped_scores[feat], 4),
                "importance_type": importance_type
            })

        return results

    def save(self, filepath_or_dir: str, preprocessor_path: Optional[str] = None):
        """Serialize model, imputer, and feature metadata to disk."""
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Cannot save unfitted model.")

        if os.path.isdir(filepath_or_dir) or not filepath_or_dir.endswith(".joblib"):
            os.makedirs(filepath_or_dir, exist_ok=True)
            model_fp = os.path.join(filepath_or_dir, "model.joblib")
            prep_fp = os.path.join(filepath_or_dir, "preprocessor.joblib")
        else:
            model_fp = filepath_or_dir
            os.makedirs(os.path.dirname(model_fp), exist_ok=True)
            prep_fp = preprocessor_path if preprocessor_path else os.path.join(os.path.dirname(model_fp), "preprocessor.joblib")

        # Save model using joblib
        joblib.dump(self.model, model_fp)
        # Also save as best_model.joblib if in directory for consistent loading
        if os.path.isdir(filepath_or_dir):
            joblib.dump(self.model, os.path.join(filepath_or_dir, "best_model.joblib"))

        prep_payload = {
            "imputer": self.imputer,
            "feature_names": self.feature_names_,
            "best_iteration": self.best_iteration_,
            "best_score": self.best_score_,
            "version": self.version
        }
        joblib.dump(prep_payload, prep_fp)
        logger.info(f"Saved XGBoost model to {model_fp} and preprocessor to {prep_fp}")

    def load(self, filepath_or_dir: str, preprocessor_path: Optional[str] = None) -> "XGBoostDownscaler":
        """Load serialized model and preprocessor from disk."""
        if os.path.isdir(filepath_or_dir):
            model_fp = os.path.join(filepath_or_dir, "best_model.joblib")
            if not os.path.exists(model_fp):
                model_fp = os.path.join(filepath_or_dir, "model.joblib")
            if not os.path.exists(model_fp):
                model_fp = os.path.join(filepath_or_dir, "xgboost_model.joblib")

            prep_fp = os.path.join(filepath_or_dir, "preprocessor.joblib")
            if not os.path.exists(prep_fp):
                prep_fp = os.path.join(filepath_or_dir, "xgboost_preprocessor.joblib")
        else:
            model_fp = filepath_or_dir
            prep_fp = preprocessor_path if preprocessor_path else os.path.join(os.path.dirname(model_fp), "preprocessor.joblib")

        self.model = joblib.load(model_fp)
        if os.path.exists(prep_fp):
            loaded_prep = joblib.load(prep_fp)
            if isinstance(loaded_prep, dict) and "imputer" in loaded_prep:
                self.imputer = loaded_prep.get("imputer")
                self.feature_names_ = loaded_prep.get("feature_names", [])
                self.best_iteration_ = loaded_prep.get("best_iteration")
                self.best_score_ = loaded_prep.get("best_score")
            elif hasattr(loaded_prep, "transform"):
                self.imputer = loaded_prep

        self.is_fitted = True
        return self
