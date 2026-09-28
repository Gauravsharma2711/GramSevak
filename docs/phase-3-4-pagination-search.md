# Phase 3.4 — Pagination & Server-Side Search for Administrative Hierarchy REST APIs

## 1. What Changed

In Phase 3.4, the District → Block → Panchayat REST APIs implemented in Phase 3.3 were extended with robust, scalable server-side pagination and search capabilities. 

Specific changes made:
1. **Pydantic Schemas (`backend/app/schemas/panchayat.py`)**:
   - `DistrictListResponse`: Extended to include standard pagination metadata (`total`, `page`, `page_size`, `total_pages`, `items`).
   - `BlockListResponse`: Extended to include standard pagination metadata (`total`, `page`, `page_size`, `total_pages`, `items`).
   - `PanchayatListResponse`: Retained canonical pagination metadata with `PanchayatResponse` items.
2. **Repository Layer (`backend/app/repositories/hierarchy_repository.py`)**:
   - Added `get_districts_paginated(db, offset, limit, search)` supporting parameterized ILIKE search, deterministic `ORDER BY name ASC, id ASC`, and SQL `LIMIT` / `OFFSET`.
   - Added `get_blocks_by_district_paginated(db, district_id, offset, limit, search)` strictly scoping queries to `district_id`, supporting search on `name` or string ID, deterministic ordering, and SQL `LIMIT` / `OFFSET`.
   - Preserved unpaginated `get_districts` and `get_blocks_by_district` for domain maintenance and existing foundation utilities.
3. **Domain Service Layer (`backend/services/hierarchy_service.py`)**:
   - Updated `list_districts(page, page_size, search, db)` to compute zero-based offsets and return `(items, total)`.
   - Updated `list_blocks_by_district(district_id, page, page_size, search, db)` to validate district existence (returning 404 if missing) and return `(items, total)`.
   - Maintained `list_panchayats_by_block(block_id, page, page_size, search, db)` and `get_panchayat_detail(panchayat_id, db)`.
4. **API Endpoint Layer (`backend/app/api/v1/endpoints/panchayats.py`)**:
   - `GET /api/v1/districts`: Accepts `page`, `page_size`, `search` query parameters, returns `DistrictListResponse`.
   - `GET /api/v1/districts/{district_id}/blocks`: Accepts `page`, `page_size`, `search` query parameters, returns `BlockListResponse`.
   - `GET /api/v1/blocks/{block_id}/panchayats`: Validated bounds (`page >= 1`, `page_size 1..200`, `search min=1, max=100`), returns `PanchayatListResponse`.
   - `GET /api/v1/panchayats/{panchayat_id}`: Retained single-resource detail lookup returning `PanchayatDetailResponse`.

---

## 2. Pagination Contract

All collection endpoints follow a uniform, predictable pagination contract:

### Query Parameters
| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `page` | int | 1 | `>= 1` | 1-indexed page number |
| `page_size` | int | 20 (Districts, Blocks) / 50 (Panchayats) | `>= 1, <= 100` (Districts, Blocks), `<= 200` (Panchayats) | Items per page |
| `search` | str | null | `min_length=1, max_length=100` | Optional search term |

### Response Envelope
```json
{
  "total": 36,
  "page": 1,
  "page_size": 20,
  "total_pages": 2,
  "items": [
    { ... }
  ]
}
```

### Deterministic Ordering
- **Districts**: `ORDER BY name ASC, id ASC`
- **Blocks**: `ORDER BY name ASC, id ASC`
- **Panchayats**: `ORDER BY name ASC, id ASC`

No nondeterministic or database-internal physical ordering is ever exposed.

---

## 3. Search Contract

1. **Case-Insensitive**: Implemented using PostgreSQL `ILIKE` via SQLAlchemy (`func.lower(...).ilike(f"%{search.strip().lower()}%")`).
2. **Search Fields**:
   - **Districts**: `name`, `id` (as text), `state`
   - **Blocks**: `name`, `id` (as text)
   - **Panchayats**: `name`, `lgd_code` (as text), `id` (as text)
3. **Scoping**:
   - Block search is strictly scoped to the parent `district_id` (`WHERE district_id = :d AND (...)`).
   - Panchayat search is strictly scoped to the parent `block_id` (`WHERE block_id = :b AND (...)`).
   - Searching for "Haveli" (Pune) in Nashik returns `total: 0, items: []`. No cross-district or cross-block leakage.

---

## 4. Query Behavior & Database Efficiency

All queries execute strictly at the database layer. No full-table scans or in-memory slicing in Python.

### Query Plan & Parameter Binding
1. **Total Count**:
   ```sql
   SELECT count(*) FROM districts WHERE lower(name) ILIKE :p;
   ```
2. **Paginated Data Retrieval**:
   ```sql
   SELECT id, name, code, state 
   FROM districts 
   WHERE lower(name) ILIKE :p 
   ORDER BY name ASC, id ASC 
   LIMIT :limit OFFSET :offset;
   ```
