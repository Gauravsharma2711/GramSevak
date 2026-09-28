# GramSevak Scalable Administrative Database & Backend Hierarchy Foundation (Phase 3.2)

## 1. Executive Summary & Objective
Phase 3.2 establishes the database-backed domain foundation and backend repository/service architecture for the multi-district administrative hierarchy:
$$\text{District} \longrightarrow \text{Block (Tehsil/Taluka)} \longrightarrow \text{Gram Panchayat} \longrightarrow \text{Weather / Forecast / Advisory Data}$$

This implementation operationalizes the findings of the Phase 3.1 architecture audit, formalizing the domain models, data-access abstractions, idempotent backfill pipeline, and dynamic spatial resolvers required to support Nashik (15 blocks, 1,388 Panchayats), Pune (13 blocks, 1,338 Panchayats), and future districts across Maharashtra without hardcoded administrative assumptions.

---

## 2. Database Architecture
The administrative hierarchy is normalized across three relational tables in PostgreSQL/Supabase, backed by foreign keys, unique constraints, and performance indexes:
- **`districts`**: Top-level administrative territory.
- **`blocks`**: Administrative subdivision (Tehsil / Taluka) scoped to a single district.
- **`panchayats`**: Local village self-government jurisdiction with centroid coordinates and elevation.

```
┌────────────────────────────────────────────────────────┐
│                      districts                         │
│  id BIGINT PK | name TEXT UNIQUE | state | code        │
└───────────────────────────┬────────────────────────────┘
                            │ 1
                            │ (ON DELETE RESTRICT)
                            ▼ N
┌────────────────────────────────────────────────────────┐
│                        blocks                          │
│  id BIGINT PK | district_id FK | name | code           │
│  CONSTRAINT: UNIQUE(district_id, name)                 │
└───────────────────────────┬────────────────────────────┘
                            │ 1
                            │ (ON DELETE RESTRICT)
                            ▼ N
┌────────────────────────────────────────────────────────┐
│                      panchayats                        │
│  id BIGINT PK | block_id FK | district_id FK           │
│  name TEXT | lgd_code BIGINT | lat | lon | elevation   │
│  CONSTRAINT: UNIQUE(id)                                │
└───────────────────────────┬────────────────────────────┘
                            │ 1
                            ├── (ON DELETE RESTRICT)
                            ▼ N
┌────────────────────────────────────────────────────────┐
│                weather_observations                    │
│  id PK | panchayat_id FK | observation_date | rainfall │
└────────────────────────────────────────────────────────┘
```

---

## 3. Domain Models

### District Model ([`backend/app/models/district.py`](file:///c:/sih/sih26074-weather-downscaling/backend/app/models/district.py))
- `id` (BIGINT, Primary Key, autoincrement)
- `name` (TEXT, unique, nullable=False, indexed)
- `state` (TEXT, default="Maharashtra", nullable=False)
- `code` (TEXT, nullable=True)
- `created_at`, `updated_at` (TIMESTAMPTZ)
- Relationships: `blocks` (one-to-many), `panchayats` (one-to-many)

### Block Model ([`backend/app/models/block.py`](file:///c:/sih/sih26074-weather-downscaling/backend/app/models/block.py))
- `id` (BIGINT, Primary Key, autoincrement)
- `district_id` (BIGINT, ForeignKey `districts.id`, nullable=False, indexed)
- `name` (TEXT, nullable=False, indexed)
- `code` (TEXT, nullable=True)
- `created_at`, `updated_at` (TIMESTAMPTZ)
- Constraints: `UniqueConstraint("district_id", "name", name="uq_blocks_district_name")`
- Relationships: `district` (many-to-one), `panchayats` (one-to-many)

### Panchayat Model ([`backend/app/models/panchayat.py`](file:///c:/sih/sih26074-weather-downscaling/backend/app/models/panchayat.py))
- `id` (BIGINT, Primary Key)
- `lgd_code` (BIGINT, nullable=False, indexed)
- `panchayat_code` (TEXT, nullable=True)
- `name` (TEXT, nullable=False, indexed)
- `block_id` (BIGINT, ForeignKey `blocks.id`, nullable=False, indexed)
- `district_id` (BIGINT, ForeignKey `districts.id`, nullable=False, indexed)
- `latitude` (NUMERIC, nullable=True, checked between -90.0 and 90.0)
- `longitude` (NUMERIC, nullable=True, checked between -180.0 and 180.0)
- `elevation_m` (NUMERIC, nullable=True, checked between 0.0 and 3000.0)
- `created_at`, `updated_at` (TIMESTAMPTZ)
- Relationships: `district` (many-to-one), `block` (many-to-one), `weather_observations` (one-to-many), `downscaled_forecasts` (one-to-many)

---

## 4. Identifier & LGD Code Strategy
- **Internal System Identifier (`panchayats.id`)**: Stable, non-reassignable integer primary key.
  - Nashik preserves legacy sequential IDs (`1001` to `2388`).
  - Pune uses official LGD integer codes (`185262` to `299397`).
  - Both ranges are disjoint, non-overlapping, and fully compatible with downstream weather foreign keys.
- **National LGD Identifier (`panchayats.lgd_code`)**: Indexed 6-digit Local Government Directory code defined by the Ministry of Panchayati Raj (MoPR). Used for external API interoperability and national spatial data cross-referencing.
- **Display Label (`panchayats.name`)**: Normalized Title Case village string. Never used as a foreign key or URL path identifier.

---

