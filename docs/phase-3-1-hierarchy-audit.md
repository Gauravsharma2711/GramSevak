# GramSevak Hierarchy Architecture Audit (Phase 3.1)

## 1. Executive Summary & Objective
Phase 3.1 establishes the architectural foundation for a robust, multi-district administrative hierarchy:
$$\text{District} \longrightarrow \text{Block (Tehsil/Taluka)} \longrightarrow \text{Gram Panchayat} \longrightarrow \text{Weather / Advisory Telemetry}$$

The primary objective is to audit the entire repository (database, backend API, React officer dashboard, Flutter mobile app, and ML inference pipeline) to eliminate hardcoded district/block assumptions and define an enterprise-grade, configuration-driven, scalable architecture capable of supporting Nashik, Pune, and future districts across Maharashtra and India.

---

## 2. Current Architecture Overview
The GramSevak repository is organized into five operational tiers:
1. **Database Layer** (`database/`, `supabase/`): PostgreSQL hosted on Supabase, featuring normalized relational schemas with Row Level Security (RLS) policies and composite spatio-temporal indexes.
2. **Backend API Layer** (`backend/`): FastAPI application exposing OpenAPI v3 REST endpoints (`/api/v1/*`) with Pydantic schemas, SQLAlchemy ORM, and dependency-injected database sessions.
3. **Machine Learning Pipeline** (`ml/`, `backend/ml/`): Production XGBoost downscaling pipeline (v2.5.0) and feature engineering registry (`schemas/ml_feature_registry.json`) locked in Phase 2.
4. **Officer Web Dashboard** (`officer_dashboard/`): React 18 SPA built with Vite, TypeScript, and Tailwind CSS for district agricultural officers.
5. **Farmer Mobile Application** (`farmer_app/`): Flutter cross-platform mobile application supporting localized weather alerts and agronomic advisories for smallholder farmers.

---

## 3. Current Hierarchy Representation
The hierarchy is represented in the relational database across three primary entities:
- **`districts`**: Represents administrative districts (e.g., Nashik, Pune).
- **`blocks`**: Represents administrative tehsils/talukas within a district.
- **`panchayats`**: Represents village Gram Panchayats with centroid coordinates and elevation.

### Schema Relationships
```
districts (id PK, name UNIQUE, state, code)
    │  1
    │  └──< Has Many
    ▼  N
blocks (id PK, district_id FK -> districts.id, name, code, UNIQUE(district_id, name))
    │  1
    │  └──< Has Many
    ▼  N
panchayats (id PK, block_id FK -> blocks.id, district_id FK -> districts.id,
            lgd_code, name, latitude, longitude, elevation_m)
    │  1
    ├──< Has Many
    ▼  N
weather_observations (id PK, panchayat_id FK -> panchayats.id, observation_date, ...)
    │  1
    ├──< Has Many
    ▼  N
downscaled_forecasts (id PK, panchayat_id FK -> panchayats.id, forecast_date, ...)
```

---

