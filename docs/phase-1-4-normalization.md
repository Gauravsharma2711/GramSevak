# GramSevak Weather Data Normalization Pipeline Report (Phase 1.4)

## Executive Summary

Phase 1.4 implements a robust, district-independent normalization pipeline converting raw heterogeneous weather datasets into the canonical 22-field weather data schema established in Phase 1.3 (`schemas/canonical_weather_schema.json` and `docs/canonical-weather-schema.md`).

The pipeline enforces deterministic source-to-canonical mappings, rigorous physical boundary checks, ISO-8601 temporal standardization, Haversine geographic audit verification, and conservative duplicate/conflict detection across all operational districts.

### Pipeline Status Overview

| Metric | Nashik Dataset | Pune Dataset | Combined Pipeline |
| :--- | :--- | :--- | :--- |
| **Input File** | `data/raw/nashik/nashik_panchayat_weather_raw.csv` | `data/raw/pune/pune_original.csv` | 2 Files |
| **Source Encoding** | `latin1` | `utf-8` | Multi-Encoding Auto-Detect |
| **Input Rows** | 1,388 | 187,320 | 188,708 |
| **Valid Canonical Rows** | 1,388 (100.0%) | 187,320 (100.0%) | 188,708 (100.0%) |
| **Rejected Rows (ERROR)** | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| **Canonical Columns** | 22 | 22 | 22 |
| **Unique Panchayats** | 1,388 | 1,338 | 2,726 |
| **Unique Blocks** | 15 | 13 | 28 |
| **Temporal Coverage** | 2026-01-09 to 2026-09-04 | 2026-04-13 to 2026-09-23 | 2026-01-09 to 2026-09-23 |
| **Date Format Standardized** | `YYYY-MM-DD` | `YYYY-MM-DD` | ISO 8601 (`YYYY-MM-DD`) |
| **Lead Days Semantics** | Snapshot (`lead_days = 0`) | Forecast (`lead_days = 1`) | Preserved & Validated |
| **Raw Data Integrity** | SHA-256 Unaltered | SHA-256 Unaltered | Strict Immutability |
| **Validation Status** | **PASS WITH WARNINGS** | **PASS** | **PASS WITH WARNINGS** |

---

## 1. Canonical Schema Implementation

The normalizer transforms raw input streams into exactly 22 standardized columns:

| Field Index | Canonical Column | Data Type | Nullable | Source Semantics & Normalization Rule |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `panchayat_id` | `INTEGER` (int64) | No | Canonical integer identifier (Nashik: 1001-2388; Pune: LGD-derived 185262) |
| 2 | `lgd_code` | `INTEGER` (int64) | No | Ministry of Panchayati Raj 6-digit Local Government Directory code |
| 3 | `panchayat_name` | `TEXT` (string) | No | Normalized Title Case string; whitespace & NBSP (`\xa0`) sanitized |
| 4 | `block_name` | `TEXT` (string) | No | Normalized Title Case sub-district administrative unit |
| 5 | `district_name` | `TEXT` (string) | No | Standardized administrative district name (`Nashik`, `Pune`) |
| 6 | `state_name` | `TEXT` (string) | No | Standardized federal state (`Maharashtra`) |
| 7 | `panchayat_latitude` | `FLOAT` (float64) | No | WGS84 coordinate rounded to 6 decimal places (~0.1m precision) |
| 8 | `panchayat_longitude` | `FLOAT` (float64) | No | WGS84 coordinate rounded to 6 decimal places (~0.1m precision) |
| 9 | `elevation_m` | `FLOAT` (float64) | No | Elevation above sea level in meters rounded to 1 decimal place |
| 10 | `date` | `TEXT` (string) | No | Target meteorological date in ISO 8601 format (`YYYY-MM-DD`) |
| 11 | `forecast_issue_date` | `TEXT` (string) | No | Forecast generation/issue date in ISO 8601 format (`YYYY-MM-DD`) |
| 12 | `lead_days` | `INTEGER` (int64) | No | Discrete forecast horizon in days (`date - forecast_issue_date`) |
| 13 | `block_forecast_rainfall_mm` | `FLOAT` (float64) | No | Quantitative forecast precipitation in millimeters (2 decimals) |
| 14 | `station_id` | `TEXT` (string) | No | Nearest weather station identifier (AWS / GHCND code) |
| 15 | `station_latitude` | `FLOAT` (float64) | No | Ground observation station latitude (6 decimals) |
| 16 | `station_longitude` | `FLOAT` (float64) | No | Ground observation station longitude (6 decimals) |
| 17 | `station_distance_km` | `FLOAT` (float64) | No | Proximity from Panchayat centroid to station (Haversine verified) |
| 18 | `actual_rainfall_mm` | `FLOAT` (float64) | Yes | Observed ground precipitation in mm; null when unobserved |
| 19 | `source_dataset` | `TEXT` (string) | No | Audit lineage identifier (`nashik`, `pune`) |
| 20 | `source_file` | `TEXT` (string) | No | Exact source CSV path for audit reproducibility |
| 21 | `source_row_id` | `INTEGER` (int64) | No | 0-indexed original physical record position in raw dataset |
| 22 | `source_panchayat_id` | `TEXT` (string) | No | Unmodified raw Panchayat identifier string (e.g. `MH_27_PUNE_185262`) |

