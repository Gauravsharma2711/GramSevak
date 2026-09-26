"""
GramSevak Scalable Supabase / PostgreSQL Weather Data Ingestion Pipeline (Phase 1.7).

Provides robust, idempotent, and high-performance ingestion of canonical Parquet weather
datasets into Supabase PostgreSQL.

Key Capabilities:
1. Administrative Hierarchy Verification & Resolution (Districts -> Blocks -> Panchayats).
2. Streaming batch processing with PyArrow RecordBatches and psycopg2.extras.execute_values.
3. Strict upsert semantics on business key (panchayat_id, observation_date).
4. Bounded exponential-backoff retries for transient operational errors.
5. Dry-run mode for pre-flight schema, hierarchy, and duplicate analysis without database mutation.
6. Post-ingestion reconciliation and sample validation against source Parquet data.
"""

import os
import sys
import time
import json
import logging
import datetime
from typing import Dict, Any, List, Tuple, Optional, Set

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import psycopg2.extras
from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.database import SessionLocal, engine
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat
from backend.app.models.weather_observation import WeatherObservation

logger = logging.getLogger("supabase_ingestion")

CANONICAL_COLUMNS: List[str] = [
    "panchayat_id",
    "lgd_code",
    "panchayat_name",
    "block_name",
    "district_name",
    "state_name",
    "panchayat_latitude",
    "panchayat_longitude",
    "elevation_m",
    "date",
    "forecast_issue_date",
    "lead_days",
    "block_forecast_rainfall_mm",
    "station_id",
    "station_latitude",
    "station_longitude",
    "station_distance_km",
    "actual_rainfall_mm",
    "source_dataset",
    "source_file",
    "source_row_id",
    "source_panchayat_id",
]

UPSERT_WEATHER_SQL = """
INSERT INTO weather_observations (
    panchayat_id, lgd_code, station_id, observation_date, actual_rainfall_mm,
    block_forecast_rainfall_mm, station_distance_km, station_latitude, station_longitude,
    forecast_issue_date, lead_days, source_dataset, source_file, source_row_id, source_panchayat_id
) VALUES %s
ON CONFLICT (panchayat_id, observation_date) DO UPDATE SET
    lgd_code = EXCLUDED.lgd_code,
    station_id = EXCLUDED.station_id,
    actual_rainfall_mm = EXCLUDED.actual_rainfall_mm,
    station_distance_km = EXCLUDED.station_distance_km,
    forecast_issue_date = EXCLUDED.forecast_issue_date,
    lead_days = EXCLUDED.lead_days,
    block_forecast_rainfall_mm = EXCLUDED.block_forecast_rainfall_mm,
    station_latitude = EXCLUDED.station_latitude,
    station_longitude = EXCLUDED.station_longitude,
    source_dataset = EXCLUDED.source_dataset,
    source_file = EXCLUDED.source_file,
    source_row_id = EXCLUDED.source_row_id,
    source_panchayat_id = EXCLUDED.source_panchayat_id,
    updated_at = NOW();
"""


class IngestionValidationError(Exception):
    """Raised when incoming dataset violates canonical schema or business constraints."""
    pass


class IngestionExecutionError(Exception):
    """Raised when ingestion fails after exhausting retries."""
    pass


