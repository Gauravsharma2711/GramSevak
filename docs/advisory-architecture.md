# Phase 5 Weather Intelligence + Agricultural Advisory System Architecture & Data Contracts

**Status:** Architecture & Contracts Defined  
**Scope:** GramSevak Backend (`backend.app.schemas.advisory_contracts`, `src.advisory.lifecycle`, `src.advisory.safety_rules`, `src.advisory.context_builder`)  
**Pipeline:** IMD Block Forecast → Panchayat-Level Downscaling → Panchayat Forecast → Deterministic Risk/Rule Layer → AI Advisory → Safety Validation → Officer Review → Approved Farmer Advisory

---

## 1. Target Pipeline Overview

```mermaid
flowchart TD
    A[IMD Block Forecast] -->|NWP Ingestion| B[Phase 2 ML Downscaling Engine]
    B -->|XGBoost / RF Inference| C[Panchayat-Level Forecast]
    C -->|Deterministic Risk Evaluation| D[Agricultural Risk & Rule Layer]
    D -->|Structured Context Assembly| E[AI Advisory Layer]
    E -->|Structured Output Generation| F[Safety Validation Layer]
    F -->|Validation PASS| G[Officer Review Queue]
    F -->|Validation FAIL: Fallback| D
    G -->|Officer APPROVE| H[Approved Farmer Advisory]
    G -->|Officer REJECT| I[Discarded / Draft Revision]
    H -->|Delivery API| J[Farmer Mobile & Web App]
```

---

## 2. Layer Responsibilities & Invariants

| Layer | Primary Responsibility | Enforced System Invariants |
| :--- | :--- | :--- |
| **A. Weather Forecast Layer** | Numerical weather prediction downscaled to Panchayat level. | **ML owns numerical weather prediction.** AI must never modify, adjust, or invent numerical weather predictions. |
| **B. Panchayat Context Layer** | Administrative spatial metadata (`panchayats`, `blocks`, `districts` via `HierarchyRepository`). | Spatial hierarchy is the single source of truth for IDs, LGD codes, coordinates, and elevation. |
| **C. Agricultural Risk/Rule Layer** | Evaluates weather variables against deterministic agronomic thresholds. | **Rules own deterministic agricultural risk logic.** Provides baseline recommendations and operational guidance. |
| **D. AI Advisory Layer** | Articulates validated structured context into farmer-friendly natural language. | Receives strictly typed structured inputs; returns strictly typed structured fields (no free-form blobs). |
| **E. Safety Validation Layer** | Automated guardrails inspecting generated content before human inspection. | Must verify numerical consistency, chemical dosage safety, and hallucination absence. |
| **F. Officer Review Layer** | Agricultural extension officers inspect, edit/amend remarks, and approve or reject. | **Officer approval is mandatory.** No advisory can ever reach farmers without explicit approval. |
| **G. Farmer Delivery Layer** | Serves approved, localized advisories to farmers via mobile and web. | Sanitized of internal debug metrics, model weights, and raw identifiers. |
| **H. Audit/Traceability Layer** | Maintains immutable end-to-end lineage for every advisory. | Every advisory traces to forecast ID, Panchayat ID, ML model, rule version, validator report, and officer ID. |

---

## 3. Advisory Data Contracts

Defined in `backend.app.schemas.advisory_contracts`:

### 3.1 Panchayat Context (`PanchayatContext`)
- `panchayat_id` (int): Database identifier.
- `panchayat_name` (str): Village name.
- `panchayat_code` (str, optional): Administrative code.
- `lgd_code` (int): Local Government Directory code.
- `block_id` (int, optional) & `block_name` (str): Tehsil/Block context.
- `district_id` (int, optional) & `district_name` (str): District context.
- `latitude` (float, optional) & `longitude` (float, optional): Center coordinates.
- `elevation_m` (float, optional): Elevation in meters.

### 3.2 Forecast Context (`ForecastContext`)
- `forecast_id` (int): Target forecast record ID in `downscaled_forecasts`.
- `forecast_date` (date) & `forecast_issue_date` (date): Date sequence (must satisfy `forecast_date >= forecast_issue_date`).
- `lead_days` (int): Days between issue date and target date.
- `block_forecast_rainfall_mm` (float): Baseline regional NWP rainfall.
- `downscaled_rainfall_mm` (float): Downscaled rainfall for the Panchayat.
- `rainfall_category` (str): IMD intensity classification.
- `model_name` (str) & `model_version` (str): ML model provenance.
- `confidence` (float, optional): Statistical certainty (null if uncalibrated).
- **Currently Unavailable Variables (Optional/Future):**
  - `temperature_c` (None)
  - `humidity_pct` (None)
  - `wind_speed_kmh` (None)
  - `soil_moisture_index` (None)  
  *Note: These fields default to `None` and are not fabricated.*

