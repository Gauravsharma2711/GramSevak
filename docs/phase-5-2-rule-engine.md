# Phase 5.2: Deterministic Agricultural Risk and Recommendation Rule Engine

## 1. Overview
The **Deterministic Agricultural Risk and Recommendation Rule Engine** is the core deterministic bridge between validated Panchayat-level weather forecast context and agricultural risk assessment. It strictly precedes the future AI Advisory Layer in the GramSevak advisory pipeline:

```text
Panchayat Forecast
       ↓
Weather Context Validation (Phase 5.1)
       ↓
Deterministic Rules Engine (Phase 5.2)
       ↓
Structured Risks + Recommendation Context (Contracts)
       ↓
[Future Phase 5.3: AI Advisory Layer & Translation]
       ↓
Safety Validation & Officer Review
       ↓
Approved Farmer Advisory
```

## 2. Design Principles
1. **Explainability & Auditability**: Every generated risk points directly to a machine-readable rule definition (`rule_id`, `rule_version`, `severity`, `triggering_condition`, `supporting_values`).
2. **Provenance-Backed Thresholds**: No numerical threshold is invented. Every threshold is grounded in documented IMD (India Meteorological Department) rainfall classification standards or ICAR (Indian Council of Agricultural Research) agronomic advisories, or explicitly flagged as a prototype requirement.
3. **Graceful Handling of Optional Variables**: Downscaled rainfall (`downscaled_rainfall_mm`) is the primary validated variable produced by the Phase 2 ML pipeline. Future/secondary variables (`temperature_c`, `humidity_pct`, `wind_speed_kmh`, `soil_moisture_index`) are evaluated only if present; missing variables produce explicit audit traces without errors.
4. **Decoupled from LLM/AI**: The rule engine is 100% deterministic Python logic. It produces structured data contracts (`AgriculturalRiskItem`, `DeterministicRecommendationContext`) consumed downstream by prompt builders or review workflows.

## 3. Threshold Provenance & Agronomic Rationale

| Rule ID | Category | Parameter | Condition | Provenance & Source | Agronomic Rationale | Prototype? |
|---|---|---|---|---|---|---|
| `AGRI_EXTREME_INUNDATION` | Inundation | `downscaled_rainfall_mm` | `>= 115.6 mm` | IMD Classification ("Very Heavy to Extremely Heavy Rainfall") | Risk of standing crop subversion, severe root hypoxia, field embankment breach. | No (IMD Standard) |
| `AGRI_HEAVY_WATERLOG` | Drainage | `downscaled_rainfall_mm` | `>= 64.5 mm` | IMD Classification ("Heavy Rainfall" > 64.4 mm) / ICAR Drainage Guidelines | Soil reaches waterlogging saturation; clear drainage outlets immediately. | No (IMD / ICAR) |
| `AGRI_TILLAGE_DELAY` | Field Operations | `downscaled_rainfall_mm` | `>= 15.6 mm` | ICAR Tilth Guidelines (Topsoil plastic limit saturation > 15.5 mm) | Machinery and bullock plowing in saturated soil causes severe subsoil compaction/smearing. | No (ICAR) |
| `AGRI_LEACHING_RISK` | Fertilization | `downscaled_rainfall_mm` | `>= 15.6 mm` | ICAR Nutrient Management Advisory | Topdressing with urea or nitrogenous fertilizer during rain causes heavy runoff & leaching loss. | No (ICAR) |
| `AGRI_HARVEST_SHELTER` | Harvesting | `downscaled_rainfall_mm` | `>= 15.6 mm` | ICAR Post-Harvest Protocol | Harvested grains/produce exposed in open threshing yards suffer grain germination and mold. | No (ICAR) |
| `AGRI_SPRAY_WASHOFF` | Spraying | `downscaled_rainfall_mm` | `>= 2.5 mm` | ICAR Plant Protection Bulletin (Washoff threshold > 2.5 mm) | Chemical pesticide/fungicide contact sprays wash off, wasting inputs and contaminating runoff. | No (ICAR) |
| `AGRI_IRRIGATION_SUSPEND`| Irrigation | `downscaled_rainfall_mm` | `>= 2.5 mm` | IMD Agromet Advisory Service (AAS) | Active precipitation satisfies evaporative demand; suspend surface and tube-well irrigation. | No (IMD AAS) |
| `AGRI_STANDARD_OPERATIONS`| Field Operations| `downscaled_rainfall_mm` | `<= 2.5 mm` | ICAR Agronomic Practice | Very light precipitation or trace drizzle does not impede interculture, spraying, or weeding. | No (ICAR) |
| `AGRI_DRY_IRRIGATION` | Irrigation | `downscaled_rainfall_mm` | `== 0.0 mm` | IMD No Rain Category / ICAR Water Balance | No precipitation expected; maintain routine irrigation scheduling based on crop stage. | No (ICAR) |
| `AGRI_HEAT_STRESS` | Thermal Stress | `temperature_c` | `>= 38.0 °C` | ICAR Heat Stress Advisory | High temperature accelerates transpirational stress; provides light canopy misting recommendation. | Yes (Needs validation) |

## 4. Rule Definition Schema
Each rule is represented as an immutable `AgriculturalRuleDefinition`:
- `rule_id`: Unique identifier (e.g. `AGRI_SPRAY_WASHOFF`)
- `rule_version`: Semantic rule version (`1.0.0`)
- `rule_name`: Human-readable label
- `category`: `RuleCategory` enum (`RAINFALL_INTENSITY`, `WATERLOGGING`, `IRRIGATION`, `SPRAYING`, `TILLAGE`, `HARVESTING`, `FERTILIZER`, `HEAT_STRESS`)
- `enabled`: Boolean toggle for operational filtering
- `input_variables`: List of variable keys required for evaluation
- `condition_operator`: `ComparisonOperator` (`GT`, `GTE`, `LT`, `LTE`, `EQ`, `RANGE_INCLUSIVE`)
- `threshold_value`: Exact numeric threshold
- `threshold_unit`: Physical unit (`mm`, `deg_C`, etc.)
- `threshold_source`: Formal reference attribution
- `is_prototype`: Boolean indicator for agronomic review
- `severity`: `AdvisorySeverityEnum` (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`)
- `risk_type`: Domain categorization string
- `recommendation`: Concrete actionable advisory text
- `timing`: Operational window (e.g. `Next 24 hours`)
- `explanation`: Auditable explanation of triggering logic
- `priority`: Numeric execution order (lower numbers evaluated first)
- `operational_action_key`: Key in `operational_guidance` map (e.g. `spraying`)
- `operational_action_value`: Guidance value (e.g. `POSTPONE`)

## 5. Verification & Testing
The test suite in `tests/test_rule_engine.py` provides 100% test coverage over:
- Inundation and drainage trigger boundaries (64.5 mm, 115.6 mm).
- Spray postponement and irrigation suspension triggers (2.5 mm threshold).
- Tillage delay, fertilizer leaching prevention, and harvest shelter triggers (15.6 mm threshold).
- Trace drizzle vs. dry weather distinction (0.0 mm vs. 1.2 mm).
- Safe skipping of absent weather variables (`temperature_c`) without crashing.
- Evaluation traces verifying condition results, actual evaluated values, and skip reasons.