---

## 2. District Dataset Validation Results

### 2.1 Nashik District (`nashik_panchayat_weather_raw.csv`)

- **Input Rows**: 1,388 rows, 17 columns (encoded as `latin1`)
- **Output Rows**: 1,388 canonical records (0 rejected)
- **Status**: `PASS WITH WARNINGS`

#### Mapped Source Columns
- `panchayat_id` -> `panchayat_id`
- `lgd_code` -> `lgd_code`
- `panchayat_name` -> `panchayat_name`
- `block_name` -> `block_name`
- `district_name` -> `district_name`
- `latitude` -> `panchayat_latitude`
- `longitude` -> `panchayat_longitude`
- `elevation_m` -> `elevation_m`
- `date` -> `date`
- `forecast_issue_date` -> `forecast_issue_date`
- `block_forecast_rainfall_mm` -> `block_forecast_rainfall_mm`
- `station_id` -> `station_id`
- `station_latitude` -> `station_latitude`
- `station_longitude` -> `station_longitude`
- `station_distance_km` -> `station_distance_km`
- `actual_rainfall_mm` -> `actual_rainfall_mm`

#### Unmapped Source Columns & Artifacts
- `Unnamed: 16`: Trailing blank column from raw export, safely excluded from canonical output.

#### Audit Metrics & Summary
- **Unique Panchayats**: 1,388 across 15 Blocks (`Baglan`, `Chandwad`, `Deola`, `Dindori`, `Igatpuri`, `Kalwan`, `Malegaon`, `Nandgaon`, `Nashik`, `Niphad`, `Peint`, `Sinnar`, `Surgana`, `Trimbakeshwar`, `Yevala`).
- **Geographic Bounds**: Lat [19.5975, 20.8988], Lon [73.2847, 74.8722], Elevation [385.0m, 1024.0m].
- **Rainfall Metrics**: Block forecast rainfall [0.0mm, 28.5mm] (mean: 4.88mm); Actual rainfall [0.0mm, 35.0mm] (mean: 5.21mm); 0 null values.
- **Haversine Distance Discrepancy**: Maximum discrepancy vs recomputed great-circle distance is 0.44 km (well within tolerance).
- **Warnings (1)**: 7 remote Panchayats located > 50.0 km from nearest AWS station (Baglan & Kalwan talukas). Retained with warning.
- **Duplicates & Conflicts**: 0 exact duplicates, 0 business-key duplicates, 0 conflicts.

---

### 2.2 Pune District (`pune_original.csv`)

- **Input Rows**: 187,320 rows, 16 columns (encoded as `utf-8`)
- **Output Rows**: 187,320 canonical records (0 rejected)
- **Status**: `PASS`

