# GramSevak Validated Parquet Weather Pipeline Report (Phase 1.5)

## Executive Summary

Phase 1.5 establishes the high-performance columnar data storage layer for the GramSevak meteorological downscaling engine. The pipeline ingests the 22-column canonical weather datasets produced by Phase 1.4, validates schema and domain contracts, enforces strict PyArrow columnar typing, writes compressed Parquet files using Snappy, and executes comprehensive read-back verification against in-memory source data.

### Pipeline Status Overview

| Metric | Nashik Dataset | Pune Dataset | Combined Pipeline |
| :--- | :--- | :--- | :--- |
| **Input Normalized File** | `data/processed/normalized_nashik.csv` | `data/processed/normalized_pune.csv` | 2 Files |
| **Output Parquet File** | `data/processed/canonical_nashik.parquet` | `data/processed/canonical_pune.parquet` | 2 Files |
| **Compression Codec** | Snappy | Snappy | Snappy |
| **Input Row Count** | 1,388 | 187,320 | 188,708 |
| **Parquet Row Count** | 1,388 (100.0%) | 187,320 (100.0%) | 188,708 (100.0%) |
| **Uncompressed CSV Size** | 273,200 bytes (~273 KB) | 37,692,267 bytes (~37.7 MB) | ~38.0 MB |
| **Parquet File Size** | 73,950 bytes (~74 KB) | 1,175,904 bytes (~1.18 MB) | ~1.25 MB |
| **Compression Ratio** | 3.7x (72.9% reduction) | 32.1x (96.9% reduction) | 30.4x (96.7% reduction) |
| **Write Time** | 0.049s | 0.328s | 0.377s |
| **Total Pipeline Time** | 0.165s | 2.383s | 2.548s |
| **Read-Back Validation** | Verified (0 errors) | Verified (0 errors) | Verified (0 errors) |
| **Raw Data Integrity** | SHA-256 Unaltered | SHA-256 Unaltered | Strict Immutability |
| **Pipeline Status** | **PASS** | **PASS** | **PASS** |

---

## 1. Pipeline Architecture & Design

The validated Parquet pipeline follows a strict, repeatable, multi-stage architecture:

```
Phase 1.4 Normalized CSV
         │
         ▼
Pre-Parquet Schema & Domain Validation
         │ (Verify 22 canonical columns, non-null IDs, coordinate ranges, ISO-8601 dates)
         ▼
Type Enforcement & Explicit Casting
         │ (Explicit int64, float64, and string typing; deterministic column order)
         ▼
PyArrow Columnar Serialization
         │ (pa.Table with explicit CANONICAL_PARQUET_SCHEMA & dictionary encoding)
         ▼
Atomic Snappy Parquet Write
         │ (Write to temporary file -> atomic os.replace prevents corruption on interruption)
         ▼
Post-Write Parquet Validation & Read-Back
         │ (Dual validation: PyArrow low-level schema audit + Pandas high-level read)
         ▼
Deep Data Integrity & Fingerprint Comparison
         │ (Exact row count, null distribution, aggregate sums, business key SHA-256)
         ▼
Structured Quality Report Generation
```

---

## 2. Canonical Column & Parquet Type Specification

The Parquet schema enforces exact physical and logical types specified in `schemas/canonical_weather_schema.json`:

| Index | Field Name | Arrow / Parquet Type | Nullable | Description & Domain Rules |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `panchayat_id` | `int64` | No | Authoritative integer Panchayat entity ID (positive integer) |
| 2 | `lgd_code` | `int64` | No | 6-digit Ministry of Panchayati Raj Local Government Directory code |
| 3 | `panchayat_name` | `string` | No | Standardized Gram Panchayat name (Title Case, non-empty) |
| 4 | `block_name` | `string` | No | Standardized sub-district administrative unit (Title Case) |
| 5 | `district_name` | `string` | No | Standardized district name (`Nashik`, `Pune`) |
| 6 | `state_name` | `string` | No | Standardized state name (`Maharashtra`) |
| 7 | `panchayat_latitude` | `float64` | No | Centroid WGS84 latitude [-90.0, 90.0] |
| 8 | `panchayat_longitude` | `float64` | No | Centroid WGS84 longitude [-180.0, 180.0] |
| 9 | `elevation_m` | `float64` | No | Terrain elevation in meters above sea level [0, 3000] |
| 10 | `date` | `string` | No | Target meteorological date in ISO 8601 format (`YYYY-MM-DD`) |
| 11 | `forecast_issue_date` | `string` | No | Model issuance date in ISO 8601 format (`YYYY-MM-DD`) |
| 12 | `lead_days` | `int64` | No | Forecast lead horizon in discrete days (`date - issue_date`) |
| 13 | `block_forecast_rainfall_mm` | `float64` | No | Block NWP precipitation forecast in mm (non-negative) |
| 14 | `station_id` | `string` | No | Reference weather station identifier (AWS / GHCND code) |
| 15 | `station_latitude` | `float64` | No | Reference weather station latitude (WGS84) |
| 16 | `station_longitude` | `float64` | No | Reference weather station longitude (WGS84) |
| 17 | `station_distance_km` | `float64` | No | Great-circle Haversine proximity distance in km [0, 150] |
| 18 | `actual_rainfall_mm` | `float64` | Yes | Observed ground precipitation in mm (null allowed for unobserved) |
| 19 | `source_dataset` | `string` | No | Lineage jurisdiction key (`nashik`, `pune`) |
| 20 | `source_file` | `string` | No | Workspace relative path of originating source CSV |
| 21 | `source_row_id` | `int64` | No | 0-indexed physical row sequence number in source file |
| 22 | `source_panchayat_id` | `string` | No | Unmodified raw Panchayat string identifier |

---

## 3. Detailed Dataset Validation Results

### 3.1 Nashik District (`canonical_nashik.parquet`)

- **Input File**: `data/processed/normalized_nashik.csv`
- **Output File**: `data/processed/canonical_nashik.parquet`
- **Pre-Validation**: `PASS` (All 22 canonical columns present, non-null IDs, valid coordinates, valid dates).
- **Post-Validation**: `PASS` (PyArrow schema verified, Pandas read-back verified, 0 errors, 0 warnings).
- **Metrics**:
  - Rows: 1,388
  - Columns: 22
  - Unique Panchayats: 1,388 across 15 Blocks
  - Date Range: 2026-01-09 to 2026-09-04
  - Lead Days: 0 (Snapshot observation)
  - Null Counts: Exactly 0 nulls across all 22 columns
  - Aggregate Forecast Sum: 6,779.0 mm (mean: 4.8840 mm)
  - Aggregate Actual Sum: 7,235.8 mm (mean: 5.2131 mm)
  - Logical Fingerprint Key Hash: `5b70ad4de1f75675c9c35156936820a6215dcad943a14660bb260804beb36b0a`

### 3.2 Pune District (`canonical_pune.parquet`)

- **Input File**: `data/processed/normalized_pune.csv`
- **Output File**: `data/processed/canonical_pune.parquet`
- **Pre-Validation**: `PASS` (All 22 canonical columns present, non-null IDs, valid coordinates, valid dates).
- **Post-Validation**: `PASS` (PyArrow schema verified, Pandas read-back verified, 0 errors, 0 warnings).
- **Metrics**:
  - Rows: 187,320
  - Columns: 22
  - Unique Panchayats: 1,338 across 13 Blocks
  - Date Range: 2026-04-13 to 2026-09-23 (140 consecutive days)
  - Lead Days: 1 (Daily forecast)
  - Null Counts: Exactly 0 nulls across all 22 columns
  - Aggregate Forecast Sum: 1,146,056.2 mm (mean: 6.1182 mm)
  - Aggregate Actual Sum: 1,281,421.4 mm (mean: 6.8408 mm)
  - Logical Fingerprint Key Hash: `9ae5aeeb5ae54011409559c55b62bda247f158cb54e0b0e51ee0851ec6a9c13b`

---

## 4. Partitioning & Storage Decision

### Decision: Single Parquet File Per District
Rather than partitioning datasets into thousands of micro-files by Panchayat or Date (which creates severe filesystem overhead, metadata bloat, and slow random I/O for ML training), the storage architecture adopts **one canonical Parquet file per district**:
- `data/processed/canonical_nashik.parquet` (~74 KB)
- `data/processed/canonical_pune.parquet` (~1.18 MB)