## 4. Database Schema Audit
Inspected migrations [`database/migrations/20260925000001_multi_district_architecture.sql`](file:///c:/sih/sih26074-weather-downscaling/database/migrations/20260925000001_multi_district_architecture.sql) and [`database/migrations/20260927000001_scalable_weather_schema.sql`](file:///c:/sih/sih26074-weather-downscaling/database/migrations/20260927000001_scalable_weather_schema.sql).

### Table Structure & Foreign Keys
- **Primary Keys**: All administrative tables use `BIGINT` primary keys (`districts.id`, `blocks.id`, `panchayats.id`).
- **Foreign Keys**:
  - `blocks.district_id` $\to$ `districts.id` (`ON DELETE RESTRICT`)
  - `panchayats.block_id` $\to$ `blocks.id` (`ON DELETE RESTRICT`)
  - `panchayats.district_id` $\to$ `districts.id` (`ON DELETE RESTRICT`)
  - `weather_observations.panchayat_id` $\to$ `panchayats.id` (`ON DELETE RESTRICT`)
  - `downscaled_forecasts.panchayat_id` $\to$ `panchayats.id` (`ON DELETE RESTRICT`)
- **Unique Constraints**:
  - `blocks`: `uq_blocks_district_name` (`district_id`, `name`)
  - `panchayats`: `uq_panchayats_id` (`id`)
  - `block_forecasts`: `uq_block_forecasts` (`district_name`, `block_name`, `forecast_issue_date`, `forecast_date`, `source_model`)
  - `weather_observations`: `uq_weather_observations` (`panchayat_id`, `observation_date`)
- **Indexes**:
  - `idx_blocks_district_id` on `blocks (district_id)`
  - `idx_panchayats_block_id` on `panchayats (block_id)`
  - `idx_panchayats_district_id` on `panchayats (district_id)`
  - `idx_panchayats_lgd_code` on `panchayats (lgd_code)`
  - `idx_panchayats_name` on `panchayats (name)`

---

## 5. Administrative Data Audit
Derived from actual Supabase verification artifacts ([`reports/phase-1-8-final-data-verification.json`](file:///c:/sih/sih26074-weather-downscaling/reports/phase-1-8-final-data-verification.json)):

| Entity | Nashik | Pune | Total | Integrity Status |
| :--- | :--- | :--- | :--- | :--- |
| **Districts** | 1 (ID: 1) | 1 (ID: 4) | **2** | PASS (Zero duplicates) |
| **Blocks (Tehsils)** | 15 | 13 | **28** | PASS (Zero orphans) |
| **Gram Panchayats** | 1,388 | 1,338 | **2,726** | PASS (Zero orphans) |
| **Weather Observations** | 1,388 | 187,320 | **188,708** | PASS (Zero unlinked rows) |

### Block Coverage
- **Nashik (15 Blocks)**: Baglan (Satana), Malegaon, Kalwan, Deola, Surgana, Dindori, Chandwad, Nandgaon, Niphad, Yeola, Nashik, Peint, Trimbakeshwar, Igatpuri, Sinnar.
- **Pune (13 Blocks)**: Ambegaon, Baramati, Bhor, Daund, Haveli, Indapur, Junnar, Khed (Rajgurunagar), Maval, Mulshi (Paud), Pune City, Shirur (Ghodnadi), Velhe.

### Orphan Records
- Orphan blocks: `0`
- Orphan Panchayats without block: `0`
- Orphan Panchayats without district: `0`
- Orphan weather observations: `0`

---

## 6. Identifier Audit
A key discovery of the audit is the historical distinction in Panchayat identifiers between districts:

| Attribute | Nashik Convention | Pune Convention | Target Standard |
| :--- | :--- | :--- | :--- |
| **Internal Primary Key (`id`)** | Arbitrary sequential (1001 to 2388) | Official MoPR LGD Code (e.g., 185262) | Stable `BIGINT` Primary Key (`panchayats.id`) |
| **Official MoPR Code (`lgd_code`)** | 6-digit LGD Code (e.g., 182597) | 6-digit LGD Code (e.g., 185262) | Standardized indexed `lgd_code` |
| **External API Identifier** | `panchayat_id` | `panchayat_id` | Uniform numeric `panchayat_id` |
| **Display Name** | Title Case Village Name | Title Case Village Name | Canonical `name` |

### Architectural Invariant
- Never use village or block strings as database keys.
- All foreign keys and API parameters must accept stable numeric identifiers (`panchayat_id`, `block_id`, `district_id`).
- Support search and lookup by both system `panchayat_id` and official `lgd_code`.

---

## 7. Hardcoded Location Logic Audit

### Findings & Classification
| File Location | Line(s) | Description | Classification | Action Required in Phase 3 |
| :--- | :--- | :--- | :--- | :--- |
| `backend/app/api/v1/endpoints/panchayats.py` | 110-174 | Flat `GET /api/v1/panchayats` groups over 188k `PanchayatWeatherData` rows | Legacy application logic | Refactor to query normalized `panchayats` table |
| `src/services/advisory_service.py` | 88-91 | Fallback spatial resolver defaults to `"district_name": "Nashik"` | Temporary fallback logic | Replace with dynamic lookup from `panchayats` table |
| `officer_dashboard/src/App.tsx` | 50-51 | Default state `selectedDistrictId = 1`, `selectedDistrictName = 'Nashik'` | Hardcoded UI default | Make configuration-driven or dynamically load first district |
| `officer_dashboard/src/App.tsx` | 68-71 | `loadData()` calls flat `getPanchayats()` without district scoping | Flawed API consumption | Update to use scoped `/districts/{id}/blocks` and `/blocks/{id}/panchayats` |
| `officer_dashboard/src/services/api.ts` | 183-186 | Fallback `getDistricts()` hardcodes `Nashik` and `Pune` | Resilient offline mock | Keep as offline mock but ensure backend is primary |
| `officer_dashboard/src/services/api.ts` | 197-205 | Fallback `getDistrictBlocks()` returns 7 hardcoded Nashik blocks | Resilient offline mock | Expand mock or make dynamic |
| `farmer_app/lib/main.dart` | 74 | `_selectedPanchayatId = 1001` (Ajmer Saundane, Baglan) | Hardcoded initial pilot village | Make user-selectable with persistent shared preferences |
| `farmer_app/lib/repositories/farmer_repository.dart` | 14-55 | `fallbackPanchayats` has 4 static Nashik Panchayats | Resilient offline mock | Retain as offline fallback, load dynamic list when connected |
| `farmer_app/lib/widgets/panchayat_picker_sheet.dart` | 46 | `_selectedDistrict = DistrictItem(id: 1, name: 'Nashik')` | Hardcoded initial state | Initialize with dynamic district list from API |

---

## 8. Backend API Audit
The backend currently exposes both modern hierarchical endpoints and legacy flat endpoints:

### Existing Endpoints in [`backend/app/api/v1/endpoints/panchayats.py`](file:///c:/sih/sih26074-weather-downscaling/backend/app/api/v1/endpoints/panchayats.py)
1. **`GET /api/v1/districts`**: Returns list of all administrative districts (`DistrictItem`).
2. **`GET /api/v1/districts/{district_id}/blocks`**: Returns blocks for a district.
3. **`GET /api/v1/blocks/{block_id}/panchayats`**: Returns paginated, searchable Panchayats scoped to a block.
4. **`GET /api/v1/panchayats/{panchayat_id}`**: Retrieves single Panchayat metadata by ID.
5. **`GET /api/v1/panchayats`**: Legacy un-scoped flat listing (queries time-series table, inefficient).

---

## 9. Frontend React Dashboard Audit
- **Jurisdiction Selection**: Uses [`HierarchicalPanchayatSelector.tsx`](file:///c:/sih/sih26074-weather-downscaling/officer_dashboard/src/components/HierarchicalPanchayatSelector.tsx) which supports cascading `district -> block -> panchayat` step navigation.
- **Weakness**: In [`App.tsx`](file:///c:/sih/sih26074-weather-downscaling/officer_dashboard/src/App.tsx), selecting a district or block does not filter the main advisory review queue or metric cards. The dashboard still queries `getPanchayats()` globally.
- **Remediation Plan**: In Phase 3.3, wire the global district/block state from `App.tsx` directly into the advisory review queue and forecast generation modal.

---

## 10. Flutter Mobile App Audit
- **Location Selection**: Uses [`panchayat_picker_sheet.dart`](file:///c:/sih/sih26074-weather-downscaling/farmer_app/lib/widgets/panchayat_picker_sheet.dart) which implements 3-step hierarchical selection.
- **Weakness**: Default initial district is hardcoded to Nashik (`id: 1`) and pilot Panchayat `1001`.
- **Remediation Plan**: Allow farmers to select any district (Nashik, Pune, or future districts) and persist the selected Panchayat ID in device local storage.

---

## 11. ML Dependency Audit
- **Inference Invariant**: [`DownscaleInferenceRequest`](file:///c:/sih/sih26074-weather-downscaling/backend/ml/schemas.py) in Phase 2 requires `panchayat_id`, `forecast_date`, `forecast_issue_date`, `block_forecast_rainfall_mm`, and spatial coordinates (`panchayat_latitude`, `panchayat_longitude`, `elevation_m`).
- **Zero Breakage Guarantee**: The ML model is district-agnostic; it operates purely on spatial coordinates, elevation, and numerical forecast features. Expanding the administrative hierarchy to Pune or future districts will **NOT** break ML inference as long as valid coordinates and block forecasts are supplied.

---

## 12. Current Scalability Problems
1. **Unbounded Flat Panchayat Queries**: Loading 2,726+ Panchayats into mobile or web memory causes severe latency and packet bloat.
2. **Expensive Aggregation Queries**: The legacy `GET /api/v1/panchayats` groups over 188,708 rows in `panchayat_weather_data` rather than querying the indexed `panchayats` table.
3. **Hardcoded Fallbacks**: Static mocks in React and Flutter only include Nashik, hiding Pune when operating in offline/fallback mode.

---

## 13. Target Scalable Architecture
```
                                 ┌────────────────────────┐
                                 │   GET /api/v1/districts│
                                 └───────────┬────────────┘
                                             │ (Select District)
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │GET /api/v1/districts/{district_id}/blocks│
                        └────────────────────┬────────────────────┘
                                             │ (Select Block)
                                             ▼
                 ┌───────────────────────────────────────────────────────┐
                 │GET /api/v1/blocks/{block_id}/panchayats?page=1&size=50│
                 └───────────────────────────┬───────────────────────────┘
                                             │ (Select Panchayat)
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │GET /api/v1/forecast/downscale                 │
                     │GET /api/v1/farmer/panchayat/{panchayat_id}    │
                     └───────────────────────────────────────────────┘
```

---

## 14. Target REST API Contract
The official Phase 3 administrative hierarchy API contract:

### 1. `GET /api/v1/districts`
- **Purpose**: List all active districts.
- **Response**: `[ { "id": 1, "name": "Nashik", "state": "Maharashtra", "code": "NSK" }, ... ]`
- **Cache**: 24 hours (immutable reference data).

### 2. `GET /api/v1/districts/{district_id}/blocks`
- **Purpose**: List all blocks under a district.
- **Parameters**: `district_id` (int, path, required).
- **Response**: `[ { "id": 1, "district_id": 1, "name": "Baglan", "code": "BGL" }, ... ]`
- **Cache**: 24 hours.

### 3. `GET /api/v1/blocks/{block_id}/panchayats`
- **Purpose**: Paginated list of Panchayats in a block.
- **Parameters**:
  - `block_id` (int, path, required)
  - `page` (int, query, default: 1)
  - `page_size` (int, query, default: 50, max: 200)
  - `search` (string, query, optional, min: 1, max: 100)
- **Response**:
  ```json
  {
    "total": 138,
    "page": 1,
    "page_size": 50,
    "total_pages": 3,
    "items": [
      {
        "id": 1001,
        "lgd_code": 182597,
        "name": "Ajmer Saundane",
        "block_id": 1,
        "district_id": 1,
        "latitude": 20.6385,
        "longitude": 74.1201,
        "elevation_m": 585.0
      }
    ]
  }
  ```

### 4. `GET /api/v1/panchayats/{panchayat_id}`
- **Purpose**: Retrieve detailed metadata for a single Panchayat.
- **Parameters**: `panchayat_id` (int, path, required).
- **Response**: Full geographic, terrain, block, and district metadata.

---

## 15. Pagination & Search Specifications
- **Bounded Pagination**: Maximum `page_size` enforced at 200 items. Default is 50 items.
- **Deterministic Sorting**: Always order by `name ASC, id ASC` to prevent duplicate or skipped items across pages.
- **Server-Side Search**: Case-insensitive substring matching (`ILIKE %query%`) over `name`, `lgd_code::text`, and `id::text`.
- **Debounced Input**: Frontend clients must debounce search queries by at least 300 ms.

---

## 16. Security & Access Boundary
- **Public Read Access**: Hierarchy endpoints (`/districts`, `/blocks`, `/panchayats`) are public read-only (`RLS FOR SELECT USING (true)`).
- **Zero Secret Leakage**: No Supabase service-role keys, database connection strings, or internal infrastructure details are exposed.
- **Sanitized Outputs**: Error messages must not leak SQL syntax or server stack traces.

---

## 17. Performance Strategy
- **Index Coverage**: Verified indexes on `blocks(district_id)`, `panchayats(block_id)`, `panchayats(name)`, `panchayats(lgd_code)`.
- **Query Elimination**: Eliminate `group_by` scans on `panchayat_weather_data`.
- **Response Caching**: Reference administrative datasets (districts, blocks) are virtually static and can be cached with `Cache-Control: public, max-age=86400`.

---

## 18. Backward Compatibility Requirements
- Existing endpoints `POST /api/v1/forecast/downscale` and `GET /api/v1/farmer/panchayat/{panchayat_id}` must continue to accept numeric `panchayat_id`.
- The legacy endpoint `GET /api/v1/panchayats` must be maintained for backward compatibility with older client versions, but rewritten to query `panchayats` directly.

---

## 19. Phase 3.2 Implementation Plan
Based on this audit, Phase 3.2 should execute:
1. **Refactor Legacy API**: Optimize `GET /api/v1/panchayats` to query the normalized `panchayats` table with indexed filters.
2. **Remove Hardcoded Fallbacks**: Replace static Nashik fallbacks in `src/services/advisory_service.py` with dynamic database queries.
3. **Harmonize Identifiers**: Ensure both Nashik (1001-2388) and Pune (185262+) Panchayats resolve seamlessly across all endpoints.
4. **Backend Test Coverage**: Expand automated test suite covering multi-district hierarchy queries, pagination boundaries, and search edge cases.

---

## 20. Known Limitations
1. **Historical ID Gap**: Nashik uses sequential surrogate IDs (1001-2388) while Pune uses official LGD codes (185262+). Both are fully supported in `panchayats.id`, with original LGD codes preserved in `panchayats.lgd_code`.
2. **Frontend Offline Mocks**: Full offline sync for all 2,726 Panchayats is not feasible without local SQLite storage. Bounded local caching of recent/favorited Panchayats should be designed in subsequent subphases.