#### Mapped Source Columns
- `panchayat_id` -> `panchayat_id` (extracted integer ID `185262`) & `source_panchayat_id` (`MH_27_PUNE_185262`)
- `lgd_code` -> `lgd_code`
- `panchayat_name` -> `panchayat_name`
- `block_name` -> `block_name`
- `district_name` -> `district_name`
- `panchayat_latitude` -> `panchayat_latitude`
- `panchayat_longitude` -> `panchayat_longitude`
- `elevation_m` -> `elevation_m`
- `date` -> `date`
- `forecast_issue_date` -> `forecast_issue_date`
- `block_forecast_rainfall_mm` -> `block_forecast_rainfall_mm`
- `station_id` -> `station_id`
- `station_latitude` -> `station_latitude`
- `station_longitude` -> `station_longitude`
- `station_distance_km` -> `station_distance_km`
- `actual_rainfall_mm` -> `actual_rainfall_mm`

#### Audit Metrics & Summary
- **Unique Panchayats**: 1,338 across 13 Blocks (`Ambegaon`, `Baramati`, `Bhor`, `Daund`, `Haveli`, `Indapur`, `Junnar`, `Khed`, `Mawal`, `Mulshi`, `Purandhar`, `Shirur`, `Velhe`).
- **Temporal Horizon**: 140 unique dates spanning 2026-04-13 through 2026-09-23. All records possess strictly `lead_days = 1` (issue date = target date - 1 day).
- **Geographic Bounds**: Lat [17.9250, 19.3789], Lon [73.3512, 75.1432], Elevation [420.0m, 1276.0m].
- **Rainfall Metrics**: Block forecast rainfall [0.0mm, 184.2mm] (mean: 6.12mm); Actual rainfall [0.0mm, 312.4mm] (mean: 6.84mm); 0 null values.
- **Haversine Distance Discrepancy**: Maximum discrepancy vs recomputed great-circle distance is 0.48 km.
- **Warnings / Errors**: 0 errors, 0 warnings.
- **Duplicates & Conflicts**: 0 exact duplicates, 0 business-key duplicates, 0 conflicts.

---

## 3. Data Transformation & Validation Policies

### 3.1 Identifier Normalization
- **Authoritative LGD Codes**: Retained as authoritative 6-digit integers.
- **Composite Format Handling**: In Pune, the composite string identifier `MH_27_PUNE_185262` is parsed using regex `(\d+)$` to extract integer `185262`, while the raw composite string is preserved in `source_panchayat_id`.
- **Cross-District Disambiguation**: By maintaining `district_name`, `panchayat_id`, and `source_panchayat_id`, all administrative entities are unambiguously identifiable across district boundaries.

### 3.2 Temporal Normalization & Lead Days
- **ISO-8601 Consistency**: All date strings parsed into standard `YYYY-MM-DD`.
- **Forecast Horizon**: `lead_days` calculated strictly as `(date - forecast_issue_date).days`.
  - Nashik snapshot data: `lead_days = 0`
  - Pune daily forecast time-series: `lead_days = 1`
- **Integrity Validation**: Records with negative lead days (`issue_date > target_date`) trigger row rejection with `ERROR`.

### 3.3 Rainfall Policies
- **Preservation of Legitimate Zeroes**: `0.0 mm` represents dry weather and is strictly preserved as numeric zero (never coerced to null).
- **Sentinel & Negative Sanitization**: Invalid sentinels (`-999.0`, `-999.9`, `9999.0`) and negative actual rainfall are coerced to `null` (`np.nan`) with a non-fatal `WARNING`.
- **Forecast Non-Negativity**: Negative block forecast rainfall triggers row rejection with `ERROR`.

### 3.4 Geographic & Elevation Bounds
- **Coordinate Envelope**: Validated within physical global ranges (-90 to 90 lat, -180 to 180 lon) and checked against Maharashtra regional bounding envelope [15.0N-22.5N, 72.0E-81.5E].
- **Elevation**: Non-null constraint enforced; values checked against Deccan plateau / Western Ghats thresholds [0m, 2500m].
- **Proximity Verification**: Vectorized Haversine recomputation compares source `station_distance_km` against coordinates; discrepancies > 5.0 km generate audit alerts.