## 5. Relational Constraints & Indexing Strategy
- **Parent-Scoped Uniqueness**: Block names repeat across India; hence `uq_blocks_district_name` enforces uniqueness per district, not globally.
- **Index Coverage**:
  - `idx_blocks_district_id` on `blocks (district_id)` for high-throughput district filtering.
  - `idx_panchayats_block_id` on `panchayats (block_id)` for sub-millisecond block-scoped pagination.
  - `idx_panchayats_district_id` on `panchayats (district_id)` for district aggregations.
  - `idx_panchayats_lgd_code` on `panchayats (lgd_code)` for national code searches.
  - `idx_panchayats_name` on `panchayats (name)` for text search indexing.

---

## 6. Migration & Backfill Strategy
- **Downtime-Safe Invariant**: ZERO drops, ZERO truncates, ZERO deletions.
- **Existing Schema Reuse**: Reused production schema verified in Phase 1.6 (`20260927000001_scalable_weather_schema.sql`).
- **Repeatable Backfill Tool**: Developed [`scripts/backfill_administrative_hierarchy.py`](file:///c:/sih/sih26074-weather-downscaling/scripts/backfill_administrative_hierarchy.py):
  - Ingests canonical Parquet datasets (`canonical_nashik.parquet` and `canonical_pune.parquet`).
  - Implements transactional upsert: running multiple times produces identical state without duplicate records.
  - Includes `--dry-run` pre-flight inspection and `--real-run` execution modes.

### Verification of Backfill Counts
| Entity | Nashik | Pune | Total System |
| :--- | :--- | :--- | :--- |
| **Districts** | 1 (ID: 1) | 1 (ID: 4) | **2** |
| **Blocks** | 15 | 13 | **28** |
| **Panchayats** | 1,388 | 1,338 | **2,726** |
| **Orphan Records** | 0 | 0 | **0** |

---

## 7. Backend Repository Layer
Implemented [`HierarchyRepository`](file:///c:/sih/sih26074-weather-downscaling/backend/app/repositories/hierarchy_repository.py):
- `get_districts(db)`: Returns all districts ordered by name.
- `get_district_by_id(db, district_id)`: Fetches single district.
- `get_district_by_name(db, name)`: Case-insensitive district lookup.
- `get_blocks_by_district(db, district_id)`: Fetches blocks under a district.
- `get_block_by_id(db, block_id, eager_district)`: Fetches block with optional parent join.
- `get_block_by_name(db, district_id, name)`: Fetches block by name under district.
- `get_panchayats_by_block(db, block_id, offset, limit, search)`: Paginated, searchable query returning `(items, total_count)` scoped by block.
- `get_panchayat_by_id(db, panchayat_id, eager_load_parents)`: Fetches single Panchayat with eager parent JOINs (`joinedload`).
- `get_panchayat_by_lgd(db, lgd_code)`: Looks up Panchayat by LGD code.
- `detect_orphans(db)`: Comprehensive foreign key integrity audit.
- `upsert_district()`, `upsert_block()`, `upsert_panchayat()`: Idempotent upsert helpers.

---

## 8. Backend Service Layer
Implemented [`HierarchyService`](file:///c:/sih/sih26074-weather-downscaling/backend/services/hierarchy_service.py):
- `resolve_panchayat_spatial_context(panchayat_id)`: Authoritatively extracts spatial coordinates (`latitude`, `longitude`, `elevation_m`), parent block name, and parent district name.
- `validate_hierarchy_parentage(panchayat_id, expected_block_id, expected_district_id)`: Validates that a Panchayat belongs to the claimed parent administrative entities, raising `HierarchyParentageMismatchError` on tampering or spoofing.
- `get_hierarchy_summary()`: Produces a district-by-district breakdown and orphan health report.

---

## 9. Dynamic Spatial Resolution & Migration of Legacy Queries
- **Fixed Hardcoded Spatial Fallback**: Refactored `_resolve_panchayat_spatial_names` in [`src/services/advisory_service.py`](file:///c:/sih/sih26074-weather-downscaling/src/services/advisory_service.py) to query the normalized `Panchayat` model first.
  - Previous behavior: If not in weather table, hardcoded `"district_name": "Nashik"`.
  - New behavior: Dynamically resolves the true district (`Pune`, `Nashik`, or future district) and block name from the database.

---

## 10. ML & Downstream Compatibility
- **ML Downscaling Compatibility**: Phase 2 XGBoost Downscaler (`POST /api/v1/forecast/downscale`) verified 100% operational with dynamically resolved spatial context.
- **Weather Observations Compatibility**: All 188,708 historical weather rows link cleanly to `panchayats.id`.
- **Downscaled Forecasts Compatibility**: All generated forecast rows link cleanly to `panchayats.id`.

---

## 11. Automated Test Suite
Implemented [`tests/test_hierarchy_foundation.py`](file:///c:/sih/sih26074-weather-downscaling/tests/test_hierarchy_foundation.py):
- **18 new tests** covering domain models, repository methods, service methods, parentage validation, orphan detection, backfill dry-run, and ML inference compatibility.
- **Full suite passed**: 18/18 passed in `test_hierarchy_foundation.py` and 23/23 passed in regression suite.

---

## 12. Phase 3.3 Readiness
Phase 3.2 is **100% COMPLETE**. The database foundation, domain models, repository layer, and service layer are operational. Phase 3.3 can now build the public REST hierarchy endpoints (`GET /api/v1/districts`, `GET /api/v1/districts/{id}/blocks`, `GET /api/v1/blocks/{id}/panchayats`, `GET /api/v1/panchayats/{id}`) on top of this foundation.
