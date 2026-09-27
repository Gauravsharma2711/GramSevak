# GramSevak ML Data Contract & Training Readiness Audit (Phase 2.1)

## 1. Executive Summary & Objective

### 1.1 Problem Statement (SIH 26074)
The GramSevak machine learning objective is to downscale coarse, regional numerical weather prediction (NWP) rainfall forecasts from the Block level (~15–25 km grid) down to hyper-local Gram Panchayat level (~2–5 km centroid), conditioning on local topography, spatial coordinates, station distance, and valid historical antecedent rainfall context:

$$\text{Block Forecast} + \text{Panchayat Spatial Context} + \text{Valid Historical Antecedents} \longrightarrow \mathcal{M}_{\text{ML}} \longrightarrow \widehat{\text{Panchayat Rainfall (mm)}}$$

### 1.2 Phase 2.1 Scope & Constraints
Phase 2.1 is strictly an **Audit and Readiness Phase**:
- It evaluates the validated Phase 1 Canonical Parquet datasets (`canonical_nashik.parquet` and `canonical_pune.parquet`).
- It establishes a non-negotiable **ML Data Contract** that prevents data leakage, defines training eligibility, formulates the non-ML block forecast baseline, and dictates valid temporal evaluation splits.
- **Strict Boundary**: No ML models (Random Forest, XGBoost, LightGBM, neural nets) are trained, tuned, or deployed in Phase 2.1. No synthetic data is fabricated.

---

## 2. Unit of Observation

A single supervised learning observation corresponds to **one specific Gram Panchayat on one specific forecast issuance instance targeting a specific 24-hour observation date**:

$$\mathbf{u} = \big( \text{panchayat\_id}, \text{forecast\_issue\_date}, \text{date} \big)$$

### 2.1 Compound Entity Key
- **`panchayat_id`** (Integer): Unique Ministry of Panchayati Raj / Normalized Gram Panchayat identifier.
- **`forecast_issue_date`** (ISO 8601 `YYYY-MM-DD`): The date on which the numerical model run was issued by IMD/NCMRWF.
- **`date`** (ISO 8601 `YYYY-MM-DD`): The validity target date representing the 24-hour accumulation window.
- **`lead_days`** (Integer $\ge 0$): The lead horizon defined as $\text{date} - \text{forecast\_issue\_date}$.

Each unit of observation represents an inference decision: *"Given what is known on `forecast_issue_date` for `panchayat_id`, what will be the 24-hour ground-truth precipitation on `date`?"*

---

## 3. Target Variable & Semantics

### 3.1 Target Definition
- **Target Column**: `actual_rainfall_mm`
- **Unit**: Millimeters of liquid precipitation ($1.0\text{ mm} = 1.0\text{ L/m}^2$).
- **Data Type**: Float64 ($\ge 0.0$).
- **Physical Meaning**: Ground-truth 24-hour accumulated precipitation recorded by reference Automatic Weather Stations (AWS) or Automatic Rain Gauges (ARG) mapped to the Panchayat centroid.
- **Temporal Window**: Standard IMD 24-hour accumulation window ending on the target date.
- **Missing Value Handling**: In Phase 1 canonical Parquet datasets, `actual_rainfall_mm` has 0 missing values (100% complete). Any future unobserved row must be marked ineligible for training.
- **Zero Value Meaning**: Exactly $0.0\text{ mm}$ denotes a verified dry day (no measurable rainfall). Zeroes are physically valid ground truth, not missing values.

### 3.2 Target Distribution Across Districts

| Metric | Nashik Snapshot ($N=1,388$) | Pune Time-Series ($N=187,320$) | Combined Foundation ($N=188,708$) |
| :--- | :---: | :---: | :---: |
| **Valid Observations** | 1,388 (100%) | 187,320 (100%) | 188,708 (100%) |
| **Missing Values** | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| **Dry Days ($0.0$ mm)** | 0 (0.0%) | 68,238 (36.43%) | 68,238 (36.16%) |
| **Rainy Days ($>0.0$ mm)** | 1,388 (100.0%) | 119,082 (63.57%) | 120,470 (63.84%) |
| **Mean Rainfall** | 9.57 mm | 6.18 mm | 6.21 mm |
| **Median (p50)** | 8.80 mm | 2.10 mm | 2.10 mm |
| **Standard Deviation** | 6.30 mm | 11.51 mm | 11.49 mm |
| **Minimum** | 0.40 mm | 0.00 mm | 0.00 mm |
| **25th Percentile (p25)** | 5.00 mm | 0.00 mm | 0.00 mm |
| **75th Percentile (p75)** | 13.00 mm | 7.40 mm | 7.40 mm |
| **90th Percentile (p90)** | 17.60 mm | 18.00 mm | 18.00 mm |
| **95th Percentile (p95)** | 21.00 mm | 29.50 mm | 29.50 mm |
| **99th Percentile (p99)** | 31.80 mm | 62.40 mm | 62.10 mm |
| **Maximum** | 52.20 mm | 120.30 mm | 120.30 mm |