### 3.5 Duplicate & Conflict Resolution
- **Exact Duplicates**: Identified and logged with `WARNING`.
- **Business Key Definition**: `(panchayat_id, date, lead_days)` represents the unique meteorological observation contract.
- **Conflict Handling**: Multiple records sharing the business key with conflicting rainfall or forecast values are quarantined and reported as `ERROR` without silent overwriting.

---

## 4. Pipeline Execution & Dry-Run Interface

The normalization pipeline is executed via CLI or programmatically:

```bash
# Dry-run execution (validation & reporting without disk writes)
python -m data_pipeline.canonical_normalizer --district nashik --dry-run
python -m data_pipeline.canonical_normalizer --district pune --dry-run

# Standard execution generating intermediate canonical outputs
python -m data_pipeline.canonical_normalizer --district nashik --output data/processed/normalized_nashik.csv
python -m data_pipeline.canonical_normalizer --district pune --output data/processed/normalized_pune.csv
```

### Python API Integration
```python
from data_pipeline.canonical_normalizer import normalize_weather_data

valid_df, quality_report = normalize_weather_data(
    source_path="data/raw/pune/pune_original.csv",
    district="pune",
    output_path="data/processed/normalized_pune.csv",
    dry_run=False
)
```

---

## 5. Raw Data Immutability Verification

Checksum validation confirmed that source files remained completely untouched throughout the execution of Phase 1.4:

| Dataset | Pre-Run SHA-256 | Post-Run SHA-256 | Immutability Verification |
| :--- | :--- | :--- | :---: |
| `data/raw/nashik/nashik_panchayat_weather_raw.csv` | `208bb024dc49b978e1c9346c2eb941bb933a9cffdf7a4f3b84c5df3594040276` | `208bb024dc49b978e1c9346c2eb941bb933a9cffdf7a4f3b84c5df3594040276` | **VERIFIED UNCHANGED** |
| `data/raw/pune/pune_original.csv` | `8dbb31ea9e6d9b36eb951f5b980dd9d2a402108a57eeffa962ee944ba403a7a9` | `8dbb31ea9e6d9b36eb951f5b980dd9d2a402108a57eeffa962ee944ba403a7a9` | **VERIFIED UNCHANGED** |

---

## 6. Automated Test Suite

A comprehensive test suite in `tests/test_normalization_pipeline.py` covers all 14 Phase 1.4 requirements:

1. `test_valid_row_normalization`: Validates 22-column canonical assembly and types.
2. `test_numeric_conversion`: Tests whitespace trimming and float/integer coercions.
3. `test_date_conversion`: Tests date formats and ISO-8601 normalization.
4. `test_missing_value_handling`: Confirms sentinel `-999.0` coercion to NaN with warning.
5. `test_zero_rainfall_preservation`: Asserts `0.0 mm` is preserved and not converted to null.
6. `test_invalid_coordinate_detection`: Asserts coordinates outside [-90, 90] are rejected with `ERROR`.
7. `test_invalid_forecast_rainfall_detection`: Asserts negative forecast rainfall is rejected with `ERROR`.
8. `test_identifier_preservation`: Asserts Nashik and Pune ID extraction and provenance retention.
9. `test_duplicate_detection`: Asserts exact duplicate rows generate audit warning.
10. `test_conflicting_duplicate_detection`: Asserts conflicting values for same business key trigger `ERROR`.
11. `test_source_to_canonical_mapping`: Asserts unmapped artifacts (e.g. `Unnamed: 16`) are dropped from canonical columns.
12. `test_lead_days_calculation`: Asserts `lead_days = 0` for Nashik and `lead_days = 1` for Pune.
13. `test_district_independence`: Asserts single entrypoint handles heterogeneous district configurations.
14. `test_raw_data_immutability`: Asserts source files and timestamps are completely unmutated.

**Test Execution Result**: 14 / 14 tests passing in 0.55s.
