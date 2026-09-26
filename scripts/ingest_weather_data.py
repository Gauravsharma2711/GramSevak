"""
CLI entrypoint for GramSevak Scalable Supabase Weather Data Ingestion (Phase 1.7).

Usage Examples:
    # Dry-run validation on Pune dataset
    python scripts/ingest_weather_data.py --district pune --dry-run

    # Ingest Nashik validated Parquet dataset
    python scripts/ingest_weather_data.py --district nashik

    # Ingest Pune validated Parquet dataset
    python scripts/ingest_weather_data.py --district pune --batch-size 2500

    # Explicit input file and custom report path
    python scripts/ingest_weather_data.py \
        --input data/processed/canonical_pune.parquet \
        --district pune \
        --batch-size 2500 \
        --report-path reports/phase-1-7-ingestion.json
"""

import os
import sys
import json
import argparse
import logging

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data_pipeline.supabase_ingestion import (
    ingest_weather_dataset,
    IngestionValidationError,
    IngestionExecutionError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
)
logger = logging.getLogger("ingest_weather_data")

DEFAULT_DISTRICT_PATHS = {
    "nashik": "data/processed/canonical_nashik.parquet",
    "pune": "data/processed/canonical_pune.parquet",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="GramSevak Scalable Supabase Weather Ingestion Pipeline (Phase 1.7)"
    )
    parser.add_argument(
        "--district",
        type=str,
        default=None,
        help="District key (e.g., 'nashik', 'pune')"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to validated canonical Parquet file (overrides default for district)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2500,
        help="Number of records per PostgreSQL upsert batch (default: 2500)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute pre-flight schema, hierarchy, and duplicate validations without modifying database"
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default="reports/phase-1-7-ingestion.json",
        help="File path to save the structured JSON ingestion report"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    if not args.district and not args.input:
        logger.error("Must specify either --district or --input")
        sys.exit(1)

    district_key = args.district.strip().lower() if args.district else None
    
    if args.input:
        input_path = os.path.abspath(args.input)
    elif district_key and district_key in DEFAULT_DISTRICT_PATHS:
        input_path = os.path.abspath(os.path.join(PROJECT_ROOT, DEFAULT_DISTRICT_PATHS[district_key]))
    else:
        logger.error(f"Unknown district '{args.district}'. Supported defaults: {list(DEFAULT_DISTRICT_PATHS.keys())}")
        sys.exit(1)

    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info("=================================================================")
    logger.info("  GramSevak Phase 1.7 - Supabase Weather Data Ingestion Engine")
    logger.info("=================================================================")
    logger.info(f"Target District : {args.district or 'Auto-detected'}")
    logger.info(f"Input Parquet   : {input_path}")
    logger.info(f"Batch Size      : {args.batch_size}")
    logger.info(f"Dry Run Mode    : {args.dry_run}")
    logger.info("-----------------------------------------------------------------")

    try:
        report = ingest_weather_dataset(
            parquet_path=input_path,
            district=args.district,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )

        # Ensure directory exists for report
        report_full_path = os.path.abspath(os.path.join(PROJECT_ROOT, args.report_path))
        os.makedirs(os.path.dirname(report_full_path), exist_ok=True)
        
        with open(report_full_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Ingestion report successfully saved to: {report_full_path}")
        logger.info(f"Overall Ingestion Status: {report['status']}")
        
        if report["status"] == "FAIL":
            sys.exit(1)

    except IngestionValidationError as ve:
        logger.error(f"Pre-ingestion validation error: {ve}")
        sys.exit(1)
    except IngestionExecutionError as ee:
        logger.error(f"Ingestion execution error: {ee}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error during ingestion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
