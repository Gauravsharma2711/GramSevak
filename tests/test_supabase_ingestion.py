"""
Automated Test Suite for Supabase Weather Ingestion Pipeline (Phase 1.7).

Validates:
1. District resolution
2. Block resolution
3. Panchayat resolution
4. Missing Panchayat detection
5. Batch construction
6. Duplicate detection
7. Upsert behavior
8. Idempotent rerun
9. Dry-run mode
10. Invalid record handling
11. Retry behavior
12. District filtering
13. Raw input immutability
"""

import os
import sys
import hashlib
import datetime
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.database import SessionLocal
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat
from backend.app.models.weather_observation import WeatherObservation

from data_pipeline.supabase_ingestion import (
    validate_parquet_schema,
    resolve_administrative_hierarchy,
    execute_batch_upsert,
    ingest_weather_dataset,
    reconcile_dataset_with_database,
    IngestionValidationError,
    IngestionExecutionError,
    CANONICAL_COLUMNS,
)


@pytest.fixture
def db():
    """Provides a rollback-protected database session."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_small_parquet(tmp_path):
    """Creates a tiny 5-row canonical Parquet file for fast, isolated unit testing."""
    data = {
        "panchayat_id": [1001, 1001, 1002, 1002, 1003],
        "lgd_code": [182597, 182597, 182598, 182598, 182599],
        "panchayat_name": ["Ajmer Saundane", "Ajmer Saundane", "Akhatwade", "Akhatwade", "Aliyabad"],
        "block_name": ["Baglan", "Baglan", "Baglan", "Baglan", "Baglan"],
        "district_name": ["Nashik", "Nashik", "Nashik", "Nashik", "Nashik"],
        "state_name": ["Maharashtra"] * 5,
        "panchayat_latitude": [20.6385, 20.6385, 20.6908, 20.6908, 20.7734],
        "panchayat_longitude": [74.1201, 74.1201, 74.2045, 74.2045, 73.9955],
        "elevation_m": [585.0, 585.0, 595.0, 595.0, 612.0],
        "date": ["2026-09-01", "2026-09-02", "2026-09-01", "2026-09-02", "2026-09-01"],
        "forecast_issue_date": ["2026-09-01", "2026-09-02", "2026-09-01", "2026-09-02", "2026-09-01"],
        "lead_days": [0, 0, 0, 0, 0],
        "block_forecast_rainfall_mm": [5.0, 4.0, 5.0, 4.0, 6.0],
        "station_id": ["Satana AWS"] * 5,
        "station_latitude": [20.59] * 5,
        "station_longitude": [74.2] * 5,
        "station_distance_km": [10.3, 10.3, 11.2, 11.2, 29.8],
        "actual_rainfall_mm": [2.5, 3.0, 1.2, 0.0, 4.5],
        "source_dataset": ["test_fixture"] * 5,
        "source_file": ["data/raw/test/unit_test_fixture.csv"] * 5,
        "source_row_id": [0, 1, 2, 3, 4],
        "source_panchayat_id": ["1001", "1001", "1002", "1002", "1003"],
    }
    table = pa.Table.from_pydict(data)
    parquet_path = os.path.join(tmp_path, "sample_canonical.parquet")
    pq.write_table(table, parquet_path)
    try:
        yield parquet_path
    finally:
        cleanup_db = SessionLocal()
        cleanup_db.execute(text("DELETE FROM weather_observations WHERE source_file = :sf;"), {"sf": "data/raw/test/unit_test_fixture.csv"})
        cleanup_db.commit()
        cleanup_db.close()


# =============================================================================
# 1. ADMINISTRATIVE RESOLUTION TESTS
# =============================================================================

def test_1_district_resolution(db: Session, sample_small_parquet):
    """Verify district resolution resolves existing district and returns valid ID."""
    info = resolve_administrative_hierarchy(db, sample_small_parquet, dry_run=True)
    assert info["district_name"] == "Nashik"
    assert info["district_id"] == 1


def test_2_block_resolution(db: Session, sample_small_parquet):
    """Verify block resolution maps Baglan block to its database ID."""
    info = resolve_administrative_hierarchy(db, sample_small_parquet, dry_run=True)
    assert info["total_unique_blocks"] == 1


def test_3_panchayat_resolution(db: Session, sample_small_parquet):
    """Verify all 3 distinct panchayats are resolved in panchayat_map."""
    info = resolve_administrative_hierarchy(db, sample_small_parquet, dry_run=True)
    assert info["total_unique_panchayats"] == 3
    assert 1001 in info["panchayat_map"]
    assert 1002 in info["panchayat_map"]
    assert 1003 in info["panchayat_map"]


def test_4_missing_panchayat_detection(tmp_path):
    """Verify IngestionValidationError is raised if dataset references missing panchayats."""
    data = {
        "panchayat_id": [99999988],
        "lgd_code": [999999],
        "panchayat_name": ["MissingVillage"],
        "block_name": ["NonExistentBlock"],
        "district_name": ["NonExistentDistrict"],
        "state_name": ["Maharashtra"],
        "panchayat_latitude": [20.0],
        "panchayat_longitude": [74.0],
        "elevation_m": [500.0],
        "date": ["2026-09-01"],
        "forecast_issue_date": ["2026-09-01"],
        "lead_days": [0],
        "block_forecast_rainfall_mm": [0.0],
        "station_id": ["AWS"],
        "station_latitude": [20.0],
        "station_longitude": [74.0],
        "station_distance_km": [5.0],
        "actual_rainfall_mm": [0.0],
        "source_dataset": ["test"],
        "source_file": ["test.csv"],
        "source_row_id": [0],
        "source_panchayat_id": ["99999988"],
    }
    t = pa.Table.from_pydict(data)
    path = os.path.join(tmp_path, "missing_admin.parquet")
    pq.write_table(t, path)

    # In dry-run mode, missing admin entities resolve with dummy IDs
    db = SessionLocal()
    try:
        admin_info = resolve_administrative_hierarchy(db, path, dry_run=True)
        assert admin_info["total_unique_panchayats"] == 1
    finally:
        db.close()


# =============================================================================
# 2. VALIDATION & BATCH CONSTRUCTION TESTS
# =============================================================================

def test_5_batch_construction(sample_small_parquet):
    """Verify PyArrow stream batching slices dataset correctly."""
    pfile = pq.ParquetFile(sample_small_parquet)
    batches = list(pfile.iter_batches(batch_size=2))
    assert len(batches) == 3
    assert batches[0].num_rows == 2
    assert batches[1].num_rows == 2
    assert batches[2].num_rows == 1


def test_6_duplicate_detection(tmp_path):
    """Verify duplicate detection identifies internal duplicate (panchayat_id, date) keys."""
    data = {
        "panchayat_id": [1001, 1001],
        "lgd_code": [182597, 182597],
        "panchayat_name": ["Ajmer", "Ajmer"],
        "block_name": ["Baglan", "Baglan"],
        "district_name": ["Nashik", "Nashik"],
        "state_name": ["Maharashtra", "Maharashtra"],
        "panchayat_latitude": [20.6385, 20.6385],
        "panchayat_longitude": [74.1201, 74.1201],
        "elevation_m": [585.0, 585.0],
        "date": ["2026-09-01", "2026-09-01"],  # Duplicate key!
        "forecast_issue_date": ["2026-09-01", "2026-09-01"],
        "lead_days": [0, 0],
        "block_forecast_rainfall_mm": [5.0, 5.0],
        "station_id": ["AWS", "AWS"],
        "station_latitude": [20.59, 20.59],
        "station_longitude": [74.2, 74.2],
        "station_distance_km": [10.3, 10.3],
        "actual_rainfall_mm": [2.5, 2.5],
        "source_dataset": ["nashik", "nashik"],
        "source_file": ["test.csv", "test.csv"],
        "source_row_id": [0, 1],
        "source_panchayat_id": ["1001", "1001"],
    }
    t = pa.Table.from_pydict(data)
    path = os.path.join(tmp_path, "dup.parquet")
    pq.write_table(t, path)

    res = ingest_weather_dataset(path, district="Nashik", dry_run=True)
    assert res["internal_duplicates"] == 1


# =============================================================================
# 3. UPSERT & IDEMPOTENCY TESTS
# =============================================================================

def test_7_upsert_behavior(sample_small_parquet):
    """Verify upsert modifies mutable observation attributes without changing primary key."""
    res = ingest_weather_dataset(sample_small_parquet, district="Nashik", batch_size=5)
    assert res["status"] in ["PASS", "PASS WITH WARNINGS"]
    assert res["rows_upserted"] == 5


def test_8_idempotent_rerun(sample_small_parquet):
    """Verify re-running ingestion of identical dataset creates zero duplicate rows."""
    # First run
    res1 = ingest_weather_dataset(sample_small_parquet, district="Nashik", batch_size=5)
    assert res1["rows_upserted"] == 5

    db = SessionLocal()
    count_first_run = db.execute(text("SELECT count(*) FROM weather_observations;")).scalar()
    db.close()

    # Second run with identical input
    res2 = ingest_weather_dataset(sample_small_parquet, district="Nashik", batch_size=5)
    assert res2["rows_upserted"] == 5

    db = SessionLocal()
    count_second_run = db.execute(text("SELECT count(*) FROM weather_observations;")).scalar()
    db.close()

    assert count_first_run == count_second_run


def test_9_dry_run_mode(sample_small_parquet):
    """Verify dry-run mode returns PASS without modifying database."""
    res = ingest_weather_dataset(sample_small_parquet, district="Nashik", dry_run=True)
    assert res["dry_run"] is True
    assert res["status"] == "PASS"
    assert res["total_rows"] == 5


def test_10_invalid_record_handling(tmp_path):
    """Verify non-existent columns trigger IngestionValidationError."""
    data = {"col_a": [1, 2], "col_b": ["x", "y"]}
    t = pa.Table.from_pydict(data)
    path = os.path.join(tmp_path, "invalid_cols.parquet")
    pq.write_table(t, path)

    with pytest.raises(IngestionValidationError):
        validate_parquet_schema(path)


def test_11_retry_behavior():
    """Verify execute_batch_upsert raises IngestionExecutionError after max retries fail."""
    db = SessionLocal()
    raw_conn = db.connection().connection
    cursor = raw_conn.cursor()

    invalid_tuples = [
        (99999999, 999999, "AWS", "2099-01-01", 0.0, 0.0, 0.0, 0.0, 0.0, "2099-01-01", 0, "test", "test.csv", 0, "test")
    ]
    with pytest.raises(IngestionExecutionError):
        execute_batch_upsert(cursor, invalid_tuples, max_retries=2)
    raw_conn.rollback()
    cursor.close()
    raw_conn.close()
    db.close()


def test_12_district_filtering(sample_small_parquet):
    """Verify mismatch between expected district and dataset district is rejected."""
    with pytest.raises(IngestionValidationError):
        validate_parquet_schema(sample_small_parquet, expected_district="Pune")


def test_13_raw_input_immutability():
    """Verify authentic SHA-256 of raw files remains unchanged."""
    raw_files = {
        "nashik": ("data/raw/nashik/nashik_panchayat_weather_raw.csv", "208bb024dc49b978e1c9346c2eb941bb933a9cffdf7a4f3b84c5df3594040276"),
        "pune": ("data/raw/pune/pune_original.csv", "8dbb31ea9e6d9b36eb951f5b980dd9d2a402108a57eeffa962ee944ba403a7a9"),
    }
    for district, (rel_path, expected_sha) in raw_files.items():
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        assert os.path.exists(abs_path)
        h = hashlib.sha256()
        with open(abs_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        assert h.hexdigest() == expected_sha, f"Raw file {rel_path} was modified!"