### 3.3 IMD Rainfall Intensity Breakdown (Pune Dataset, $N=187,320$)
- **No Rain (Dry)** ($0.0$ mm): 68,238 rows (**36.43%**)
- **Very Light / Trace** ($0.01 - 2.4$ mm): 31,437 rows (**16.78%**)
- **Light Rain** ($2.41 - 15.5$ mm): 62,561 rows (**33.40%**)
- **Moderate Rain** ($15.51 - 64.4$ mm): 23,371 rows (**12.48%**)
- **Heavy Rain** ($64.41 - 115.5$ mm): 1,691 rows (**0.90%**)
- **Very Heavy Rain** ($115.51 - 204.4$ mm): 22 rows (**0.01%**)
- **Extremely Heavy Rain** ($>204.4$ mm): 0 rows (**0.00%**)

---

## 4. Prediction-Time Information Boundary

For every feature $X$, we enforce the strict causality principle: **Could this value be legitimately observed by the downscaling engine at the exact timestamp when the forecast is issued?**

```
PAST HISTORY (t - 1, t - 2, ...)  │ FORECAST ISSUANCE (t - lead)  │ TARGET DAY (t)
──────────────────────────────────┼───────────────────────────────┼─────────────────────────
• Antecedent rainfall lags        │ • Regional block NWP forecast │ • actual_rainfall_mm [TARGET]
  (lag_actual_t1, lag_actual_t3)  │ • Static coordinates (lat/lon)│ • Future station observations
• Rolling historical statistics   │ • Terrain elevation (m)       │ • Future aggregations
                                  │ • Station distance (km)       │ • Target encodings
                                  │ • Lead horizon (lead_days)    │
                                  │ • Calendar seasonality        │
──────────────────────────────────┴───────────────────────────────┴─────────────────────────
             ALLOWED FEATURES                  ALLOWED FEATURES          FORBIDDEN (LEAKAGE)
```

### 4.1 Boundary Classification
- **Category A — Available at Forecast Issuance Time**: Macro NWP forecast (`block_forecast_rainfall_mm`), static terrain/spatial features (`panchayat_latitude`, `panchayat_longitude`, `elevation_m`, `station_distance_km`), temporal parameters (`lead_days`, `month`, `day_of_year`).
- **Category B — Available from Past History Only**: Antecedent rainfall observations strictly prior to `forecast_issue_date` ($t-1, t-2, t-3, t-7$, backward rolling sums). Allowed only where continuous historical time series exist (Pune).
- **Category C — Available Only After Target Date (FORBIDDEN)**: Ground-truth target `actual_rainfall_mm`, same-day station observations, future rolling averages, global target encodings.
- **Category D — Unknown / ETL Artifacts (FORBIDDEN)**: `source_row_id`, `source_file`, `source_dataset`.

---

## 5. Explicit Data Leakage Audit

To prevent fatal data leakage that invalidates machine learning models, the following 6 leakage vectors are strictly audited and prohibited:

