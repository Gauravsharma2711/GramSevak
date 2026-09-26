"""
CLI entrypoint for GramSevak Validated Parquet Weather Pipeline (Phase 1.5).

Usage Examples:
    # Convert Nashik normalized CSV to canonical Parquet
    python scripts/build_weather_parquet.py --district nashik

    # Convert Pune normalized CSV to canonical Parquet
    python scripts/build_weather_parquet.py --district pune

    # Dry-run validation without writing files
    python scripts/build_weather_parquet.py --district pune --dry-run

    # Explicit input and output paths
    python scripts/build_weather_parquet.py \
        --input data/processed/normalized_nashik.csv \
        --output data/processed/canonical_nashik.parquet \
        --district nashik
"""

import os
import sys
import argparse
import logging

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data_pipeline.parquet_pipeline import (
    convert_normalized_to_parquet,
    validate_parquet_file,
)

DEFAULT_DATA_PATHS = {
    "nashik": {
        "input": "data/processed/normalized_nashik.csv",
        "output": "data/processed/canonical_nashik.parquet",
    },
    "pune": {
        "input": "data/processed/normalized_pune.csv",
        "output": "data/processed/canonical_pune.parquet",
    },
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="GramSevak Validated Canonical Parquet Weather Pipeline"
    )
    parser.add_argument(
        "--district",
        type=str,
        required=True,
        help="District key (e.g. 'nashik', 'pune')"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Custom path to Phase 1.4 normalized CSV file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Destination path for canonical Parquet file"
    )
    parser.add_argument(
        "--compression",
        type=str,
        default="snappy",
        help="Parquet compression codec (default: 'snappy')"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute pre-parquet validation without writing files to disk"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate an existing Parquet file on disk without rebuilding"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger("build_weather_parquet")

    district_key = args.district.strip().lower()
    defaults = DEFAULT_DATA_PATHS.get(district_key, {})

    input_path = args.input or defaults.get("input")
    output_path = args.output or defaults.get("output")

    if not input_path and not args.validate_only:
        logger.error(f"Missing input path for district '{district_key}'. Specify --input explicitly.")
        sys.exit(1)

    if not output_path:
        output_path = f"data/processed/canonical_{district_key}.parquet"

    if args.validate_only:
        logger.info(f"Validating existing Parquet file: {output_path}")
        report = validate_parquet_file(output_path)
        print("\n" + "=" * 60)
        print(f"PARQUET VALIDATION AUDIT: {district_key.upper()}")
        print("=" * 60)
        print(f"Status        : {report['status']}")
        print(f"Parquet Path  : {report['parquet_path']}")
        print(f"File Size     : {report.get('file_size_bytes', 0):,} bytes")
        print(f"Arrow Rows    : {report.get('arrow_rows', 0):,}")
        print(f"Arrow Columns : {report.get('arrow_columns', 0)}")
        print(f"Errors Logged : {report.get('errors_count', 0)}")
        print(f"Warnings      : {report.get('warnings_count', 0)}")
        print("=" * 60 + "\n")
        sys.exit(0 if report["status"] == "PASS" else 1)

    report = convert_normalized_to_parquet(
        input_path=input_path,
        output_path=output_path,
        district=district_key,
        compression=args.compression,
        dry_run=args.dry_run
    )

    print("\n" + "=" * 60)
    print(f"CANONICAL PARQUET PIPELINE REPORT: {district_key.upper()}")
    print("=" * 60)
    print(f"Status           : {report['overall_status']}")
    print(f"Input Path       : {report['input_path']}")
    print(f"Output Path      : {report['output_path']}")
    print(f"Input Rows       : {report['input_rows']:,}")
    print(f"Canonical Columns: {report['canonical_columns_count']}")
    if not args.dry_run and "write_metadata" in report and report["write_metadata"]:
        wm = report["write_metadata"]
        print(f"File Size        : {wm.get('file_size_bytes', 0):,} bytes")
        print(f"Compression      : {wm.get('compression', 'snappy')}")
        print(f"Write Time       : {wm.get('write_elapsed_seconds', 0):.4f}s")
    print(f"Total Time       : {report['total_elapsed_seconds']:.4f}s")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
