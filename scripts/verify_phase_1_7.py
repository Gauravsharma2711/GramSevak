"""
Phase 1.7 Verification Script: Idempotency, Failure Recovery, and Representative Queries.

Validates:
1. Idempotency: Re-ingesting dataset creates zero duplicates.
2. Failure Recovery: Controlled invalid batch failure safely rolls back and reports errors.
3. Representative Queries: 10 production query benchmarks across districts, blocks, panchayats, weather.
4. Generates consolidated reports/phase-1-7-ingestion.json.
"""

import os
import sys
import time
import json
import hashlib
from typing import Dict, Any, List

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.database import SessionLocal
from data_pipeline.supabase_ingestion import (
    ingest_weather_dataset,
    execute_batch_upsert,
    IngestionValidationError,
    IngestionExecutionError,
)

RAW_FILES = {
    "nashik": "data/raw/nashik/nashik_panchayat_weather_raw.csv",
    "pune": "data/raw/pune/pune_original.csv",
}

EXPECTED_CHECKSUMS = {
    "nashik": "208bb024dc49b978e1c9346c2eb941bb933a9cffdf7a4f3b84c5df3594040276",
    "pune": "8dbb31ea9e6d9b36eb951f5b980dd9d2a402108a57eeffa962ee944ba403a7a9",
}


def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_raw_data_immutability() -> Dict[str, Any]:
    results = {}
    for district, rel_path in RAW_FILES.items():
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        actual_sha = calculate_sha256(abs_path)
        expected_sha = EXPECTED_CHECKSUMS[district]
        results[district] = {
            "file": rel_path,
            "sha256": actual_sha,
            "immutable": actual_sha == expected_sha,
        }
    return results


def test_idempotency() -> Dict[str, Any]:
    print("\n--- Testing Idempotency on Nashik Dataset ---")
    db = SessionLocal()
    count_before = db.execute(text("SELECT count(*) FROM weather_observations;")).scalar()
    nashik_count_before = db.execute(text("SELECT count(*) FROM weather_observations WHERE source_dataset = 'nashik';")).scalar()
    db.close()

    # Re-run Nashik ingestion
    nashik_parquet = os.path.join(PROJECT_ROOT, "data/processed/canonical_nashik.parquet")
    ingest_weather_dataset(nashik_parquet, district="nashik", batch_size=2500)

    db = SessionLocal()
    count_after = db.execute(text("SELECT count(*) FROM weather_observations;")).scalar()
    nashik_count_after = db.execute(text("SELECT count(*) FROM weather_observations WHERE source_dataset = 'nashik';")).scalar()
    db.close()

    idempotent = (count_before == count_after) and (nashik_count_before == nashik_count_after)
    return {
        "idempotent": idempotent,
        "total_count_before": count_before,
        "total_count_after": count_after,
        "nashik_count_before": nashik_count_before,
        "nashik_count_after": nashik_count_after,
    }


def test_failure_recovery() -> Dict[str, Any]:
    print("\n--- Testing Failure Recovery & Transaction Isolation ---")
    db = SessionLocal()
    initial_count = db.execute(text("SELECT count(*) FROM weather_observations;")).scalar()
    
    # Attempt to insert an invalid batch referencing a non-existent panchayat
    raw_conn = db.connection().connection
    raw_conn.autocommit = False
    cursor = raw_conn.cursor()

    invalid_tuples = [
        (
            99999999,  # Non-existent panchayat
            999999,
            "TestStation",
            "2099-01-01",
            10.0,
            12.0,
            5.0,
            19.0,
            74.0,
            "2099-01-01",
            0,
            "test_district",
            "test_file.csv",
            0,
            "test_p",
        )
    ]

    caught_error = False
    error_message = ""
    try:
        execute_batch_upsert(cursor, invalid_tuples, max_retries=1)
        raw_conn.commit()
    except Exception as e:
        raw_conn.rollback()
        caught_error = True
        error_message = str(e)
    finally:
        cursor.close()
        raw_conn.close()
        db.close()

    db = SessionLocal()
    final_count = db.execute(text("SELECT count(*) FROM weather_observations;")).scalar()
    db.close()

    isolated = (caught_error and (initial_count == final_count))
    return {
        "error_caught": caught_error,
        "error_message": error_message,
        "database_isolated": isolated,
        "count_before": initial_count,
        "count_after": final_count,
    }


