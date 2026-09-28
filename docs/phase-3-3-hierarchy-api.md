# Phase 3.3 — Scalable Administrative Hierarchy REST APIs

## Overview

Phase 3.3 exposes the Phase 3.2 administrative hierarchy (District → Block → Panchayat) through versioned REST APIs under `/api/v1/`. All endpoints are database-backed, use parameterized queries via the HierarchyService/HierarchyRepository stack, and are ready for React and Flutter integration.

## API Architecture

```
API Route Handler (panchayats.py)
    ↓
Request Validation (FastAPI Path/Query params, Pydantic schemas)
    ↓
HierarchyService (backend/services/hierarchy_service.py)
    ↓
HierarchyRepository (backend/app/repositories/hierarchy_repository.py)
    ↓
SQLAlchemy ORM → PostgreSQL (Supabase)
```

All hierarchy endpoints follow FastAPI dependency injection. The `HierarchyService` singleton is injected via `Depends(get_hierarchy_service)`.

## Endpoints

### 1. List Districts

```
GET /api/v1/districts
```

**Purpose**: Return all configured administrative districts in deterministic alphabetical order.

**Response** (`200 OK`):
```json
[
  {
    "id": 1,
    "name": "Nashik",
    "code": null,
    "state": "Maharashtra"
  },
  {
    "id": 4,
    "name": "Pune",
    "code": null,
    "state": "Maharashtra"
  }
]
```

**Notes**:
- Returns a flat list (backward-compatible with existing frontend consumers).
- No nested blocks or panchayats (lightweight payload).
- Deterministic ordering by `name ASC`.
- Fallback to legacy `panchayat_weather_data` distinct district names if the `districts` table is empty.

### 2. List Blocks by District

```
GET /api/v1/districts/{district_id}/blocks
```

**Path Parameters**:
| Parameter | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `district_id` | int | `>= 1` | Unique district identifier |

**Response** (`200 OK`):
```json
[
  {
    "id": 1,
    "district_id": 1,
    "name": "Baglan",
    "code": null
  }
]
```

**Errors**:
| Code | Condition |
|------|-----------|
| `404` | District with the given ID does not exist |
| `422` | Malformed district ID (0, negative, non-integer) |

**Empty state**: Returns `200 OK` with `[]` if the district exists but has no blocks.

### 3. List Panchayats by Block

```
GET /api/v1/blocks/{block_id}/panchayats
```

**Path Parameters**:
| Parameter | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `block_id` | int | `>= 1` | Unique block identifier |

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | str | null | Case-insensitive search on name/LGD code |
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 50 | Items per page (1-200) |

**Response** (`200 OK`):
```json
{
  "total": 132,
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
      "elevation_m": 585.0,
      "panchayat_id": 1001,
      "panchayat_name": "Ajmer Saundane"
    }
  ]
}
```

**Errors**:
| Code | Condition |
|------|-----------|
| `404` | Block with the given ID does not exist |
| `422` | Malformed block ID |

**Empty state**: Returns `200 OK` with `{"total": 0, "items": [], ...}` if block exists but has no panchayats.

### 4. Panchayat Detail

```
GET /api/v1/panchayats/{panchayat_id}
```

**Path Parameters**:
| Parameter | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `panchayat_id` | int | `>= 1` | Unique panchayat identifier |

**Response** (`200 OK`):
```json
{
  "panchayat_id": 1001,
  "lgd_code": 182597,
  "panchayat_name": "Ajmer Saundane",
  "block_name": "Baglan",
  "district_name": "Nashik",
  "latitude": 20.6385,
  "longitude": 74.1201,
  "elevation_m": 585.0,
  "id": 1001,
  "name": "Ajmer Saundane",
  "block_id": 1,
  "district_id": 1
}
```

**Errors**:
| Code | Condition |
|------|-----------|
| `404` | Panchayat not found |
| `422` | Malformed panchayat ID |

## Response Schemas

| Schema | Purpose |
|--------|---------|
| `DistrictResponse` | District list item (id, name, code, state) |
| `BlockResponse` | Block list item (id, district_id, name, code) |
| `PanchayatResponse` | Panchayat list item with spatial coordinates |
| `PanchayatListResponse` | Paginated envelope for block panchayats |
| `PanchayatDetailResponse` | Full panchayat detail with administrative metadata |

Backward-compatibility aliases (`DistrictItem`, `BlockItem`, `BlockPanchayatItem`, `BlockPanchayatPagination`) are preserved for existing consumers.

## Error Behavior

- **Invalid ID format** → `422 Unprocessable Entity` (FastAPI built-in validation)
- **Parent not found** → `404 Not Found` with `{"detail": "... not found."}`
- **Resource not found** → `404 Not Found`
- **Database failure** → `500 Internal Server Error` (logged internally, no SQL/stack traces exposed)

## Authentication

Hierarchy endpoints follow the existing project convention: **no authentication required** for read-only administrative data. This is consistent with the existing `/api/v1/panchayats` and `/api/v1/districts` endpoints.

## Query Strategy

| Endpoint | Query | Index Used |
|----------|-------|------------|
| Districts | `SELECT ... FROM districts ORDER BY name` | `districts_pkey` |
| Blocks | `SELECT ... FROM blocks WHERE district_id = ? ORDER BY name` | `ix_blocks_district_id` |
| Panchayats | `SELECT ... FROM panchayats WHERE block_id = ? ORDER BY name, id LIMIT ? OFFSET ?` | `ix_panchayats_block_id` |
| Panchayat detail | `SELECT ... FROM panchayats LEFT JOIN blocks, districts WHERE id = ?` | `panchayats_pkey` |

All queries use parameterized bindings via SQLAlchemy. No string concatenation. No N+1 patterns.

## Test Coverage

17 tests in `tests/test_hierarchy_api.py`:

1. District listing with deterministic ordering
2. District payload cleanliness (no DB internals)
3. Block retrieval for Nashik (15 blocks) and Pune (13 blocks)
4. Invalid district → 404
5. Malformed district ID → 422
6. Empty district → 200 with empty list
7. Panchayat retrieval by block with pagination
8. Invalid block → 404
9. Malformed block ID → 422
10. Empty block → 200 with empty items
11. Panchayat detail for Nashik and Pune
12. Missing panchayat → 404
13. Malformed panchayat ID → 422
14. Cross-hierarchy isolation (Baglan panchayats not in Dindori/Haveli)
15. No special-case district routes
16. Health endpoint regression
17. Forecast endpoint regression

## Performance Observations

Measured via TestClient (includes Supabase network latency):

| Endpoint | Latency | Items |
|----------|---------|-------|
| Districts | ~1640 ms | 2 |
| Blocks (Nashik) | ~2549 ms | 15 |
| Panchayats (Baglan, page 1) | ~2720 ms | 132 total |
| Panchayat Detail (1001) | ~1669 ms | 1 |

> **Note**: Latencies include remote Supabase network round-trips. Production behind a local PostgreSQL or connection pool will be significantly faster.

## Phase 3.4 Readiness

The API architecture is designed for clean pagination/search extension:

- `PanchayatListResponse` already includes `total`, `page`, `page_size`, `total_pages` fields.
- District and Block list endpoints return flat lists; Phase 3.4 can wrap them in `{"items": [...], "total": N}` envelopes without breaking existing structure.
- Repository methods already accept `offset`, `limit`, and `search` parameters.
- No full dataset loading — all queries use `LIMIT/OFFSET` at the database level.