| Leakage Vector | Description | Severity | Enforcement Mechanism |
| :--- | :--- | :---: | :--- |
| **1. Target Self-Inclusion** | Including `actual_rainfall_mm` as an input feature in matrix $X$. | **FATAL** | Column `actual_rainfall_mm` is segregated into target vector $y$ only. Dropped from feature set prior to model ingestion. |
| **2. Temporal Random Splitting** | Using standard `train_test_split(shuffle=True)` or random $k$-fold cross-validation on time-series records. | **CRITICAL** | Shuffled splits cause future days to leak into past training folds. Must enforce strict **Chronological Forward Splits** (`TimeSeriesSplit` or fixed temporal cutoffs). |
| **3. Same-Day Station Observations** | Using AWS station rainfall from day $t$ to predict Panchayat rainfall on day $t$. | **CRITICAL** | Real-time ground rainfall is not available at forecast issuance. Station features are restricted to static geometry (`station_distance_km`, `station_lat/lon`). |
| **4. Forward-Looking Rolling Windows** | Computing centered or forward rolling rainfall averages (e.g. $t-1$ to $t+1$). | **CRITICAL** | Rolling windows must be strictly backward-looking (e.g. $[t-7, t-1]$) with a closed right boundary before `forecast_issue_date`. |
| **5. Global Target Encoding** | Replacing high-cardinality `panchayat_id` or `block_name` with the target mean computed over the entire dataset. | **HIGH** | Global target encoding leaks validation fold targets into training. Target encoding is forbidden in Phase 2; spatial coordinates (`lat`, `lon`, `elevation`) must be used instead. |
| **6. Entity ID Memorization** | Feeding raw integer `panchayat_id` into tree-based models (RF/XGBoost). | **HIGH** | Models split on arbitrary integer thresholds and memorize specific Panchayats, destroying geographic generalization. Raw entity IDs are excluded from features. |

---

## 6. Candidate Feature Inventory

| Field Name | Data Type | Information Category | Decision | Rationale |
| :--- | :---: | :---: | :---: | :--- |
| `block_forecast_rainfall_mm` | Float64 | Category A | **ALLOWED (Core)** | Primary numerical weather signal from regional NWP models. |
| `panchayat_latitude` | Float64 | Category A | **ALLOWED (Spatial)** | Encodes North-South geographic gradient across Maharashtra. |
| `panchayat_longitude` | Float64 | Category A | **ALLOWED (Spatial)** | Encodes Western Ghats orographic gradient and rain shadow. |
| `elevation_m` | Float64 | Category A | **ALLOWED (Topographic)** | Physical altitude driving localized precipitation enhancement. |
| `station_distance_km` | Float64 | Category A | **ALLOWED (Context)** | Haversine distance from Panchayat centroid to reference AWS. |
| `lead_days` | Int64 | Category A | **ALLOWED (Horizon)** | Forecast lead horizon; accounts for skill degradation over time. |
| `month`, `day_of_year` | Int64 / Float | Category A | **ALLOWED (Temporal)** | Encoded cyclically ($\sin/\cos$) to capture monsoon phases. |
| `lag_actual_t1_mm` | Float64 | Category B | **ALLOWED (Pune Only)** | Valid 24h prior rainfall ($t-1$); requires 1-day warm-up window. |
| `lag_actual_t3_mm` | Float64 | Category B | **ALLOWED (Pune Only)** | 3-day backward cumulative precipitation persistence indicator. |
| `actual_rainfall_mm` | Float64 | Category C | **FORBIDDEN AS FEATURE** | **Ground-truth target variable ($y$) only.** |
| `panchayat_id` / `lgd_code` | Int64 | Category A | **FORBIDDEN IN MODEL** | High-cardinality identifier prone to memorization/overfitting. |
| `source_row_id` / `source_file` | Int/Str | Category D | **FORBIDDEN** | ETL pipeline artifact with zero physical meteorological relevance. |

---

## 7. Historical Feature Feasibility & Temporal Coverage

### 7.1 Historical Feasibility Analysis
- **Pune Dataset**:
  - Contains **140 consecutive daily slices** ($2026-04-13$ to $2026-09-23$) for all 1,338 Panchayats ($1,338 \times 140 = 187,320$ records).
  - Every Panchayat has 140 continuous daily observations without gaps ($\Delta t = 1$ day).
  - Lags $t-1, t-3, t-7$ are **fully feasible** using a 7-day initial warm-up window.
  - Slices on or after day 8 ($2026-04-20$ onwards) have 100% complete antecedent histories.
- **Nashik Dataset**:
  - Contains **1,388 Panchayats**, but each Panchayat has **exactly 1 observation record** ($1,388$ total rows across 9 snapshot dates).
  - Maximum records per Panchayat = 1; minimum = 1.
  - **Lag features ($t-1, t-3, t-7$) are NOT FEASIBLE on Nashik** due to absence of antecedent historical sequence.