def test_representative_queries() -> Dict[str, Any]:
    print("\n--- Benchmarking Representative Queries ---")
    db = SessionLocal()
    queries = {
        "1_district_list": "SELECT id, name FROM districts ORDER BY id;",
        "2_blocks_for_pune": "SELECT id, name FROM blocks WHERE district_id = 4 ORDER BY name;",
        "3_blocks_for_nashik": "SELECT id, name FROM blocks WHERE district_id = 1 ORDER BY name;",
        "4_panchayats_for_pune_block": "SELECT id, name FROM panchayats WHERE block_id = 46 LIMIT 20;",
        "5_panchayats_for_nashik_block": "SELECT id, name FROM panchayats WHERE block_id = 1 LIMIT 20;",
        "6_weather_for_panchayat": "SELECT * FROM weather_observations WHERE panchayat_id = 1001 ORDER BY observation_date DESC LIMIT 10;",
        "7_weather_for_date_range": "SELECT * FROM weather_observations WHERE panchayat_id = 185262 AND observation_date BETWEEN '2026-05-01' AND '2026-05-31';",
        "8_forecast_by_issue_date": "SELECT * FROM weather_observations WHERE panchayat_id = 185262 AND forecast_issue_date = '2026-05-01' LIMIT 10;",
        "9_count_by_district": "SELECT source_dataset, count(*) as count FROM weather_observations GROUP BY source_dataset;",
        "10_count_by_panchayat": "SELECT panchayat_id, count(*) as count FROM weather_observations GROUP BY panchayat_id LIMIT 10;",
    }

    benchmarks = {}
    for name, sql in queries.items():
        t0 = time.perf_counter()
        res = db.execute(text(sql)).fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        benchmarks[name] = {
            "result_count": len(res),
            "elapsed_ms": round(elapsed_ms, 2),
        }
    db.close()
    return benchmarks


def main():
    print("=================================================================")
    print("  GramSevak Phase 1.7 - Full Verification & Validation Suite")
    print("=================================================================")
    
    # 1. Raw Immutability
    immutability = test_raw_data_immutability()
    all_immutable = all(d["immutable"] for d in immutability.values())
    print(f"Raw data immutability: {'PASS' if all_immutable else 'FAIL'}")

    # 2. Idempotency
    idempotency = test_idempotency()
    print(f"Idempotency verification: {'PASS' if idempotency['idempotent'] else 'FAIL'}")

    # 3. Failure Recovery
    failure_recovery = test_failure_recovery()
    print(f"Failure recovery verification: {'PASS' if failure_recovery['database_isolated'] else 'FAIL'}")

    # 4. Representative Queries
    queries_benchmarks = test_representative_queries()
    print("Representative queries benchmarked successfully.")

    # 5. Load District Ingestion Reports
    nashik_report_path = os.path.join(PROJECT_ROOT, "reports/phase-1-7-ingestion-nashik.json")
    pune_report_path = os.path.join(PROJECT_ROOT, "reports/phase-1-7-ingestion-pune.json")
    
    with open(nashik_report_path, "r", encoding="utf-8") as f:
        nashik_report = json.load(f)
    with open(pune_report_path, "r", encoding="utf-8") as f:
        pune_report = json.load(f)

    consolidated_report = {
        "phase": "1.7",
        "title": "Scalable Supabase Weather Ingestion Pipeline Validation Report",
        "timestamp": "2026-09-27T00:22:00+05:30",
        "overall_status": "PASS" if (all_immutable and idempotency["idempotent"] and failure_recovery["database_isolated"]) else "FAIL",
        "ingestions": {
            "nashik": nashik_report,
            "pune": pune_report,
        },
        "idempotency_verification": idempotency,
        "failure_recovery_verification": failure_recovery,
        "raw_data_immutability": immutability,
        "representative_query_benchmarks": queries_benchmarks,
        "total_database_observations": idempotency["total_count_after"],
    }

    report_path = os.path.join(PROJECT_ROOT, "reports/phase-1-7-ingestion.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(consolidated_report, f, indent=2)

    print(f"\nConsolidated report saved to: {report_path}")
    print(f"Overall Phase 1.7 Status: {consolidated_report['overall_status']}")


if __name__ == "__main__":
    main()
