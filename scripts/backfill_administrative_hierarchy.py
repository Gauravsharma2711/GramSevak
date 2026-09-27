"""
GramSevak Administrative Hierarchy Backfill and Ingestion Script (Phase 3.2).

Performs safe, idempotent backfill of administrative hierarchy entities:
Districts -> Blocks -> Panchayats
using validated canonical Parquet datasets.

Usage:
  # Dry-run inspection
  python scripts/backfill_administrative_hierarchy.py --dry-run

  # Full production execution
  python scripts/backfill_administrative_hierarchy.py --real-run
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, List, Optional
import pyarrow.parquet as pq
import pandas as pd
from sqlalchemy.orm import Session

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.database import SessionLocal
from backend.app.repositories.hierarchy_repository import HierarchyRepository
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hierarchy_backfill")

CANONICAL_PARQUET_FILES = {
    "nashik": "data/processed/canonical_nashik.parquet",
    "pune": "data/processed/canonical_pune.parquet",
}


def backfill_hierarchy_from_parquet(
    parquet_path: str,
    db: Session,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Extract distinct administrative entities from Parquet and idempotently backfill.
    """
    abs_path = os.path.join(PROJECT_ROOT, parquet_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Canonical Parquet file not found at: {abs_path}")

    logger.info(f"Reading administrative metadata from: {parquet_path}")
    pfile = pq.ParquetFile(abs_path)
    columns_to_read = [
        "panchayat_id",
        "lgd_code",
        "panchayat_name",
        "block_name",
        "district_name",
        "state_name",
        "panchayat_latitude",
        "panchayat_longitude",
        "elevation_m",
    ]
    table = pfile.read(columns=columns_to_read)
    df = table.to_pandas().drop_duplicates(subset=["panchayat_id"])

    district_name = str(df["district_name"].iloc[0]).strip()
    state_name = str(df["state_name"].iloc[0]).strip()
    unique_blocks = [str(b).strip() for b in df["block_name"].unique()]
    total_panchayats_in_file = len(df)

    logger.info(
        f"Parsed {district_name}: {len(unique_blocks)} blocks, {total_panchayats_in_file} panchayats."
    )

    if dry_run:
        logger.info(f"[DRY-RUN] Would process District: {district_name}")
        return {
            "district": district_name,
            "blocks_count": len(unique_blocks),
            "panchayats_count": total_panchayats_in_file,
            "status": "DRY_RUN_OK",
        }

    # 1. Upsert District
    district = HierarchyRepository.upsert_district(db, name=district_name, state=state_name)
    district_id = district.id
    logger.info(f"Resolved District '{district.name}' (ID: {district_id})")

    # 2. Upsert Blocks
    block_map = {}
    for b_name in unique_blocks:
        blk = HierarchyRepository.upsert_block(db, district_id=district_id, name=b_name)
        block_map[b_name.lower()] = blk.id
    logger.info(f"Upserted {len(block_map)} Blocks under District '{district_name}'.")

    # 3. Upsert Panchayats
    created_count = 0
    updated_count = 0
    for _, row in df.iterrows():
        p_id = int(row["panchayat_id"])
        lgd = int(row["lgd_code"]) if pd.notna(row["lgd_code"]) else p_id
        p_name = str(row["panchayat_name"]).strip()
        b_name = str(row["block_name"]).strip()
        b_id = block_map[b_name.lower()]

        lat = float(row["panchayat_latitude"]) if pd.notna(row["panchayat_latitude"]) else None
        lon = float(row["panchayat_longitude"]) if pd.notna(row["panchayat_longitude"]) else None
        elev = float(row["elevation_m"]) if pd.notna(row["elevation_m"]) else None

        existing = db.query(Panchayat).filter(Panchayat.id == p_id).first()
        if existing:
            updated_count += 1
        else:
            created_count += 1

        HierarchyRepository.upsert_panchayat(
            db,
            id=p_id,
            lgd_code=lgd,
            name=p_name,
            block_id=b_id,
            district_id=district_id,
            latitude=lat,
            longitude=lon,
            elevation_m=elev,
        )

    db.commit()
    logger.info(
        f"District '{district_name}' backfill committed: {created_count} new, {updated_count} existing."
    )

    return {
        "district": district_name,
        "district_id": district_id,
        "blocks_count": len(block_map),
        "created_panchayats": created_count,
        "updated_panchayats": updated_count,
        "total_panchayats": total_panchayats_in_file,
        "status": "COMMITTED",
    }


def run_full_backfill(dry_run: bool = True) -> Dict[str, Any]:
    """
    Run backfill across all canonical Parquet datasets and verify orphan health.
    """
    db = SessionLocal()
    results = {}
    try:
        for dist_key, rel_path in CANONICAL_PARQUET_FILES.items():
            results[dist_key] = backfill_hierarchy_from_parquet(
                rel_path, db=db, dry_run=dry_run
            )

        # Integrity & Orphan Check
        orphans = HierarchyRepository.detect_orphans(db)
        results["orphan_audit"] = orphans
        results["healthy"] = orphans["is_clean"]
        logger.info(f"Orphan integrity check: {orphans}")

    except Exception as e:
        db.rollback()
        logger.error(f"Backfill execution failed: {e}")
        raise
    finally:
        db.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="GramSevak Administrative Hierarchy Backfill Tool")
    parser.add_argument(
        "--real-run",
        action="store_true",
        help="Execute database mutations. Default is dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate Parquet and schema without database mutations.",
    )
    args = parser.parse_args()

    is_dry_run = not args.real_run
    mode_str = "DRY-RUN" if is_dry_run else "REAL-RUN"
    logger.info(f"=== Starting GramSevak Administrative Hierarchy Backfill ({mode_str}) ===")

    summary = run_full_backfill(dry_run=is_dry_run)
    logger.info(f"Backfill Summary: {summary}")
    print("\nSUCCESS: Administrative backfill execution complete.")


if __name__ == "__main__":
    main()