### 7.2 Temporal Evaluation Split Rules
For time-series modeling in Phase 2.2:
1. **Forbidden**: Random train/test shuffling.
2. **Permitted Split 1 — Temporal Holdout**:
   - **Training Set**: April 13, 2026 to July 31, 2026 (110 days, 147,180 rows, covers pre-monsoon and peak monsoon onset).
   - **Validation/Test Set**: August 1, 2026 to September 23, 2026 (30 days, 40,140 rows, covers late monsoon withdrawal).
3. **Permitted Split 2 — Rolling Expanding Window Cross-Validation (`TimeSeriesSplit`)**:
   - Minimum fold train size: 45 days; test size: 15 days; strictly forward-marching without overlap.

---

## 8. Panchayat Coverage & Training Eligibility Contract

### 8.1 Panchayat Coverage Classification
- **Tier 1: Sufficient History ($\ge 60$ days)**: 1,338 Panchayats (100% of Pune; eligible for temporal ML & lag features).
- **Tier 2: Single Snapshot ($1$ day)**: 1,388 Panchayats (100% of Nashik; eligible for spatial snapshot downscaling, ineligible for lag features).
- **Tier 3: Moderate (10–59 days) / Sparse (2–9 days) / Unusable ($0$ days)**: 0 Panchayats across both datasets.

### 8.2 Row-Level Training Eligibility Rules
A row in the canonical weather database is declared **Eligible for Training** if and only if all 5 conditions hold:
1. `actual_rainfall_mm` is not null and $0.0 \le \text{actual\_rainfall\_mm} \le 1000.0$.
2. `block_forecast_rainfall_mm` is not null and $0.0 \le \text{block\_forecast\_rainfall\_mm} \le 500.0$.
3. `panchayat_latitude` and `panchayat_longitude` are valid non-null coordinates within Maharashtra bounding box ($15.0^{\circ} - 22.0^{\circ}\text{ N}, 72.0^{\circ} - 81.0^{\circ}\text{ E}$).
4. `forecast_issue_date` and `date` are valid non-null ISO dates.
5. $\text{lead\_days} = \text{date} - \text{forecast\_issue\_date} \ge 0$.

### 8.3 Eligibility Audit Results
- **Nashik Parquet**: 1,388 / 1,388 rows eligible (**100.0%**).
- **Pune Parquet**: 187,320 / 187,320 rows eligible (**100.0%**).
- **System Total**: 188,708 / 188,708 rows eligible (**100.0%**). Rejection rate: 0.0%.

---

## 9. Block Forecast Baseline (Benchmark Definition)

Before any machine learning model is trained, we establish the non-ML **Raw Block Forecast Baseline**:
$$\widehat{y}_{\text{baseline}} = \text{block\_forecast\_rainfall\_mm}$$
The raw regional forecast from IMD/NCMRWF is applied directly as the Panchayat-level prediction. Any subsequent ML model in Phase 2.2 must demonstrate statistically significant improvement over these baseline metrics.

### 9.1 Baseline Metrics Across Slices

| District | Evaluation Slice | Row Count | MAE (mm) | RMSE (mm) | Mean Bias (mm) | Pearson $r$ |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Nashik** | Overall (All Records) | 1,388 | **4.3651** | **5.5919** | **+2.2980** | **0.8777** |
| **Pune** | Overall (All Records) | 187,320 | **6.1879** | **13.7786** | **-0.5079** | **0.3708** |
| **Pune** | Dry Days (`actual == 0.0` mm) | 68,238 | **2.4353** | **4.0183** | **+2.4353** | 0.0000 |
| **Pune** | Rainy Days (`actual > 0.0` mm) | 119,082 | **8.3382** | **17.0114** | **-2.1944** | 0.2983 |
| **Pune** | Moderate+ Rain (`actual >= 15.5` mm) | 25,084 | **22.5694** | **31.3320** | **-22.1812** | 0.0520 |
| **Pune** | Heavy Rain (`actual >= 35.5` mm) | 5,352 | **63.2750** | **72.8210** | **-63.2750** | -0.2342 |
| **Pune** | Very Heavy Rain (`actual >= 64.5` mm) | 1,713 | **98.2435** | **106.6321** | **-98.2435** | -0.1985 |