### Rationale:
1. **Compact Footprint**: 187k rows of Pune data compress into just 1.18 MB using Snappy, fitting completely in memory with sub-millisecond retrieval.
2. **Columnar Projection**: ML algorithms can select subsets of columns (e.g. `['panchayat_id', 'elevation_m', 'block_forecast_rainfall_mm', 'actual_rainfall_mm']`) without reading unneeded string columns, providing near-instantaneous I/O.
3. **Partitioning Overhead Avoidance**: Creating partitions per Panchayat would yield 2,726 individual sub-directories with sub-kilobyte files, creating immense metadata overhead.
4. **Idempotent Regeneration**: A single file per district guarantees atomic replacement and zero risk of orphaned partition partitions.

---

## 5. Performance Observations

| Benchmark Stage | Nashik (1,388 rows) | Pune (187,320 rows) | Scaling Behavior |
| :--- | :--- | :--- | :--- |
| **Normalized CSV Read** | ~0.015s | ~1.100s | Linear with row count |
| **Pre-Parquet Validation** | ~0.035s | ~0.350s | Vectorized NumPy/Pandas validation |
| **Type Enforcement & Casting** | ~0.005s | ~0.150s | Direct array casting |
| **PyArrow Serialization & Write**| ~0.049s | ~0.328s | High-throughput C++ columnar writer |
| **Parquet Read-Back & Audit** | ~0.012s | ~0.320s | Fast metadata scan & column decompression |
| **Total Execution Elapsed** | **0.165s** | **2.383s** | **~78,000 rows / second throughput** |

---

## 6. Raw Data Immutability Verification

Checksum validation confirmed that source files remained completely untouched throughout the execution of Phase 1.5:

| Dataset | Pre-Run SHA-256 | Post-Run SHA-256 | Status |
| :--- | :--- | :--- | :---: |
| `data/raw/nashik/nashik_panchayat_weather_raw.csv` | `208bb024dc49b978e1c9346c2eb941bb933a9cffdf7a4f3b84c5df3594040276` | `208bb024dc49b978e1c9346c2eb941bb933a9cffdf7a4f3b84c5df3594040276` | **VERIFIED UNCHANGED** |
| `data/raw/pune/pune_original.csv` | `8dbb31ea9e6d9b36eb951f5b980dd9d2a402108a57eeffa962ee944ba403a7a9` | `8dbb31ea9e6d9b36eb951f5b980dd9d2a402108a57eeffa962ee944ba403a7a9` | **VERIFIED UNCHANGED** |

---

## 7. Automated Test Suite

A comprehensive test suite in `tests/test_parquet_pipeline.py` covers all 14 Phase 1.5 requirements:

1. `test_valid_canonical_dataset_converts`: Validates 22-column Arrow table generation and Snappy write.
2. `test_schema_mismatch_fails`: Verifies that invalid schemas fail validation and log informative errors.
3. `test_missing_required_column_fails`: Asserts that missing canonical columns halt pre-conversion validation.
4. `test_unexpected_column_reported`: Confirms non-canonical columns generate audit warnings.
5. `test_invalid_type_fails_pre_validation`: Tests rejection of invalid/non-positive identifiers.
6. `test_row_count_preserved`: Validates exact row count equality before and after write.
7. `test_null_counts_preserved`: Confirms nullable columns retain precise null and non-null distributions.
8. `test_identifiers_preserved`: Asserts integer Panchayat IDs and LGD codes are unaltered.
9. `test_date_values_preserved`: Verifies target date, issue date, and lead days integrity.
10. `test_rainfall_values_preserved`: Tests quantitative precision of forecast and actual rainfall.
11. `test_read_back_pyarrow_and_pandas`: Validates interoperability between PyArrow and Pandas readers.
12. `test_repeated_execution_is_safe`: Proves idempotence and deterministic atomic file replacement.
13. `test_district_independent_execution`: Asserts pipeline converts multiple districts independently.
14. `test_raw_data_remains_untouched`: Verifies SHA-256 and modification timestamps of source files.

**Test Execution Result**: 14 / 14 tests passing in 0.70s.
