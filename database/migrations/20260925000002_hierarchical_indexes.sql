-- =============================================================================
-- Migration: Scalable Administrative Hierarchy Indexes
-- Timestamp: 2026-09-25
-- Description: Composite and functional indexes on panchayats, blocks, and districts
--              tables for high-throughput hierarchical filtering, pagination, and
--              case-insensitive search across thousands of Panchayats.
-- Safety Invariant: Safe additive indexes using IF NOT EXISTS. No table rewrites.
-- =============================================================================

-- 1. Composite block + name index for efficient block-scoped name lookups and sorting
CREATE INDEX IF NOT EXISTS idx_panchayats_block_name 
    ON panchayats (block_id, name);

-- 2. Composite block + id index for deterministic pagination
CREATE INDEX IF NOT EXISTS idx_panchayats_block_id_id 
    ON panchayats (block_id, id);

-- 3. Composite district + name index for district-scoped filtering
CREATE INDEX IF NOT EXISTS idx_panchayats_district_name 
    ON panchayats (district_id, name);

-- 4. Functional lower-case name index for case-insensitive search acceleration
CREATE INDEX IF NOT EXISTS idx_panchayats_lower_name 
    ON panchayats (lower(name));

-- 5. LGD code lookup index (non-unique to safely accommodate multi-hamlet revenue records)
CREATE INDEX IF NOT EXISTS idx_panchayats_lgd_code_lookup 
    ON panchayats (lgd_code);
