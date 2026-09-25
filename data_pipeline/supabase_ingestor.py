"""
Supabase PostgreSQL Ingestion Engine for Multi-District Weather Data.

Handles idempotent batch upserts into:
- districts
- blocks
- panchayats
- station_metadata
- block_forecasts
- weather_observations
- panchayat_weather_data (backward compatibility snapshot)

Enforces dry-run capability, conflict resolution, transaction safety,
and comprehensive reporting without deleting or truncating existing records.
"""

import time
import logging
from typing import Dict, Any, List
import pandas as pd
import psycopg2.extras
from sqlalchemy import text

from backend.app.core.database import engine
from data_pipeline.district_config import DistrictConfig

logger = logging.getLogger(__name__)


def ingest_district_data(
    df: pd.DataFrame,
    config: DistrictConfig,
    dry_run: bool = False,
    batch_size: int = 5000,
    limit_observations: int = None,
) -> Dict[str, Any]:
    """
    Ingest normalized canonical weather DataFrame into Supabase PostgreSQL.
    """
    start_time = time.time()
    total_records = len(df)
    
    # 1. Prepare unique entities
    # District
    district_name = config.name
    state_name = config.state

    # Unique Blocks
    unique_blocks = sorted(df["block_name"].dropna().unique().tolist())
    
    # Unique Panchayats (latest record metadata)
    panchayat_meta = (
        df.sort_values(by=["panchayat_id", "date"], ascending=[True, False])
        .drop_duplicates(subset=["panchayat_id"])
        .copy()
    )
    unique_panchayats_count = len(panchayat_meta)

    # Unique Stations
    stations_df = (
        df[["station_id", "station_latitude", "station_longitude"]]
        .dropna(subset=["station_id"])
        .drop_duplicates(subset=["station_id"])
        .copy()
    )
    unique_stations_count = len(stations_df)

    # Block Forecasts (Consensus aggregation by block, issue date, target date)
    forecast_group_cols = [
        "district_name",
        "block_name",
        "forecast_issue_date",
        "date",
    ]
    block_forecasts_df = (
        df.groupby(forecast_group_cols, as_index=False)["block_forecast_rainfall_mm"]
        .mean()
        .round(2)
        .rename(columns={"date": "forecast_date"})
    )
    total_block_forecasts = len(block_forecasts_df)

    # Weather Observations
    obs_df = df[[
        "panchayat_id",
        "lgd_code",
        "station_id",
        "date",
        "actual_rainfall_mm",
        "station_distance_km"
    ]].copy()
    if limit_observations:
        obs_df = obs_df.head(limit_observations)
    total_observations = len(obs_df)

    summary = {
        "district": district_name,
        "dry_run": dry_run,
        "total_source_records": total_records,
        "entities": {
            "districts_to_upsert": 1,
            "blocks_to_upsert": len(unique_blocks),
            "panchayats_to_upsert": unique_panchayats_count,
            "stations_to_upsert": unique_stations_count,
            "block_forecasts_to_upsert": total_block_forecasts,
            "weather_observations_to_upsert": total_observations,
            "legacy_panchayat_snapshot_to_upsert": unique_panchayats_count,
        },
        "inserted_or_updated": {},
        "status": "DRY_RUN_COMPLETED" if dry_run else "PENDING",
    }

    if dry_run:
        summary["duration_seconds"] = round(time.time() - start_time, 2)
        summary["message"] = "Dry run completed successfully. No changes committed to database."
        return summary

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()

        # Step 1: Upsert District
        cursor.execute("""
            INSERT INTO districts (name, state)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET state = EXCLUDED.state
            RETURNING id;
        """, (district_name, state_name))
        district_id = cursor.fetchone()[0]
        raw_conn.commit()
        summary["inserted_or_updated"]["districts"] = 1

        # Step 2: Upsert Blocks
        block_tuples = [(district_id, b_name) for b_name in unique_blocks]
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO blocks (district_id, name)
            VALUES %s
            ON CONFLICT (district_id, name) DO NOTHING;
            """,
            block_tuples,
            page_size=100
        )
        raw_conn.commit()

        # Query mapping: block_name -> block_id
        cursor.execute("SELECT name, id FROM blocks WHERE district_id = %s;", (district_id,))
        block_map = {row[0]: row[1] for row in cursor.fetchall()}
        summary["inserted_or_updated"]["blocks"] = len(block_map)

        # Step 3: Upsert Panchayats
        panchayat_tuples = [
            (
                int(row["panchayat_id"]),
                int(row["lgd_code"]),
                f"MH_{district_name.upper()}_{row['lgd_code']}",
                str(row["panchayat_name"]),
                block_map.get(str(row["block_name"])),
                district_id,
                float(row["panchayat_latitude"]) if pd.notnull(row["panchayat_latitude"]) else None,
                float(row["panchayat_longitude"]) if pd.notnull(row["panchayat_longitude"]) else None,
                float(row["elevation_m"]) if pd.notnull(row["elevation_m"]) else None,
            )
            for _, row in panchayat_meta.iterrows()
        ]
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO panchayats (id, lgd_code, panchayat_code, name, block_id, district_id, latitude, longitude, elevation_m)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                lgd_code = EXCLUDED.lgd_code,
                name = EXCLUDED.name,
                block_id = EXCLUDED.block_id,
                district_id = EXCLUDED.district_id,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                elevation_m = EXCLUDED.elevation_m;
            """,
            panchayat_tuples,
            page_size=1000
        )
        raw_conn.commit()
        summary["inserted_or_updated"]["panchayats"] = len(panchayat_tuples)

        # Step 4: Upsert Stations
        station_tuples = [
            (
                str(row["station_id"]),
                str(row["station_id"]),
                float(row["station_latitude"]) if pd.notnull(row["station_latitude"]) else None,
                float(row["station_longitude"]) if pd.notnull(row["station_longitude"]) else None,
                district_name,
            )
            for _, row in stations_df.iterrows()
        ]
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO station_metadata (station_id, station_name, latitude, longitude, district_name)
            VALUES %s
            ON CONFLICT (station_id) DO UPDATE SET
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                district_name = EXCLUDED.district_name;
            """,
            station_tuples,
            page_size=500
        )
        raw_conn.commit()
        summary["inserted_or_updated"]["station_metadata"] = len(station_tuples)

        # Step 5: Upsert Block Forecasts
        forecast_tuples = [
            (
                district_id,
                block_map.get(str(row["block_name"])),
                str(row["district_name"]),
                str(row["block_name"]),
                str(row["forecast_issue_date"]),
                str(row["forecast_date"]),
                float(row["block_forecast_rainfall_mm"]),
                config.source,
                config.source_model,
            )
            for _, row in block_forecasts_df.iterrows()
        ]
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO block_forecasts (
                district_id, block_id, district_name, block_name,
                forecast_issue_date, forecast_date, rainfall_mm,
                source, source_model
            )
            VALUES %s
            ON CONFLICT (district_name, block_name, forecast_issue_date, forecast_date, source_model)
            DO UPDATE SET rainfall_mm = EXCLUDED.rainfall_mm;
            """,
            forecast_tuples,
            page_size=2000
        )
        raw_conn.commit()
        summary["inserted_or_updated"]["block_forecasts"] = len(forecast_tuples)

        # Step 6: Upsert Legacy / Active Snapshot into panchayat_weather_data
        # Ensures existing endpoints & dashboards immediately see all panchayats
        legacy_tuples = [
            (
                int(row["panchayat_id"]),
                int(row["lgd_code"]),
                str(row["panchayat_name"]),
                str(row["block_name"]),
                str(row["district_name"]),
                float(row["panchayat_latitude"]) if pd.notnull(row["panchayat_latitude"]) else None,
                float(row["panchayat_longitude"]) if pd.notnull(row["panchayat_longitude"]) else None,
                float(row["elevation_m"]) if pd.notnull(row["elevation_m"]) else None,
                str(row["date"]),
                str(row["forecast_issue_date"]),
                float(row["block_forecast_rainfall_mm"]) if pd.notnull(row["block_forecast_rainfall_mm"]) else None,
                str(row["station_id"]) if pd.notnull(row["station_id"]) else None,
                float(row["station_latitude"]) if pd.notnull(row["station_latitude"]) else None,
                float(row["station_longitude"]) if pd.notnull(row["station_longitude"]) else None,
                float(row["station_distance_km"]) if pd.notnull(row["station_distance_km"]) else None,
                float(row["actual_rainfall_mm"]) if pd.notnull(row["actual_rainfall_mm"]) else None,
            )
            for _, row in panchayat_meta.iterrows()
        ]
        psycopg2.extras.execute_values(
            cursor,
            """
            INSERT INTO panchayat_weather_data (
                panchayat_id, lgd_code, panchayat_name, block_name, district_name,
                panchayat_latitude, panchayat_longitude, elevation_m,
                date, forecast_issue_date, block_forecast_rainfall_mm,
                station_id, station_latitude, station_longitude, station_distance_km,
                actual_rainfall_mm
            )
            VALUES %s
            ON CONFLICT (panchayat_id) DO UPDATE SET
                lgd_code = EXCLUDED.lgd_code,
                panchayat_name = EXCLUDED.panchayat_name,
                block_name = EXCLUDED.block_name,
                district_name = EXCLUDED.district_name,
                panchayat_latitude = EXCLUDED.panchayat_latitude,
                panchayat_longitude = EXCLUDED.panchayat_longitude,
                elevation_m = EXCLUDED.elevation_m,
                date = EXCLUDED.date,
                forecast_issue_date = EXCLUDED.forecast_issue_date,
                block_forecast_rainfall_mm = EXCLUDED.block_forecast_rainfall_mm,
                station_id = EXCLUDED.station_id,
                station_latitude = EXCLUDED.station_latitude,
                station_longitude = EXCLUDED.station_longitude,
                station_distance_km = EXCLUDED.station_distance_km,
                actual_rainfall_mm = EXCLUDED.actual_rainfall_mm;
            """,
            legacy_tuples,
            page_size=1000
        )
        raw_conn.commit()
        summary["inserted_or_updated"]["panchayat_weather_data"] = len(legacy_tuples)

        # Step 7: Batch Upsert Weather Observations
        logger.info(f"Uploading {total_observations} weather observations in batches of {batch_size}...")
        obs_records = [
            (
                int(row["panchayat_id"]),
                int(row["lgd_code"]),
                str(row["station_id"]) if pd.notnull(row["station_id"]) else None,
                str(row["date"]),
                float(row["actual_rainfall_mm"]) if pd.notnull(row["actual_rainfall_mm"]) else None,
                float(row["station_distance_km"]) if pd.notnull(row["station_distance_km"]) else None,
            )
            for _, row in obs_df.iterrows()
        ]

        obs_sql = """
            INSERT INTO weather_observations (
                panchayat_id, lgd_code, station_id,
                observation_date, actual_rainfall_mm, station_distance_km
            )
            VALUES %s
            ON CONFLICT (panchayat_id, observation_date) DO UPDATE SET
                actual_rainfall_mm = EXCLUDED.actual_rainfall_mm,
                station_distance_km = EXCLUDED.station_distance_km;
        """

        uploaded_obs = 0
        for i in range(0, len(obs_records), batch_size):
            chunk = obs_records[i : i + batch_size]
            psycopg2.extras.execute_values(cursor, obs_sql, chunk, page_size=len(chunk))
            raw_conn.commit()
            uploaded_obs += len(chunk)
            if uploaded_obs % 25000 == 0 or uploaded_obs == len(obs_records):
                logger.info(f"Uploaded {uploaded_obs}/{len(obs_records)} observations...")

        summary["inserted_or_updated"]["weather_observations"] = uploaded_obs
        summary["status"] = "SUCCESS"
        summary["duration_seconds"] = round(time.time() - start_time, 2)
        summary["message"] = f"Successfully ingested {district_name} dataset into Supabase."

    finally:
        raw_conn.close()

    return summary