### 3.3 Agricultural Risk & Baseline Rules
- `AgriculturalRiskItem`: `risk_type`, `severity` (LOW, MODERATE, HIGH, CRITICAL), `triggering_condition`, `supporting_values`, `rule_id`, `rule_version`.
- `DeterministicRecommendationContext`: `recommended_actions` (list of strings), `timing_window`, `operational_guidance` (e.g. `{"spraying": "POSTPONE", "tillage": "PERMITTED", "drainage": "NORMAL"}`).

---

## 4. AI Advisory Input / Output Contracts

### 4.1 Input Contract (`AIAdvisoryInputContract`)
Passed to the future AI generator:
- `panchayat_context`: Validated `PanchayatContext`.
- `forecast_context`: Validated `ForecastContext`.
- `risks`: Evaluated `List[AgriculturalRiskItem]`.
- `deterministic_recommendations`: Baseline `DeterministicRecommendationContext`.
- `target_language`: Canonical language code (`en`, `mr`, `hi`).
- `advisory_constraints`: Safety boundaries (no dosage prescribing, no weather altering).

### 4.2 Output Contract (`AIAdvisoryOutputContract`)
Structured payload required from the future AI generator:
- `summary` (str, 10-500 chars): High-level headline.
- `what_is_happening` (str, 10-1000 chars): Tier 1 meteorological description.
- `why_it_matters` (str, 10-1000 chars): Tier 2 agronomic impact on crops/soil.
- `recommended_actions` (List[str], >= 1 item): Tier 3 actionable operational steps.
- `timing` (str): Timeframe and validity period.
- `severity` (`AdvisorySeverityEnum`): Risk urgency.
- `warnings` (List[str]): Threshold caution alerts.
- `supporting_forecast_reference` (Dict[str, Any]): Grounding reference validating input forecast link.

---

## 5. Advisory Status Lifecycle

State machine implemented in `src.advisory.lifecycle`:

```mermaid
stateDiagram-v2
    [*] --> DRAFT : Forecast Created
    DRAFT --> GENERATED : AI Generation (AI_SERVICE)
    DRAFT --> NEEDS_REVIEW : Deterministic Rules (RULE_ENGINE)
    GENERATED --> VALIDATED : Safety Checks Pass (SAFETY_VALIDATOR)
    GENERATED --> FAILED_VALIDATION : Safety Checks Fail (SAFETY_VALIDATOR)
    FAILED_VALIDATION --> NEEDS_REVIEW : Fallback to Deterministic (FALLBACK_SERVICE)
    FAILED_VALIDATION --> REJECTED : Discarded Draft
    VALIDATED --> NEEDS_REVIEW : Queued for Inspection
    NEEDS_REVIEW --> APPROVED : Extension Officer Approves (EXTENSION_OFFICER)
    NEEDS_REVIEW --> REJECTED : Extension Officer Rejects (EXTENSION_OFFICER)
    APPROVED --> PUBLISHED : Release to Farmers (PUBLICATION_SERVICE)
    PUBLISHED --> [*]
    REJECTED --> [*]
```

### Transition Invariants
- `GENERATED -> PUBLISHED` is **FORBIDDEN** (prevents unreviewed AI release).
- `DRAFT -> PUBLISHED` is **FORBIDDEN**.
- `REJECTED -> APPROVED` is **FORBIDDEN** (requires generating a new draft).
- `APPROVED -> DRAFT` is **FORBIDDEN** (approved advisories are immutable).

---

## 6. Safety Boundaries & Guardrails

Implemented in `src.advisory.safety_rules`:

1. **Weather Numerical Consistency:** Rainfall figures cited in text must match input downscaled rainfall within 0.5 mm tolerance. AI is prohibited from inventing rainfall numbers.
2. **Chemical Dosage Safety:** Regular expressions block specific chemical dosage formulas (`X ml per acre`, `mix X gm`). AI cannot prescribe chemical recipes or brand dosages.
3. **Medical & Emergency Safeguard:** Prohibits unauthorized human medical claims or unsupported disaster panics (`tsunami`, `emergency evacuation immediately`).
4. **Content Completeness:** Enforces presence of all 3 tiers (`what_is_happening`, `why_it_matters`, `recommended_actions`).
5. **Fallback Principle:** If AI generation fails, times out, or fails automated safety validation, the system falls back to the deterministic agronomic rule output. The advisory source is recorded as `DETERMINISTIC_FALLBACK` and advanced to `NEEDS_REVIEW`.

---

## 7. Traceability Requirements