### 9.2 Critical Baseline Limitations & Failure Modes
1. **Severe Under-Prediction on Heavy Precipitation**: In Pune, the maximum block forecast issued is $12.4\text{ mm}$, whereas actual observed rainfall reaches $120.3\text{ mm}$. On heavy rainfall events ($\ge 35.5\text{ mm}$), the baseline suffers a staggering **MAE of 63.28 mm** and negative bias of $-63.28\text{ mm}$. Macro NWP models smooth out convective extremes over $25\text{ km}$ grid cells.
2. **False Alarms on Dry Days**: On zero-rainfall days in Pune ($n=68,238$), the block forecast predicts non-zero rain on average $+2.44\text{ mm}$ (positive bias), resulting in false agricultural spray warnings.
3. **Zero Spatial Granularity**: All Panchayats within a block receive identical predictions regardless of whether they lie at $550\text{ m}$ elevation on the plains or $1,200\text{ m}$ on the Ghats ridgeline.

---

## 10. Nashik vs. Pune Comparative Analysis & Pooling Strategy

| Dimension | Nashik Dataset | Pune Dataset | Reconciliation & Strategy |
| :--- | :--- | :--- | :--- |
| **Dataset Structure** | Spatial Snapshot (1 row / Panchayat) | Time-Series (140 rows / Panchayat) | **Cannot be pooled directly into one time-series model.** |
| **Total Rows** | 1,388 | 187,320 | Pune represents 99.27% of volume. |
| **Panchayats** | 1,388 | 1,338 | Spatially disjoint administrative entities. |
| **Lead Horizon** | `lead_days = 0` (nowcast / same-day) | `lead_days = 1` (1-day advance forecast) | Horizon mismatch requires explicit handling. |
| **Historical Lags** | Impossible ($t-1$ not available) | Supported ($t-1, t-3, t-7$ available) | Temporal features exclusive to Pune. |
| **Recommended ML Role** | **Out-of-District Spatial Generalization Holdout** | **Primary Model Training & Temporal Validation** | Model trained on Pune can be evaluated on Nashik static features to test geographic transferability. |

---

## 11. Generalization Risks & Proposed Mitigations

1. **Spatial Overfitting / Identity Memorization**:
   - *Risk*: A gradient boosting model may memorize specific `panchayat_id` values.
   - *Mitigation*: Strictly omit `panchayat_id` and `block_name` from feature matrix $X$. Rely solely on continuous geographic coordinates (`lat`, `lon`), `elevation_m`, and `station_distance_km`.
2. **Temporal Autocorrelation / Future Leakage**:
   - *Risk*: Random train-test splitting produces unrealistically optimistic test scores.
   - *Mitigation*: Strictly enforce forward chronological splitting (Train April–July, Test August–September).
3. **Severe Class Imbalance / Extreme Event Suppression**:
   - *Risk*: Models minimizing standard MSE will predict the safe mean (~6 mm) and completely miss heavy convective rainfall ($>35.5$ mm).
   - *Mitigation*: In Phase 2.2, consider two-stage modeling (classification: rain vs no rain, regression: rainfall amount) or asymmetric loss functions (Tweedie loss / Quantile regression).

---

## 12. Dataset Readiness Verdict

$$\mathbf{STATUS: \quad READY \quad WITH \quad WARNINGS}$$

### 12.1 Readiness Verdict Rationale
- **Target Integrity**: $100\%$ verified and non-null in both datasets. Physical units and zero semantics are established.
- **Structural Integrity**: $100\%$ schema compliance; zero duplicate keys; 188,708 eligible rows.
- **Baseline Quantified**: Established across all slices (Overall Pune MAE = 6.19 mm, RMSE = 13.78 mm).
- **Readiness Warnings**:
  1. *Nashik Snapshot Structure*: Nashik has only 1 row per Panchayat and cannot support lag features or temporal splits. It must be treated as a spatial transferability test set.
  2. *Lead Horizon Discrepancy*: Nashik represents `lead_days=0` while Pune represents `lead_days=1`.
  3. *Block Forecast NWP Compression*: Severe NWP under-prediction on heavy precipitation ($\ge 35.5$ mm, bias $-63.28$ mm) requires robust loss function design in Phase 2.2.
- **Phase 2.2 Progression**: Phase 2.2 (Feature Engineering & Temporal Splits) is **APPROVED TO PROCEED**.