3. **Blocks Scoped Query**:
   ```sql
   SELECT id, district_id, name, code 
   FROM blocks 
   WHERE district_id = :d AND lower(name) ILIKE :p 
   ORDER BY name ASC, id ASC 
   LIMIT :limit OFFSET :offset;
   ```
4. **Panchayats Scoped Query**:
   ```sql
   SELECT id, lgd_code, name, block_id, district_id, latitude, longitude, elevation_m 
   FROM panchayats 
   WHERE block_id = :b AND (lower(name) ILIKE :p OR CAST(lgd_code AS VARCHAR) ILIKE :p) 
   ORDER BY name ASC, id ASC 
   LIMIT :limit OFFSET :offset;
   ```

### Indexes Utilized
- `districts`: `districts_pkey` (id), `districts_name_key` (name), `idx_districts_name`
- `blocks`: `blocks_pkey` (id), `idx_blocks_district_id` (district_id), `uq_blocks_district_name` (district_id, name)
- `panchayats`: `uq_panchayats_id` (id), `idx_panchayats_block_id` (block_id), `idx_panchayats_block_name` (block_id, name), `idx_panchayats_lower_name` (lower(name)), `idx_panchayats_lgd_code` (lgd_code)

---

## 5. Validation Rules

FastAPI Path and Query annotations strictly validate all input parameters before SQL execution:
- `page < 1`: HTTP 422 Unprocessable Entity
- `page_size < 1` or `page_size > 100` (or `> 200`): HTTP 422 Unprocessable Entity
- `search` exceeding 100 characters: HTTP 422 Unprocessable Entity
- Malformed resource IDs (`0`, `-5`, string `"abc"`): HTTP 422 Unprocessable Entity
- Non-existent parent IDs: HTTP 404 Not Found (e.g. `District with ID 999999 not found.`)

---

## 6. Empty Results Handling

Empty states are handled cleanly as HTTP 200 OK responses with valid pagination metadata:
- Search with 0 matches: `{"total": 0, "page": 1, "page_size": 20, "total_pages": 0, "items": []}`
- Valid page beyond available results: `{"total": 15, "page": 10, "page_size": 5, "total_pages": 3, "items": []}`
- District with 0 blocks: `{"total": 0, "page": 1, "page_size": 20, "total_pages": 0, "items": []}`
- Block with 0 panchayats: `{"total": 0, "page": 1, "page_size": 50, "total_pages": 0, "items": []}`

---

## 7. Backward Compatibility

1. **Deliberate Response Shape Change**:
   - `GET /api/v1/districts` and `GET /api/v1/districts/{district_id}/blocks` now return the canonical pagination envelope `{ items: [...], total, page, page_size, total_pages }` instead of a raw JSON array `[...]`.
   - This change was explicitly planned in Phase 3.3 documentation to standardize all collection endpoints across the GramSevak API.
2. **Frontend Safety**:
   - The Flutter repository has a built-in `if (data is List)` check with fallback to offline data, preventing mobile app crashes until Phase 3.5 frontend integration.
   - The React Officer Dashboard has error catch boundaries with fallback mock data.
   - Per requirements, frontend code is untouched in Phase 3.4 and will be upgraded in Phase 3.5.
3. **Single-Resource Unchanged**:
   - `GET /api/v1/panchayats/{panchayat_id}` remains an unpaginated single-resource detail lookup.
4. **Legacy Weather Endpoint**:
   - `GET /api/v1/panchayats` remains untouched for legacy callers.

---

## 8. Testing Performed

All 83 automated test cases pass:
- **`tests/test_hierarchy_api.py` (27 tests)**:
  - Default pagination across districts, blocks, panchayats
  - Custom pagination parameters & boundary values
  - Maximum page size enforcement
  - Case-insensitive search across all tiers
  - No-match search behavior
  - Page beyond available results
  - Input validation (422 on page=0, negative, oversized page_size, oversized search)
  - Parent scoping & cross-hierarchy search isolation
  - 404 on non-existent parent IDs
  - Clean payloads & deterministic ordering
  - Health & forecast regression
- **`tests/test_hierarchy_foundation.py` (18 tests)**: All repository and domain integrity tests pass.
- **`tests/test_hierarchical_architecture.py` (10 tests)**: Architecture contracts pass.
- **`tests/test_multi_district_architecture.py` (8 tests)**: Multi-district data-serving passes.
- **`tests/test_model_packaging_and_api.py` (13 tests)**: ML inference pipeline passes.
- **`tests/test_health.py` (7 tests)**: Health checks pass.

---

## 9. Known Limitations

1. **Network Latency in TestClient**:
   - The test environment connects to a remote Supabase instance, resulting in network round-trip latency. In production, local PostgreSQL / PgBouncer pooling will yield single-digit millisecond response times.
2. **Fuzzy Spelling Correction**:
   - Search uses SQL `ILIKE %query%`. Phonetic matching or Levenshtein distance (e.g. pg_trgm) is not enabled as strict exact/substring search satisfies current requirements.