Implemented in `AdvisoryTraceabilityContract`:
- **Spatial Link:** `panchayat_id`.
- **Forecast Link:** `forecast_id`, `forecast_date`, `forecast_issue_date`, `source_forecast_reference`.
- **Downscaling Provenance:** `downscaled_rainfall_mm`, `ml_model_name`, `ml_model_version`.
- **Agronomic Provenance:** `rule_version`, `advisory_source` (DETERMINISTIC_RULE, AI_AUGMENTED, DETERMINISTIC_FALLBACK).
- **AI Provenance:** `ai_provider`, `ai_model`, `ai_prompt_version`.
- **Safety Audit:** Full `SafetyValidationReport` snapshot with checked rules and violation logs.
- **Human Oversight:** `officer_id`, `officer_action`, `officer_comment`, `action_timestamp`.
- **Publication Audit:** `publication_timestamp`, `approved_content_hash`.

---

## 8. Deterministic Agricultural Risk & Recommendation Rule Engine (Phase 5.2)

Implemented in `src.advisory.rule_engine` (`DeterministicRuleEngine`):

### 8.1 Rule Categories Implemented
1. `EXTREME_WEATHER`: Critical hazard management for extreme inundation.
2. `DRAINAGE`: Soil saturation and furrow discharge protocols.
3. `FIELD_OPERATIONS`: Tillage window and soil compaction prevention.
4. `FERTILIZER`: Runoff and nitrogen leaching safeguards.
5. `HARVEST`: Post-harvest produce shelter advisories.
6. `SPRAYING`: Foliar chemical wash-off precautions.
7. `IRRIGATION`: Natural precipitation recharge suspension and dry weather irrigation scheduling.
8. `TEMPERATURE_STRESS`: Thermal crop stress (conditional on temperature availability).

### 8.2 Rule Catalog & Threshold Provenance

