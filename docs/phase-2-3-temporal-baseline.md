# GramSevak Temporal Split, Baselines & Evaluation Framework (Phase 2.3)

## 1. Executive Summary & Objective

In **Phase 2.3**, a leakage-safe temporal evaluation framework and rigorous baseline benchmarks were established for Panchayat-level rainfall downscaling under the [Phase 2.1 ML Data Contract](file:///c:/sih/sih26074-weather-downscaling/docs/phase-2-1-ml-data-contract.md) using the verified feature datasets from [Phase 2.2](file:///c:/sih/sih26074-weather-downscaling/docs/phase-2-2-feature-engineering.md).

The central purpose is to establish the **definitive benchmark that all future machine learning models must beat**:

$$\text{Block Forecast Baseline} \quad \text{and} \quad \text{Simple Linear Baseline} \quad \longleftarrow \quad \text{The Benchmarks to Beat}$$

### Strict Phase 2.3 Boundaries
- **No Advanced Models**: Zero Random Forest, XGBoost, LightGBM, or neural networks were trained or tuned.
- **Strict Chronological Splitting**: No random shuffling (`train_test_split(shuffle=True)` is permanently barred). All splits preserve the forward march of time: $\text{Past} \rightarrow \text{Train}$, $\text{Later} \rightarrow \text{Validation}$, $\text{Future} \rightarrow \text{Locked Test}$.
- **Immutable Test Period**: The test set (September 2026) is sealed and locked to simulate real-world future operational deployment.

---

## 2. Chronological Split Strategy & Exact Dates

### 2.1 Split Key & Causality Rule
The temporal partitioning is controlled by the **forecast target date (`date`)**, and verified against the **`forecast_issue_date`**:
- In Pune, `lead_days = 1` for all records ($\text{date} = \text{forecast\_issue\_date} + 1\text{ day}$).
- The chronological ordering rule guarantees that no information from future forecasting periods enters past folds:
$$\max(\text{train\_date}) < \min(\text{val\_date}) \quad \text{and} \quad \max(\text{val\_date}) < \min(\text{test\_date})$$
$$\max(\text{train\_issue}) < \min(\text{val\_issue}) \quad \text{and} \quad \max(\text{val\_issue}) < \min(\text{test\_issue})$$

### 2.2 Exact Partition Boundaries (Pune Dataset, $N = 187,320$)

| Split Name | Calendar Period | Forecast Issue Period | Unique Dates | Row Count | Dataset % | Meteorological & Operational Role |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Train** | $2026-04-13$ to $2026-07-31$ | $2026-04-12$ to $2026-07-30$ | 89 dates | **119,082** | 63.57% | Covers pre-monsoon convective heating (April–May) and active monsoon onset & heavy cloudbursts (June–July). |
| **Validation** | $2026-08-01$ to $2026-08-31$ | $2026-07-31$ to $2026-08-30$ | 28 dates | **37,464** | 20.00% | Covers persistent synoptic mid-monsoon spell in August. Used for model diagnostics and hyperparameter decisions. |
| **Test (LOCKED)** | $2026-09-01$ to $2026-09-23$ | $2026-08-31$ to $2026-09-22$ | 23 dates | **30,774** | 16.43% | Covers monsoon withdrawal phase in September. Sealed as an immutable future simulation. |

### 2.3 Panchayat Continuity Analysis
- Total unique Panchayats in Pune: **1,338**.
- Panchayats present in Train: 1,338 (**100.0%**).
- Panchayats present in Validation: 1,338 (**100.0%**).
- Panchayats present in Test: 1,338 (**100.0%**).
- Shared across all three splits: **1,338 (100.0%)**.
- Panchayats only in Train or only in Test: **0**.
*Finding*: Full spatial temporal continuity is achieved across all 1,338 Panchayats without artificial entity dropping.

### 2.4 District Evaluation Strategy
- **Pune**: Primary dataset for chronological temporal training, validation, and testing.
- **Nashik**: Single-observation spatial snapshot per Panchayat (1,388 rows across 9 snapshot dates). Evaluated as an **Out-of-District Spatial Generalization Benchmark** to assess whether downscaling models transfer to unseen administrative jurisdictions.

---

## 3. Baseline Model Formulations

### 3.1 Baseline 1: Raw Numerical Block Forecast (`block_forecast`)
- **Definition**: Uses the coarse regional NWP forecast directly as the Panchayat prediction without any downscaling or adjustment:
$$\widehat{y}_{\text{block}} = \text{block\_forecast\_rainfall\_mm}$$
- **Domain Interpretation**: Represents the status quo coarse-resolution (~20 km) forecast issued by IMD/NCMRWF before GramSevak hyper-local downscaling.

### 3.2 Baseline 2: Simple Statistical Linear Baseline (`linear_regression`)
- **Definition**: A transparent, regularized linear regression model with non-negative prediction clipping:
$$\widehat{y}_{\text{linear}} = \max\Big(0.0, \; \mathbf{w}^T \mathbf{x} + b\Big)$$
- **Algorithm**: `Ridge(alpha=1.0)` with `StandardScaler` and training median imputation for warm-up `NaN` values.
- **Features Used ($k=10$)**:
  1. `block_forecast_rainfall_mm` (macro numerical signal)
  2. `panchayat_latitude` (geographic coordinate)
  3. `panchayat_longitude` (geographic coordinate)
  4. `elevation_m` (topography)
  5. `station_distance_km` (station proximity)
  6. `lead_days` (forecast horizon)
  7. `target_day_of_year_sin` (calendar seasonality)
  8. `target_day_of_year_cos` (calendar seasonality)
  9. `historical_rainfall_prior_1d_mm` (antecedent rainfall)
  10. `has_historical_rainfall_context` (missing history indicator)
- **Training Rule**: Trained **strictly on the Pune Train split** ($N = 119,082$). Zero validation or test records were observed during fitting.
- **Learned Parameters**:
  - Intercept $b = 7.091011$
  - Key Coefficients: `block_forecast_rainfall_mm`: $+2.23886$, `historical_rainfall_prior_1d_mm`: $+2.98297$, `has_historical_rainfall_context`: $-2.89562$, `target_day_of_year_sin`: $-6.17542$, `target_day_of_year_cos`: $+2.09654$.

---

## 4. Comprehensive Evaluation Metrics & Thresholds

### 4.1 Regression Metrics
- **Mean Absolute Error (MAE)**: $\frac{1}{N}\sum |y_i - \widehat{y}_i|$
- **Root Mean Squared Error (RMSE)**: $\sqrt{\frac{1}{N}\sum (y_i - \widehat{y}_i)^2}$
- **Mean Error / Bias**: $\frac{1}{N}\sum (\widehat{y}_i - y_i)$ ($>0$: over-prediction, $<0$: under-prediction)
- **Pearson Correlation ($r$)**: Linear association between ground-truth and prediction.
- **Coefficient of Determination ($R^2$)**: $1 - \frac{\sum (y_i - \widehat{y}_i)^2}{\sum (y_i - \bar{y})^2}$

### 4.2 Rain Occurrence Metrics (IMD Trace Threshold $> 0.0\text{ mm}$)
Binary classification of dry ($0.0\text{ mm}$) versus rainy days ($> 0.0\text{ mm}$):
- Precision, Recall, and F1-score.

### 4.3 Sliced Rain Intensity Metrics (IMD Standard Thresholds)
- **Zero-Rainfall Slice (`actual == 0.0 mm`)**: Tests false alarms on dry days.
- **Non-Zero Rainfall Slice (`actual > 0.0 mm`)**: Tests accuracy on rainy days without dilution from dry days.
- **Heavy Rainfall Slice (`actual >= 35.5 mm`)**: Tests failure modes on convective cloudbursts.

---

## 5. Baseline Benchmark Results Table

All metrics below are computed from [`scripts/evaluate_baselines.py`](file:///c:/sih/sih26074-weather-downscaling/scripts/evaluate_baselines.py) and verified against [`reports/phase-2-3-baseline-results.json`](file:///c:/sih/sih26074-weather-downscaling/reports/phase-2-3-baseline-results.json).

| Dataset & Split | Evaluation Metric | Baseline 1: Raw Block Forecast | Baseline 2: Simple Linear Ridge | Benchmark Takeaway |
| :--- | :--- | :---: | :---: | :--- |
| **Pune Validation**<br>*(August 2026, $N=37,464$)* | **MAE (All Records)**<br>**RMSE (All Records)**<br>**Mean Bias**<br>**Pearson $r$**<br>**$R^2$ Score**<br>**Rain Occurrence F1**<br>**Non-Zero MAE**<br>**Heavy Rain MAE ($\ge 35.5$)** | **5.7464 mm**<br>**7.1634 mm**<br>+2.6893 mm<br>0.4256<br>0.0333<br>**1.0000**<br>5.7464 mm<br>25.9687 mm | **18.3521 mm**<br>**18.8882 mm**<br>+17.6377 mm<br>0.3820<br>-5.7196<br>**1.0000**<br>18.3521 mm<br>15.2289 mm | **Block Forecast outperforms Linear Regression on MAE/RMSE in August.** Linear regression suffers catastrophic positive bias (+17.6 mm) due to linear extrapolation of monsoon seasonal sin/cos features. |
| **Pune Test (LOCKED)**<br>*(September 2026, $N=30,774$)* | **MAE (All Records)**<br>**RMSE (All Records)**<br>**Mean Bias**<br>**Pearson $r$**<br>**$R^2$ Score**<br>**Rain Occurrence F1**<br>**Non-Zero MAE**<br>**Heavy Rain MAE ($\ge 35.5$)** | **4.5783 mm**<br>**5.0508 mm**<br>+2.8739 mm<br>0.1610<br>-0.4578<br>**0.9547**<br>4.9213 mm<br>— *(N/A)* | **23.9176 mm**<br>**24.1842 mm**<br>+23.9176 mm<br>0.5437<br>-32.4498<br>**0.9547**<br>23.9789 mm<br>— *(N/A)* | **Locked Test Benchmark**: Future ML models in Phase 2.4 must beat **Test MAE = 4.58 mm** and **RMSE = 5.05 mm**. |
| **Nashik Transferability**<br>*(Snapshot, $N=1,388$)* | **MAE (All Records)**<br>**RMSE (All Records)**<br>**Mean Bias**<br>**Pearson $r$** | **4.3651 mm**<br>**5.5919 mm**<br>+2.2980 mm<br>0.8777 | **2.6713 mm**<br>**3.7847 mm**<br>-1.0509 mm<br>0.8920 | **Linear model transfers well to Nashik snapshot** ($\text{MAE}=2.67\text{ mm}$ vs $4.37\text{ mm}$ baseline), indicating that static elevation and coordinates provide valuable downscaling signal when temporal shift is absent. |

---

## 6. Critical Baseline Failure Modes & Empirical Findings

1. **Seasonal Extrapolation Failure in Linear Models**:
   - In Train (April–July), actual rainfall averaged $8.32\text{ mm}$ with peak July storms averaging $20.45\text{ mm}$.
   - In August (Validation), actual rainfall dropped to $5.96\text{ mm}$, and in September (Test) to $2.94\text{ mm}$.
   - The linear model learned steep positive weights on `block_forecast_rainfall_mm` ($+2.24$) and `historical_rainfall_prior_1d_mm` ($+2.98$), combined with linear drift from periodic sine/cosine features. As a result, the linear model severely overpredicted late-monsoon rainfall (Bias $= +17.64\text{ mm}$ in August, $+23.92\text{ mm}$ in September).
   - **Conclusion**: Linear models are fundamentally ill-suited for seasonal weather downscaling. **Non-linear tree-based models with step-wise thresholding (Random Forest in Phase 2.4) are mandatory.**
2. **NWP Regional Compression on Heavy Rain Events**:
   - The raw block forecast caps its predictions around $12.4\text{ mm}$, failing to resolve local convective cloudbursts.
   - On heavy rainfall events ($\ge 35.5\text{ mm}$), the block forecast suffers an MAE of $25.97\text{ mm}$ in August and $63.28\text{ mm}$ overall.
3. **Panchayat Spatial Variance Uncaptured by Block Forecast**:
   - Within any single block, the raw block forecast assigns identical rainfall to all Panchayats, ignoring high-altitude Ghats ridge communities vs low-altitude valley communities.
   - Across Panchayats in Pune, block forecast MAE ranges from $3.2\text{ mm}$ to $11.4\text{ mm}$ (Panchayat MAE std $= 1.48\text{ mm}$).

---

## 7. Panchayat-Level Error Diagnostics (August Validation)

Evaluating performance across all 1,338 Panchayats in Pune:
- **Panchayats Evaluated**: 1,338 (100.0%)
- **Block Forecast MAE Distribution across Panchayats**:
  - Minimum Panchayat MAE: **3.89 mm**
  - 25th Percentile (p25): **4.97 mm**
  - Median Panchayat MAE: **5.58 mm**
  - 75th Percentile (p75): **6.40 mm**
  - Maximum Panchayat MAE: **11.23 mm**
  - Inter-Panchayat Std Dev: **1.09 mm**

---

## 8. Test-Set Discipline & Seal

The test period (**September 1 to September 23, 2026**, 30,774 rows) is officially **SEALED AND LOCKED**:
- The test metrics ($\text{MAE} = 4.5783\text{ mm}$, $\text{RMSE} = 5.0508\text{ mm}$) serve exclusively as the final future simulation benchmark.
- In Phase 2.4 (Random Forest), model selection, hyperparameter tuning, and feature pruning **must strictly take place using the Validation split (August 2026)**.
- The test set will only be evaluated once during final model benchmarking.

---

## 9. Readiness for Phase 2.4

Phase 2.3 has successfully established the reproducible chronological split, the locked test protocol, and the quantitative benchmark:

| Metric Target for Phase 2.4 Random Forest | Benchmark to Beat |
| :--- | :---: |
| **Validation MAE (August)** | **< 5.7464 mm** |
| **Validation RMSE (August)** | **< 7.1634 mm** |
| **Heavy Rainfall MAE ($\ge 35.5$ mm)** | **< 25.9687 mm** |
| **Test Set MAE (September, Locked)** | **< 4.5783 mm** |

**Phase 2.4 (Random Forest Implementation & Tuning) is approved to begin.**
