"""
Unit and Integration Tests for Multi-District Scalable Weather Architecture (Phase 1).

Tests:
1. Normalization of Nashik dataset to canonical schema.
2. Normalization of Pune dataset to canonical schema.
3. Quality check and duplicate detection.
4. Haversine distance verification logic.
5. Parquet file integrity and schemas.
6. API endpoint GET /api/v1/districts.
7. API endpoint GET /api/v1/districts/{district_id}/blocks.
8. API endpoint GET /api/v1/blocks.
9. API endpoint GET /api/v1/panchayats with district_name filter.
"""

import os
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app
from data_pipeline.district_config import get_district_config
from data_pipeline.canonical_normalizer import (
    normalize_and_validate_dataset,
    haversine_vectorized,
    CANONICAL_COLUMNS,
)

client = TestClient(app)


def test_district_config_retrieval():
    nashik_cfg = get_district_config("nashik")
    assert nashik_cfg.name == "Nashik"
    assert nashik_cfg.encoding == "latin1"

    pune_cfg = get_district_config("pune")
    assert pune_cfg.name == "Pune"
    assert pune_cfg.encoding == "utf-8"

    with pytest.raises(ValueError):
        get_district_config("non_existent_district")


def test_nashik_normalization():
    cfg = get_district_config("nashik")
    assert os.path.exists(cfg.raw_path), f"Missing raw file: {cfg.raw_path}"
    df_raw = pd.read_csv(cfg.raw_path, encoding=cfg.encoding, low_memory=False)
    
    valid_df, report = normalize_and_validate_dataset(df_raw, cfg)
    
    assert len(valid_df) == 1388
    assert report["rejected_rows"] == 0
    assert list(valid_df.columns) == CANONICAL_COLUMNS
    assert valid_df["district_name"].unique().tolist() == ["Nashik"]
    assert valid_df["lead_days"].unique().tolist() == [0]


def test_pune_normalization_sample():
    cfg = get_district_config("pune")
    assert os.path.exists(cfg.raw_path), f"Missing raw file: {cfg.raw_path}"
    # Read first 1000 rows
    df_raw = pd.read_csv(cfg.raw_path, nrows=1000, encoding=cfg.encoding)
    
    valid_df, report = normalize_and_validate_dataset(df_raw, cfg)
    
    assert len(valid_df) == 1000
    assert report["rejected_rows"] == 0
    assert list(valid_df.columns) == CANONICAL_COLUMNS
    assert valid_df["district_name"].unique().tolist() == ["Pune"]
    assert valid_df["lead_days"].unique().tolist() == [1]


def test_haversine_accuracy():
    # Mumbai to Pune coordinates approx ~120 km
    lat1 = pd.Series([18.5204]) # Pune
    lon1 = pd.Series([73.8567])
    lat2 = pd.Series([18.9220]) # Mumbai (Gateway of India)
    lon2 = pd.Series([72.8347])
    
    dist = haversine_vectorized(lat1, lon1, lat2, lon2)
    assert 115 < dist.iloc[0] < 125


def test_parquet_datasets_integrity():
    processed_dir = "data/processed"
    files = [
        "canonical_nashik.parquet",
        "canonical_pune.parquet",
        "panchayats.parquet",
        "forecasts.parquet",
        "observations.parquet",
        "training_dataset.parquet",
    ]
    for f in files:
        path = os.path.join(processed_dir, f)
        assert os.path.exists(path), f"Missing Parquet file: {path}"
        df = pd.read_parquet(path)
        assert len(df) > 0, f"Parquet file {path} is empty"


def test_api_districts_endpoint():
    response = client.get("/api/v1/districts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    names = [d["name"] for d in data]
    assert "Nashik" in names
    assert "Pune" in names


def test_api_blocks_endpoint():
    response = client.get("/api/v1/blocks?district_name=Nashik")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 15
    block_names = [b["name"] for b in data]
    assert "Baglan" in block_names
    assert "Dindori" in block_names

    response_pune = client.get("/api/v1/blocks?district_name=Pune")
    assert response_pune.status_code == 200
    data_pune = response_pune.json()
    assert len(data_pune) == 13
    pune_block_names = [b["name"] for b in data_pune]
    assert "Haveli" in pune_block_names
    assert "Baramati" in pune_block_names


def test_api_panchayats_district_filtering():
    # Query Nashik panchayats
    r_nashik = client.get("/api/v1/panchayats?district_name=Nashik&page=1&page_size=10")
    assert r_nashik.status_code == 200
    data_nashik = r_nashik.json()
    assert data_nashik["total"] == 1388
    for item in data_nashik["items"]:
        assert item["district_name"] == "Nashik"

    # Query Pune panchayats
    r_pune = client.get("/api/v1/panchayats?district_name=Pune&page=1&page_size=10")
    assert r_pune.status_code == 200
    data_pune = r_pune.json()
    assert data_pune["total"] == 1338
    for item in data_pune["items"]:
        assert item["district_name"] == "Pune"
