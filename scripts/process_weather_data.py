"""
GramSevak Multi-District Weather Data Processing & Ingestion CLI.

Usage Examples:
  python scripts/process_weather_data.py --district pune --dry-run
  python scripts/process_weather_data.py --district pune
  python scripts/process_weather_data.py --district nashik --dry-run
  python scripts/process_weather_data.py --district nashik

Workflow:
1. Load raw dataset safely with encoding fallback.
2. Validate raw schema and detect district configuration.
3. Normalize administrative names, casing, and data types.
4. Calculate lead_days = date - forecast_issue_date.
5. Validate coordinates, rainfall bounds, and temporal consistency.
6. Check exact and spatio-temporal duplicates.
7. Recalculate Haversine distance and audit discrepancies.
8. Generate machine-readable JSON & markdown quality reports.
9. Export canonical columnar Parquet datasets.
10. Upsert normalized administrative hierarchy and observations into Supabase PostgreSQL.
"""

import os
import sys
import json
import time
import argparse
import logging
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data_pipeline.district_config import get_district_config, DISTRICT_REGISTRY
from data_pipeline.canonical_normalizer import normalize_and_validate_dataset
from data_pipeline.parquet_exporter import export_district_to_parquet
from data_pipeline.supabase_ingestor import ingest_district_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("process_weather_data")


def parse_args():
    parser = argparse.ArgumentParser(
        description="GramSevak Multi-District Weather Normalization, Parquet & Supabase Pipeline"
    )
    parser.add_argument(
        "--district",
        type=str,
        required=True,
        help=f"Target district to process. Supported: {list(DISTRICT_REGISTRY.keys())}"
    )
    parser.add_argument(
        "--raw-path",
        type=str,
        default=None,
        help="Optional custom path to raw CSV file (overrides district default)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate validation and database upload without committing changes to Supabase"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip database upload entirely (generate Parquet and reports only)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Batch size for observation database upserts (default: 5000)"
    )
    parser.add_argument(
        "--limit-observations",
        type=int,
        default=None,
        help="Optional limit on observations to upload (useful for testing)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    district_key = args.district.strip().lower()
    
    try:
        config = get_district_config(district_key)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    raw_path = args.raw_path or config.raw_path
    if not os.path.exists(raw_path):
        logger.error(f"Raw dataset file not found at: {raw_path}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f"GRAMSEVAK WEATHER PIPELINE — DISTRICT: {config.name.upper()}")
    print("=" * 70)
    print(f"Raw Data Path : {raw_path}")
    print(f"Encoding      : {config.encoding}")
    print(f"Mode          : {'DRY RUN (No DB Writes)' if args.dry_run else ('LOCAL ONLY' if args.no_upload else 'LIVE SUPABASE UPLOAD')}")
    print("-" * 70)

    # 1. Load Raw Dataset
    logger.info(f"Loading raw dataset from {raw_path}...")
    try:
        df_raw = pd.read_csv(raw_path, encoding=config.encoding, low_memory=False)
    except UnicodeDecodeError:
        logger.warning(f"Failed with {config.encoding}, falling back to latin1...")
        df_raw = pd.read_csv(raw_path, encoding="latin1", low_memory=False)

    logger.info(f"Loaded raw dataset with {len(df_raw):,} rows and {len(df_raw.columns)} columns.")

    # 2. Normalize & Validate
    logger.info("Normalizing fields, validating coordinates, dates, rainfall, and station distances...")
    valid_df, quality_report = normalize_and_validate_dataset(df_raw, config)
    logger.info(f"Validation finished: {len(valid_df):,} valid rows, {quality_report['rejected_rows']} rejected rows.")

    # 3. Save Quality Report
    reports_dir = os.path.join(PROJECT_ROOT, "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"{district_key}_quality_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2)
    logger.info(f"Saved data quality report to {report_path}")

    # 4. Export Parquet Datasets
    logger.info("Exporting canonical columnar Parquet datasets...")
    parquet_files = export_district_to_parquet(
        df=valid_df,
        district_name=config.name,
        output_dir=os.path.join(PROJECT_ROOT, "data", "processed")
    )
    for name, p_path in parquet_files.items():
        logger.info(f"  -> {name}: {p_path}")

    # 5. Supabase Ingestion
    ingest_summary = {}
    if not args.no_upload:
        logger.info(f"Initiating Supabase Ingestion ({'DRY RUN' if args.dry_run else 'LIVE UPSERT'})...")
        ingest_summary = ingest_district_data(
            df=valid_df,
            config=config,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit_observations=args.limit_observations
        )
        import_report_path = os.path.join(reports_dir, f"{district_key}_import_report.json")
        with open(import_report_path, "w", encoding="utf-8") as f:
            json.dump(ingest_summary, f, indent=2)
        logger.info(f"Saved import summary report to {import_report_path}")

    # 6. Final Summary Display
    print("\n" + "=" * 70)
    print(f"PIPELINE SUMMARY: {config.name.upper()}")
    print("=" * 70)
    print(f"Raw Rows Loaded           : {quality_report['raw_rows']:,}")
    print(f"Valid Rows Processed      : {quality_report['valid_rows']:,}")
    print(f"Rows Rejected             : {quality_report['rejected_rows']:,}")
    print(f"Unique Panchayats         : {quality_report['unique_panchayats']:,}")
    print(f"Unique Blocks             : {quality_report['unique_blocks']:,}")
    print(f"Unique Weather Stations   : {quality_report['unique_stations']:,}")
    print(f"Date Range                : {quality_report['date_range']['min_date']} to {quality_report['date_range']['max_date']} ({quality_report['date_range']['unique_dates_count']} dates)")
    print(f"Lead Days Distribution    : {quality_report['lead_days_distribution']}")
    print(f"Exact Duplicates          : {quality_report['duplicates']['exact_duplicates']:,}")
    print(f"Panchayat/Date Duplicates : {quality_report['duplicates']['panchayat_date_duplicates']:,}")
    print(f"Max Station Discrepancy   : {quality_report['station_distance_stats']['max_discrepancy_km']} km")
    print(f"Parquet Files Generated   : {list(parquet_files.keys())}")
    
    if ingest_summary:
        print("\n--- DATABASE INGESTION STATUS ---")
        print(f"Status                    : {ingest_summary.get('status')}")
        print(f"Dry Run                   : {ingest_summary.get('dry_run')}")
        print(f"Duration                  : {ingest_summary.get('duration_seconds')} seconds")
        print(f"Entities Processed        : {ingest_summary.get('entities')}")
        if not args.dry_run:
            print(f"Inserted / Updated Rows   : {ingest_summary.get('inserted_or_updated')}")
        print(f"Message                   : {ingest_summary.get('message')}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