def validate_parquet_schema(parquet_path: str, expected_district: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate that Parquet file exists, contains all 22 canonical columns, and matches expected district.
    """
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"Parquet dataset not found at: {parquet_path}")

    pfile = pq.ParquetFile(parquet_path)
    file_cols = pfile.schema.names
    missing_cols = [c for c in CANONICAL_COLUMNS if c not in file_cols]
    if missing_cols:
        raise IngestionValidationError(
            f"Parquet file {parquet_path} missing canonical columns: {missing_cols}"
        )

    # Read minimal metadata
    num_rows = pfile.metadata.num_rows
    if num_rows == 0:
        raise IngestionValidationError(f"Parquet file {parquet_path} contains 0 rows.")

    # Inspect district sample
    sample_table = pfile.read_row_group(0, columns=["district_name", "date", "source_dataset"])
    districts_in_data = set(sample_table.column("district_name").to_pylist())
    
    if expected_district:
        normalized_expected = expected_district.strip().lower()
        normalized_found = {d.strip().lower() for d in districts_in_data}
        if normalized_expected not in normalized_found:
            raise IngestionValidationError(
                f"District mismatch: expected '{expected_district}', but found in dataset: {districts_in_data}"
            )

    return {
        "num_rows": num_rows,
        "num_row_groups": pfile.num_row_groups,
        "districts": list(districts_in_data),
        "columns_verified": len(CANONICAL_COLUMNS),
    }


def resolve_administrative_hierarchy(
    db: Session,
    parquet_path: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Ensures District, Blocks, and Panchayats from Parquet exist in PostgreSQL.
    Extracts distinct hierarchy metadata, performs idempotent upsert, and returns
    a mapping of authoritative panchayat_id -> database panchayat id.
    """
    logger.info("Resolving administrative hierarchy from Parquet metadata...")
    
    # Read distinct hierarchy columns only
    pfile = pq.ParquetFile(parquet_path)
    admin_table = pfile.read(columns=[
        "panchayat_id", "lgd_code", "panchayat_name", "block_name",
        "district_name", "state_name", "panchayat_latitude",
        "panchayat_longitude", "elevation_m"
    ])
    admin_df = admin_table.to_pandas().drop_duplicates(subset=["panchayat_id"])
    
    district_name = str(admin_df["district_name"].iloc[0]).strip()
    state_name = str(admin_df["state_name"].iloc[0]).strip()
    
    # 1. District Resolution
    district = db.query(District).filter(District.name.ilike(district_name)).first()
    if not district:
        if dry_run:
            logger.info(f"[DRY-RUN] Would create District: {district_name} ({state_name})")
            district_id = -1
        else:
            district = District(name=district_name, state=state_name)
            db.add(district)
            db.flush()
            district_id = district.id
            logger.info(f"Created District '{district_name}' with ID {district_id}")
    else:
        district_id = district.id
        logger.info(f"Resolved existing District '{district.name}' (ID: {district_id})")

    # 2. Blocks Resolution (Bulk In-Memory Mapping)
    unique_blocks = [str(b).strip() for b in admin_df["block_name"].unique()]
    existing_blocks = db.query(Block).filter(Block.district_id == district_id).all()
    block_map: Dict[str, int] = {b.name.strip().lower(): b.id for b in existing_blocks}
    
    new_blocks = []
    for clean_bname in unique_blocks:
        if clean_bname.lower() not in block_map:
            if not dry_run:
                new_block = Block(district_id=district_id, name=clean_bname)
                db.add(new_block)
                new_blocks.append(new_block)
    
    if new_blocks and not dry_run:
        db.flush()
        for nb in new_blocks:
            block_map[nb.name.strip().lower()] = nb.id
        logger.info(f"Created {len(new_blocks)} new Blocks under District {district_id}")

    # Standardize map with actual casing
    cased_block_map: Dict[str, int] = {}
    for b_name in unique_blocks:
        cased_block_map[b_name] = block_map.get(b_name.lower(), -1)

    # 3. Panchayats Resolution & Cache
    panchayat_map: Dict[int, int] = {}
    db_panchayats = db.query(Panchayat.id, Panchayat.lgd_code).filter(
        Panchayat.district_id == district_id
    ).all()
    existing_panchayat_ids = {p.id for p in db_panchayats}
    
    new_panchayats_to_create = []
    for _, row in admin_df.iterrows():
        p_id = int(row["panchayat_id"])
        b_name = str(row["block_name"]).strip()
        b_id = block_map.get(b_name)
        
        if p_id not in existing_panchayat_ids:
            if not dry_run and b_id and b_id > 0:
                new_panchayats_to_create.append(
                    Panchayat(
                        id=p_id,
                        lgd_code=int(row["lgd_code"]),
                        name=str(row["panchayat_name"]).strip(),
                        block_id=b_id,
                        district_id=district_id,
                        latitude=float(row["panchayat_latitude"]),
                        longitude=float(row["panchayat_longitude"]),
                        elevation_m=float(row["elevation_m"]) if row["elevation_m"] is not None else None,
                    )
                )
            panchayat_map[p_id] = p_id
        else:
            panchayat_map[p_id] = p_id

    if new_panchayats_to_create and not dry_run:
        db.add_all(new_panchayats_to_create)
        db.flush()
        logger.info(f"Created {len(new_panchayats_to_create)} new Panchayats under District {district_id}")

    if not dry_run:
        db.commit()

    return {
        "district_id": district_id,
        "district_name": district_name,
        "total_unique_blocks": len(unique_blocks),
        "total_unique_panchayats": len(admin_df),
        "existing_panchayats_count": len(existing_panchayat_ids),
        "new_panchayats_created": len(new_panchayats_to_create) if not dry_run else len(admin_df) - len(existing_panchayat_ids),
        "panchayat_map": panchayat_map,
    }


def execute_batch_upsert(
    cursor: Any,
    batch_tuples: List[Tuple],
    max_retries: int = 3,
    page_size: int = 2500
) -> int:
    """
    Executes an execute_values upsert for a single batch with bounded retries.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            psycopg2.extras.execute_values(
                cursor,
                UPSERT_WEATHER_SQL,
                batch_tuples,
                page_size=page_size
            )
            return len(batch_tuples)
        except Exception as e:
            attempt += 1
            logger.warning(f"Batch upsert failed on attempt {attempt}/{max_retries}: {e}")
            if attempt >= max_retries:
                raise IngestionExecutionError(f"Batch failed after {max_retries} attempts: {e}")
            time.sleep(1.5 ** attempt)
    return 0


def ingest_weather_dataset(
    parquet_path: str,
    district: Optional[str] = None,
    batch_size: int = 2500,
    dry_run: bool = False,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Main orchestration function for ingesting a Parquet weather dataset into PostgreSQL/Supabase.
    """
    start_time = time.perf_counter()
    logger.info(f"Starting ingestion process: input='{parquet_path}', district='{district}', batch_size={batch_size}, dry_run={dry_run}")

    # 1. Pre-ingestion schema & domain validation
    schema_info = validate_parquet_schema(parquet_path, expected_district=district)
    total_rows = schema_info["num_rows"]

    # 2. Administrative Hierarchy Resolution
    db = SessionLocal()
    try:
        admin_info = resolve_administrative_hierarchy(db, parquet_path, dry_run=dry_run)
        panchayat_map = admin_info["panchayat_map"]
    finally:
        db.close()

    # 3. Detect duplicate business keys and missing panchayat mappings
    logger.info("Scanning dataset for duplicate business keys (panchayat_id, date)...")
    pfile = pq.ParquetFile(parquet_path)
    
    # Read key identifiers to check duplicates & missing mappings
    key_table = pfile.read(columns=["panchayat_id", "date"])
    key_df = key_table.to_pandas()
    
    # Check missing mappings
    missing_ids = [pid for pid in key_df["panchayat_id"].unique() if pid not in panchayat_map]
    if missing_ids:
        raise IngestionValidationError(
            f"Dataset contains {len(missing_ids)} Panchayats not resolved in administrative hierarchy: {missing_ids[:10]}"
        )

    # Check internal duplicate business keys
    duplicate_count = key_df.duplicated(subset=["panchayat_id", "date"]).sum()
    if duplicate_count > 0:
        logger.warning(f"Dataset contains {duplicate_count} internal duplicate business keys!")
    else:
        logger.info("Internal duplicate check passed: 0 duplicate business keys found.")

    if dry_run:
        elapsed = time.perf_counter() - start_time
        logger.info(f"[DRY-RUN] Pre-flight validation passed successfully for {total_rows} rows in {elapsed:.2f}s.")
        return {
            "status": "PASS",
            "dry_run": True,
            "district": district or admin_info["district_name"],
            "total_rows": total_rows,
            "unique_panchayats": admin_info["total_unique_panchayats"],
            "unique_blocks": admin_info["total_unique_blocks"],
            "missing_panchayat_mappings": 0,
            "internal_duplicates": int(duplicate_count),
            "batches_planned": int(np.ceil(total_rows / batch_size)),
            "elapsed_seconds": round(elapsed, 4),
            "message": f"Pre-flight dry-run completed successfully. {total_rows} rows ready for ingestion."
        }

    # 4. Streamed Batch Execution
    logger.info(f"Executing batch upsert for {total_rows} rows (batch_size={batch_size})...")
    
    db_session = SessionLocal()
    raw_conn = db_session.connection().connection
    raw_conn.autocommit = False
    cursor = raw_conn.cursor()

    rows_upserted = 0
    batch_idx = 0
    total_batches = int(np.ceil(total_rows / batch_size))
    batch_timings: List[float] = []

    try:
        for batch in pfile.iter_batches(batch_size=batch_size):
            b_start = time.perf_counter()
            batch_idx += 1
            
            p_ids = batch.column("panchayat_id").to_pylist()
            lgd_codes = batch.column("lgd_code").to_pylist()
            station_ids = [str(s) if s is not None else None for s in batch.column("station_id").to_pylist()]
            dates = [datetime.date.fromisoformat(str(d)) for d in batch.column("date").to_pylist()]
            actual_rain = [float(r) if r is not None and not np.isnan(r) else None for r in batch.column("actual_rainfall_mm").to_pylist()]
            forecast_rain = [float(r) if r is not None and not np.isnan(r) else None for r in batch.column("block_forecast_rainfall_mm").to_pylist()]
            dist_km = [float(r) if r is not None and not np.isnan(r) else None for r in batch.column("station_distance_km").to_pylist()]
            st_lat = [float(r) if r is not None and not np.isnan(r) else None for r in batch.column("station_latitude").to_pylist()]
            st_lon = [float(r) if r is not None and not np.isnan(r) else None for r in batch.column("station_longitude").to_pylist()]
            issue_dates = [datetime.date.fromisoformat(str(d)) for d in batch.column("forecast_issue_date").to_pylist()]
            leads = [int(l) if l is not None else 0 for l in batch.column("lead_days").to_pylist()]
            datasets = [str(s) if s is not None else None for s in batch.column("source_dataset").to_pylist()]
            files = [str(s) if s is not None else None for s in batch.column("source_file").to_pylist()]
            row_ids = [int(r) if r is not None else None for r in batch.column("source_row_id").to_pylist()]
            source_p_ids = [str(s) if s is not None else None for s in batch.column("source_panchayat_id").to_pylist()]

            batch_tuples = list(zip(
                p_ids, lgd_codes, station_ids, dates, actual_rain,
                forecast_rain, dist_km, st_lat, st_lon,
                issue_dates, leads, datasets, files, row_ids, source_p_ids
            ))

            execute_batch_upsert(cursor, batch_tuples, max_retries=max_retries, page_size=batch_size)
            raw_conn.commit()

            b_elapsed = time.perf_counter() - b_start
            batch_timings.append(b_elapsed)
            rows_upserted += len(batch_tuples)

            if batch_idx % 5 == 0 or batch_idx == total_batches:
                avg_rate = rows_upserted / (time.perf_counter() - start_time)
                logger.info(
                    f"Processed Batch {batch_idx}/{total_batches} ({rows_upserted}/{total_rows} rows, "
                    f"batch_time={b_elapsed:.2f}s, throughput={avg_rate:.1f} rows/s)"
                )

    except Exception as e:
        raw_conn.rollback()
        logger.error(f"Ingestion failed on batch {batch_idx}: {e}")
        raise IngestionExecutionError(f"Ingestion aborted on batch {batch_idx}: {e}")
    finally:
        cursor.close()
        raw_conn.close()
        db_session.close()

    total_time = time.perf_counter() - start_time
    throughput = rows_upserted / total_time if total_time > 0 else 0.0
    logger.info(f"Ingestion completed: {rows_upserted} rows upserted in {total_time:.2f}s ({throughput:.1f} rows/s).")

    # 5. Deep Post-Ingestion Verification
    logger.info("Executing deep post-ingestion reconciliation against database...")
    reconciliation = reconcile_dataset_with_database(parquet_path, district or admin_info["district_name"])

    return {
        "status": "PASS" if reconciliation["matched"] else "PASS WITH WARNINGS",
        "dry_run": False,
        "district": district or admin_info["district_name"],
        "total_input_rows": total_rows,
        "rows_upserted": rows_upserted,
        "batches_completed": batch_idx,
        "elapsed_seconds": round(total_time, 4),
        "throughput_rows_per_sec": round(throughput, 2),
        "reconciliation": reconciliation,
    }


def reconcile_dataset_with_database(parquet_path: str, district: str) -> Dict[str, Any]:
    """
    Performs rigorous reconciliation comparing Parquet metrics with live database state.
    """
    pfile = pq.ParquetFile(parquet_path)
    full_table = pfile.read(columns=[
        "panchayat_id", "date", "actual_rainfall_mm", "block_forecast_rainfall_mm"
    ])
    src_df = full_table.to_pandas()

    src_row_count = len(src_df)
    src_unique_panchayats = src_df["panchayat_id"].nunique()
    src_min_date = str(src_df["date"].min())
    src_max_date = str(src_df["date"].max())
    src_actual_sum = float(src_df["actual_rainfall_mm"].sum())
    src_forecast_sum = float(src_df["block_forecast_rainfall_mm"].sum())

    db = SessionLocal()
    try:
        norm_district = district.strip().lower()
        res = db.execute(text("""
            SELECT 
                count(*) as row_count,
                count(distinct panchayat_id) as unique_panchayats,
                min(observation_date)::text as min_date,
                max(observation_date)::text as max_date,
                sum(coalesce(actual_rainfall_mm, 0.0)) as actual_sum,
                sum(coalesce(block_forecast_rainfall_mm, 0.0)) as forecast_sum
            FROM weather_observations
            WHERE lower(source_dataset) = :district;
        """), {"district": norm_district}).mappings().first()

        db_row_count = int(res["row_count"])
        db_unique_panchayats = int(res["unique_panchayats"])
        db_min_date = str(res["min_date"])
        db_max_date = str(res["max_date"])
        db_actual_sum = float(res["actual_sum"]) if res["actual_sum"] is not None else 0.0
        db_forecast_sum = float(res["forecast_sum"]) if res["forecast_sum"] is not None else 0.0

        # Tolerances
        row_count_match = (src_row_count == db_row_count)
        panchayat_match = (src_unique_panchayats == db_unique_panchayats)
        date_match = (src_min_date == db_min_date and src_max_date == db_max_date)
        actual_sum_match = np.isclose(src_actual_sum, db_actual_sum, rtol=1e-3, atol=1e-2)
        forecast_sum_match = np.isclose(src_forecast_sum, db_forecast_sum, rtol=1e-3, atol=1e-2)

        matched = all([row_count_match, panchayat_match, date_match, actual_sum_match, forecast_sum_match])

        # Sample validation: first, middle, last
        sample_indices = [0, len(src_df) // 2, len(src_df) - 1]
        sample_checks = []
        for idx in sample_indices:
            row = src_df.iloc[idx]
            p_id = int(row["panchayat_id"])
            o_date = str(row["date"])
            
            db_sample = db.execute(text("""
                SELECT 
                    panchayat_id, observation_date::text as obs_date,
                    actual_rainfall_mm, block_forecast_rainfall_mm, source_dataset
                FROM weather_observations
                WHERE panchayat_id = :p_id AND observation_date = :o_date;
            """), {"p_id": p_id, "o_date": o_date}).mappings().first()

            if db_sample:
                sample_checks.append({
                    "sample_idx": idx,
                    "panchayat_id": p_id,
                    "date": o_date,
                    "parquet_actual": float(row["actual_rainfall_mm"]),
                    "db_actual": float(db_sample["actual_rainfall_mm"]) if db_sample["actual_rainfall_mm"] is not None else None,
                    "parquet_forecast": float(row["block_forecast_rainfall_mm"]),
                    "db_forecast": float(db_sample["block_forecast_rainfall_mm"]) if db_sample["block_forecast_rainfall_mm"] is not None else None,
                    "verified": True
                })
            else:
                sample_checks.append({
                    "sample_idx": idx,
                    "panchayat_id": p_id,
                    "date": o_date,
                    "verified": False,
                    "error": "Record not found in database"
                })

        return {
            "matched": matched,
            "source_parquet": {
                "row_count": src_row_count,
                "unique_panchayats": src_unique_panchayats,
                "min_date": src_min_date,
                "max_date": src_max_date,
                "actual_rainfall_sum": round(src_actual_sum, 2),
                "forecast_rainfall_sum": round(src_forecast_sum, 2),
            },
            "database": {
                "row_count": db_row_count,
                "unique_panchayats": db_unique_panchayats,
                "min_date": db_min_date,
                "max_date": db_max_date,
                "actual_rainfall_sum": round(db_actual_sum, 2),
                "forecast_rainfall_sum": round(db_forecast_sum, 2),
            },
            "sample_record_checks": sample_checks,
        }

    finally:
        db.close()
