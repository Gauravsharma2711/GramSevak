# Phase 4.3: React Forecast & Panchayat Experience Specification

## 1. Overview
This document specifies the refined officer experience from **District → Block → Panchayat → Forecast** implemented in Phase 4.3. Grounded in the Universal Farmer Product Design System and Phase 4.1 UX architecture, this redesign resolves previous information duplication, introduces a standardized IMD rainfall intensity visualization, adds clean date timeline navigation, and keeps technical model specifications quiet.

---

## 2. Panchayat Context & Administrative Hierarchy
1. **Clear Administrative Breadcrumb**:
   - Replaced heavy duplicate location headers with an immediate, lightweight breadcrumb:
     `{district_name} › {block_name} Block › {panchayat_name} GP`
   - Context is continuously visible at the top of the detail screen without excessive viewport consumption.
2. **Compact Profile Summary**:
   - Consolidated technical metadata into a single calm chip strip:
     - Bhuvan DEM Elevation (`{elevation_m} m`)
     - Decimal Coordinates (`{latitude}°N, {longitude}°E`)
     - Official LGD Code (`{lgd_code}`)
   - Removed internal database IDs and unneeded technical identifiers from primary views.

---

## 3. Forecast Presentation & Visualization
1. **Elimination of Duplicated Numbers**:
   - Previously, block baseline, downscaled rainfall, and delta were rendered across 3 separate cards (workflow stepper, comparison grid, and metrics card).
   - Unified into a single, high-contrast, calm **Microclimate Rainfall Forecast** card.
2. **IMD Rainfall Intensity Visual Scale**:
   - Implemented `RainfallIntensityGauge`: an accessible, segmented horizontal visual scale mapping exact rainfall millimeters to official IMD agricultural criteria:
     - Nil / Dry: `< 0.1 mm`
     - Very Light Rain: `0.1 – 2.4 mm`
     - Light Rain: `2.5 – 15.5 mm`
     - Moderate Rain: `15.6 – 64.4 mm`
     - Heavy Rain: `64.5 – 115.5 mm`
     - Very Heavy Rain: `> 115.5 mm`
   - Gives officers instantaneous situational awareness regarding spray schedules and runoff risk.
3. **Ground Truth Telemetry**:
   - Clean status tile displaying AWS/ARG ground observation when verified, or clear pending note when post-event validation is awaiting observation.

---

## 4. Forecast Timeline & Date Navigation
- Compact date tabs allow officers to inspect:
  - **Target Forecast** (e.g. `2026-09-09` • Validated)
  - **Day +2 Outlook** (`2026-09-10`)
  - **Historical Baseline** (`2026-09-08`)
- Active date pill clearly communicates the active temporal scope without triggering full-page reload.

---

## 5. Agricultural Advisory & Action Bar
- **Structured Recommendation Presentation**:
  - Title and agronomic guidance prominently styled with earth-toned typography.
  - Clear meteorological trigger badge displaying condition and severity level.
- **Action Priority**:
  - Single primary green button: `Approve & Publish`
  - Secondary danger button: `Reject`
  - Approved state renders official verified seal (`DR-S-PATIL-AO`) with active mobile delivery indicator.

---

## 6. Quiet Supporting Information
- Technical ML model specifications (Random Forest/XGBoost, feature vectors, DOY math) are collapsed by default into a subtle secondary section with an accessible disclosure toggle (`View Specs`).
- Single secondary CTA: `Re-run Inference`.

---

## 7. Responsive & Accessible Behavior
- **Mobile (< 768px)**:
  - Stacked vertical cards with minimum 48px touch targets.
  - Rainfall gauge automatically scales with abbreviated labels.
  - Interactive Panchayat names in `PanchayatForecastSection` table and mobile cards allow direct navigation.
- **Accessibility**:
  - Semantic HTML5 landmarks (`<section>`, `<nav>`, `<article>`).
  - Screen reader progressbar roles on the rainfall scale (`role="progressbar"` with `aria-valuenow`).
  - Keyboard accessible tablist and buttons with visible focus rings.

---

## 8. Validation Summary
- `npx tsc --noEmit`: 0 errors
- `npx vitest run`: 3 test suites, 20/20 passed (100%)
- `npm run build`: Production bundle compiled cleanly in 4.58s
- `flutter analyze`: 0 issues found in `farmer_app`
- Zero backend, ML, or database contract modifications.