| Rule ID | Category | Parameter | Condition | Provenance & Source | Status | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AGRO_RULE_EXTREME_INUNDATION_V1` | `EXTREME_WEATHER` | `downscaled_rainfall_mm` | `> 115.5 mm` | IMD Very Heavy Rainfall standard (>115.5 mm) | Authoritative | 1 |
| `AGRO_RULE_HEAVY_RAIN_DRAINAGE_V1` | `DRAINAGE` | `downscaled_rainfall_mm` | `> 64.4 mm` | IMD Heavy Rainfall (>64.4 mm) / ICAR Drainage Guidelines | Authoritative | 2 |
| `AGRO_RULE_TILLAGE_RESTRICTION_V1` | `FIELD_OPERATIONS` | `downscaled_rainfall_mm` | `> 15.5 mm` | ICAR Soil Management / Tilth Preservation (>15.5 mm) | Authoritative | 4 |
| `AGRO_RULE_FERTILIZER_LEACHING_V1` | `FERTILIZER` | `downscaled_rainfall_mm` | `> 15.5 mm` | ICAR Nutrient Best Management Practices (>15.5 mm) | Authoritative | 4 |
| `AGRO_RULE_HARVEST_SHELTER_V1` | `HARVEST` | `downscaled_rainfall_mm` | `> 15.5 mm` | ICAR Post-Harvest Protection Guidelines (>15.5 mm) | Authoritative | 3 |
| `AGRO_RULE_SPRAY_WASHOFF_V1` | `SPRAYING` | `downscaled_rainfall_mm` | `> 2.5 mm` | ICAR Plant Protection (wash-off threshold >2.5 mm) | Authoritative | 5 |
| `AGRO_RULE_IRRIGATION_SUSPENSION_V1`| `IRRIGATION` | `downscaled_rainfall_mm` | `> 2.5 mm` | ICAR Water Management / Daily Evapotranspiration | Authoritative | 6 |
| `AGRO_RULE_VERY_LIGHT_RAIN_ROUTINE_V1`| `FIELD_OPERATIONS`| `downscaled_rainfall_mm` | `0.0 < rf <= 2.5`| IMD Very Light Rainfall Classification (0.1–2.5 mm) | Authoritative | 8 |
| `AGRO_RULE_DRY_WEATHER_IRRIGATION_V1` | `IRRIGATION` | `downscaled_rainfall_mm` | `== 0.0 mm` | IMD No Significant Rainfall Classification (0.0 mm) | Authoritative | 9 |
| `AGRO_RULE_HEAT_STRESS_PROTOTYPE_V1` | `TEMPERATURE_STRESS`| `temperature_c` | `> 38.0 °C` | ICAR Thermal Stress Guidelines (>38°C flower abortion)| Prototype (Needs validation) | 3 |

### 8.3 Input Variables & Availability
- **Primary / Active:** `downscaled_rainfall_mm` (downscaled by Phase 2 ML), `block_forecast_rainfall_mm`, `lead_days`.
- **Optional / Future:** `temperature_c`, `humidity_pct`, `wind_speed_kmh`, `soil_moisture_index`. Default to `None` in current pipeline.

### 8.4 Missing Data & Edge Case Safety
- **Missing Rainfall:** Never assumed to be `0.0 mm`. Rainfall-dependent rules do not trigger. Evaluation trace records `skipped=True`. Operational guidance defaults to `"UNKNOWN"`.
- **Missing Temperature:** Temperature rules safely skip with documented reason.
- **Invalid Numerics:** Rejects `NaN`, `Inf`, and negative rainfall values without throwing uncaught exceptions.
- **Missing Forecast Date:** Timing-dependent recommendations are marked unavailable (`timing_window = "Timing unavailable (missing forecast date)"`).
- **Missing Panchayat Context:** Structured validation error returned in `validation_errors` (or raises `RuleEngineValidationError` if strict mode enabled).

### 8.5 Output Structure & Deterministic Ordering
`RuleEngineEvaluationResult`:
- `risks`: List of `AgriculturalRiskItem` sorted deterministically by severity (`CRITICAL > HIGH > MODERATE > LOW`) then `rule_id`.
- `recommendation_context`: `DeterministicRecommendationContext` containing:
  - `recommended_actions`: Consolidated, deduplicated action strings ordered by rule priority.
  - `timing_window`: Timing window from highest-priority triggered rule.
  - `operational_guidance`: Dict mapping operation keys (`spraying`, `tillage`, `drainage`, `irrigation`) to guidance tokens, resolved deterministically by priority.
- `triggered_rules`: Triggered rules sorted by priority (`1 = critical`) then `rule_id`.
- `evaluation_trace`: Complete audit trail of all evaluated rules (triggered, skipped, actual values, thresholds).
- `validation_errors`: Structured non-blocking warnings or validation issues.
- `rule_version`: Immutable version string (`v1.0.0`).

### 8.6 Known Limitations
- Current ML forecasts downscaled rainfall only; thermal and moisture index rules remain conditional prototypes until multi-variable sensors/models are added.
- General agronomic rules apply at the Panchayat level; crop-specific phenological thresholds require farm-level crop profile inputs.

---

## 9. Canonical Advisory Context & Risk Generation (Phase 5.3)

Implemented in `src.advisory.context_builder` (`AdvisoryContextService`) and `backend.app.schemas.advisory_contracts` (`AdvisoryContext`):

### 9.1 AdvisoryContext Canonical Contract
The internal pipeline envelope uniting authoritative spatial metadata, numerical forecasts, and deterministic risk outputs:
```text
AdvisoryContext
├── panchayat: PanchayatContext
├── forecast: ForecastContext
├── risks: List[AgriculturalRiskItem]
├── recommendations: DeterministicRecommendationContext
├── traceability: AdvisoryTraceabilityContract
└── validation_errors: List[str]
```

### 9.2 Data Sources & Performance Optimization
- **Spatial Metadata:** Queried via `HierarchyRepository.get_panchayat_by_id(eager_load_parents=True)` in a single indexed join across `panchayats`, `blocks`, and `districts`. Avoids multi-query round-trips.
- **Forecast Ingestion:** Queried directly from `downscaled_forecasts` table preserving original Phase 2 model names, versions, issue dates, and downscaled rainfall.

### 9.3 Validation Rules & Freshness Policy
- **Panchayat Existence & Parentage:** Confirms valid database identifier; optional `expected_block_id` and `expected_district_id` prevent cross-jurisdiction routing errors.
- **Forecast Ownership:** Enforces `forecast.panchayat_id == panchayat_id`. Mismatches raise `ForecastPanchayatMismatchError`.
- **Temporal Integrity:** Enforces `forecast_issue_date <= forecast_date`. Issue dates later than forecast dates raise `InvalidForecastDataError`.
- **Physical Numerical Range:** Validates that `downscaled_rainfall_mm` and `block_forecast_rainfall_mm` are finite, non-negative numbers. Rejects `NaN`, `Inf`, and negative values.
- **Deterministic Multi-Record Resolution:** When multiple forecast records exist for the same Panchayat and target date, the engine resolves deterministically via:
  `ORDER BY forecast_issue_date DESC, created_at DESC, id DESC`.

### 9.4 Error Handling Taxonomy
Structured exceptions subclassing `AdvisoryContextError`:
- `PanchayatNotFoundError`: HTTP 404
- `ForecastNotFoundError`: HTTP 404
- `HierarchyMismatchError`: HTTP 422
- `ForecastPanchayatMismatchError`: HTTP 422
- `InvalidForecastDataError`: HTTP 422
- `RuleEvaluationError`: HTTP 422

### 9.5 Internal API Integration
Exposed as `GET /api/v1/advisory/context/{panchayat_id}`:
- Query parameters: `forecast_id` (optional), `forecast_date` (optional).
- Returns the complete strongly-typed `AdvisoryContext`.
- Operates strictly as a read-only context preparation layer (does not call LLMs, publish advisories, or alter forecasts).
