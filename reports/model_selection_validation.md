# Model selection and uncertainty validation

## Scope and input integrity

This evaluation reads saved predictions only. It does not retrain models or write to the existing experiment directory. Input: `reports/multimodel_experiment/predictions.csv`, SHA-256 `46c70a4a75c65ce1b7efa535305a3dfa7aa67bc04d38ed77538b7757995aeca2`. Original experiment metadata reports disease-candidate SHA-256 `283c202f132261b77f86710c32649f6102ce258e0cc54eaadd83d4fd808c0f23` and weather-candidate SHA-256 `85364a93b25a741b2eaf5080f958fee764ac557821e03fe1e663e7c73518e175`.

All eligible model/feature candidates were checked against identical disease, classification, geographic level, validation phase/window, origin, target period, district, and horizon keys, with exactly matching actual counts. The saved prediction file contains 11,760 records; 10,080 development rolling-origin records and 1,680 final-2025 records. Saved experiment fit/forecast failures: 0.

## Experimental selection method

Selection is performed independently for Dengue and Leptospirosis at horizons 1, 3, 6, and 12 months. Only `rolling_origin` records are used; the 2025 final holdout is excluded. A candidate must have at least 5 rolling origins and 70 equivalent predictions, both 80% and 95% predictive intervals, aggregate coverage within 10 percentage points of nominal, per-origin minimum coverage of at least 50% (80% intervals) and 70% (95% intervals), and fold MAE coefficient of variation no greater than 2.0.

Eligible candidates are ranked on a prespecified composite: 40% average MAE/RMSE rank, 40% average proper 80%/95% interval-score rank (which penalizes both misses and unnecessarily wide intervals), and 20% fold-MAE-variability rank. If the best two candidates are within 0.10 composite-score units, the engine returns `insufficient_evidence` rather than forcing a winner. A unique eligible candidate can be selected only after passing the same uncertainty and stability gates.

The selection policy is an experimental evidence filter, not an automated production model-switching policy. Six rolling origins are limited evidence, and nearby annual origins are not equivalent to six independent trials.

## Selection results

| disease | horizon | selection_status | selected_candidate_id | eligible_candidate_count | score_margin | reason |
| --- | --- | --- | --- | --- | --- | --- |
| Dengue | 1 | selected_experimental | negative_binomial_regression::disease_history_and_climate | 3 | 0.200 | Candidate passed coverage and fold-stability gates and ranked best on the prespecified accuracy/interval-score/stability composite. |
| Dengue | 3 | selected_experimental | negative_binomial_regression::disease_history_and_climate | 1 | N/A | Candidate passed coverage and fold-stability gates and ranked best on the prespecified accuracy/interval-score/stability composite. |
| Dengue | 6 | insufficient_evidence | nan | 0 | N/A | No candidate met the minimum rolling-origin evidence, fold stability, and interval-coverage requirements. |
| Dengue | 12 | insufficient_evidence | nan | 0 | N/A | No candidate met the minimum rolling-origin evidence, fold stability, and interval-coverage requirements. |
| Leptospirosis | 1 | selected_experimental | negative_binomial_regression::disease_history_and_climate | 1 | N/A | Candidate passed coverage and fold-stability gates and ranked best on the prespecified accuracy/interval-score/stability composite. |
| Leptospirosis | 3 | selected_experimental | negative_binomial_regression::disease_history | 2 | 0.500 | Candidate passed coverage and fold-stability gates and ranked best on the prespecified accuracy/interval-score/stability composite. |
| Leptospirosis | 6 | selected_experimental | negative_binomial_regression::disease_history | 2 | 0.500 | Candidate passed coverage and fold-stability gates and ranked best on the prespecified accuracy/interval-score/stability composite. |
| Leptospirosis | 12 | insufficient_evidence | nan | 0 | N/A | No candidate met the minimum rolling-origin evidence, fold stability, and interval-coverage requirements. |

Selected experimentally: 5 of 8 disease/horizon combinations. These statuses are comparative outputs only; they do not establish clinical readiness or disease-definition consistency.

## Rolling-origin predictive interval review

The nominal 80% and 95% quantities are **predictive intervals** for future counts, not confidence intervals for model parameters or the mean. Coverage tolerance is used to flag undercoverage (more than 10 percentage points below nominal) and overcoverage (more than 10 points above nominal). Overcoverage can indicate overly wide intervals; interval-score ranking penalizes this.

| disease | model_name | feature_set | horizon | n_predictions | n_origins | coverage_80 | coverage_95 | mean_width_80 | mean_width_95 | coverage_assessment_80 | coverage_assessment_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dengue | negative_binomial_regression | disease_history | 1 | 84 | 6 | 83.3% | 95.2% | 37.50 | 59.02 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history | 3 | 84 | 6 | 72.6% | 85.7% | 17.94 | 28.20 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history | 6 | 84 | 6 | 54.8% | 79.8% | 176.12 | 277.86 | undercoverage | undercoverage |
| Dengue | negative_binomial_regression | disease_history | 12 | 84 | 6 | 52.4% | 67.9% | 30.06 | 47.31 | undercoverage | undercoverage |
| Dengue | negative_binomial_regression | disease_history_and_climate | 1 | 84 | 6 | 85.7% | 95.2% | 40.57 | 63.94 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history_and_climate | 3 | 84 | 6 | 76.2% | 89.3% | 28.64 | 45.24 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history_and_climate | 6 | 84 | 6 | 52.4% | 81.0% | 242.24 | 381.54 | undercoverage | undercoverage |
| Dengue | negative_binomial_regression | disease_history_and_climate | 12 | 84 | 6 | 42.9% | 54.8% | 32.39 | 50.93 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history | 1 | 84 | 6 | 60.7% | 72.6% | 10.19 | 15.54 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history | 3 | 84 | 6 | 48.8% | 64.3% | 7.90 | 12.06 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history | 6 | 84 | 6 | 13.1% | 16.7% | 25.08 | 38.27 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history | 12 | 84 | 6 | 23.8% | 32.1% | 10.61 | 16.23 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 1 | 84 | 6 | 64.3% | 73.8% | 10.43 | 15.76 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 3 | 84 | 6 | 42.9% | 52.4% | 9.42 | 14.31 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 6 | 84 | 6 | 17.9% | 23.8% | 23.27 | 35.65 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 12 | 84 | 6 | 20.2% | 26.2% | 10.21 | 15.43 | undercoverage | undercoverage |
| Dengue | seasonal_naive | disease_history | 1 | 84 | 6 | 85.7% | 97.6% | 69.82 | 224.55 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | seasonal_naive | disease_history | 3 | 84 | 6 | 95.2% | 100.0% | 65.88 | 218.14 | overcoverage | within_10_percentage_point_tolerance |
| Dengue | seasonal_naive | disease_history | 6 | 84 | 6 | 65.5% | 88.1% | 90.79 | 258.01 | undercoverage | within_10_percentage_point_tolerance |
| Dengue | seasonal_naive | disease_history | 12 | 84 | 6 | 66.7% | 84.5% | 73.56 | 233.68 | undercoverage | undercoverage |
| Leptospirosis | negative_binomial_regression | disease_history | 1 | 84 | 6 | 90.5% | 98.8% | 12.89 | 20.25 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history | 3 | 84 | 6 | 89.3% | 96.4% | 10.32 | 16.18 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history | 6 | 84 | 6 | 72.6% | 90.5% | 23.33 | 36.79 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history | 12 | 84 | 6 | 72.6% | 88.1% | 26.06 | 41.15 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 1 | 84 | 6 | 86.9% | 97.6% | 12.20 | 19.07 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 3 | 84 | 6 | 83.3% | 91.7% | 13.51 | 21.02 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 6 | 84 | 6 | 70.2% | 83.3% | 18.35 | 28.69 | within_10_percentage_point_tolerance | undercoverage |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 12 | 84 | 6 | 46.4% | 61.9% | 10.98 | 17.13 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history | 1 | 84 | 6 | 65.5% | 85.7% | 5.87 | 8.85 | undercoverage | within_10_percentage_point_tolerance |
| Leptospirosis | poisson_regression | disease_history | 3 | 84 | 6 | 65.5% | 81.0% | 4.93 | 7.27 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history | 6 | 84 | 6 | 40.5% | 57.1% | 7.60 | 11.49 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history | 12 | 84 | 6 | 39.3% | 52.4% | 7.50 | 11.48 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history_and_climate | 1 | 84 | 6 | 71.4% | 79.8% | 5.49 | 8.23 | within_10_percentage_point_tolerance | undercoverage |
| Leptospirosis | poisson_regression | disease_history_and_climate | 3 | 84 | 6 | 69.0% | 78.6% | 4.83 | 7.11 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history_and_climate | 6 | 84 | 6 | 46.4% | 57.1% | 4.68 | 7.08 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history_and_climate | 12 | 84 | 6 | 13.1% | 23.8% | 3.63 | 5.39 | undercoverage | undercoverage |
| Leptospirosis | seasonal_naive | disease_history | 1 | 84 | 6 | 92.9% | 100.0% | 17.25 | 37.22 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | seasonal_naive | disease_history | 3 | 84 | 6 | 94.0% | 96.4% | 16.04 | 35.47 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | seasonal_naive | disease_history | 6 | 84 | 6 | 76.2% | 92.9% | 18.18 | 39.94 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | seasonal_naive | disease_history | 12 | 84 | 6 | 70.2% | 92.9% | 19.39 | 42.50 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |

Across the 120 rolling model/disease/horizon summaries (all 12 horizons), 80% intervals are flagged undercovered in 80 groups and 95% intervals in 75; overcoverage flags occur in 8 80% groups and 0 95% groups. Undercoverage indicates intervals are too narrow or otherwise miss more often than the nominal level suggests; it is a warning of overconfident predictive uncertainty, especially for longer-horizon Dengue and Poisson variants. Some Seasonal Naive and short-horizon Leptospirosis intervals overcover, with very large widths. Model/horizon-specific results and widths are in `reports/model_intelligence/uncertainty_review.csv`. Coverage is calculated over district predictions pooled across origins; origin-level minima are also used as a selection gate. This is diagnostic evidence, not proof of calibrated uncertainty.

## Final 2025 holdout (descriptive only)

The following summaries are reported for transparency, but were not used for eligibility, scoring, or selection. At each horizon there is one origin and 14 district observations per disease/model, too little to establish calibration.

| disease | model_name | feature_set | horizon | n_predictions | n_origins | coverage_80 | coverage_95 | mean_width_80 | mean_width_95 | coverage_assessment_80 | coverage_assessment_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dengue | negative_binomial_regression | disease_history | 1 | 14 | 1 | 92.9% | 100.0% | 72.29 | 114.00 | overcoverage | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history | 3 | 14 | 1 | 92.9% | 100.0% | 43.64 | 68.64 | overcoverage | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history | 6 | 14 | 1 | 35.7% | 92.9% | 392.71 | 618.36 | undercoverage | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history | 12 | 14 | 1 | 78.6% | 92.9% | 104.29 | 164.07 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history_and_climate | 1 | 14 | 1 | 85.7% | 100.0% | 74.50 | 117.64 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history_and_climate | 3 | 14 | 1 | 85.7% | 100.0% | 63.43 | 99.71 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history_and_climate | 6 | 14 | 1 | 35.7% | 92.9% | 368.43 | 579.43 | undercoverage | within_10_percentage_point_tolerance |
| Dengue | negative_binomial_regression | disease_history_and_climate | 12 | 14 | 1 | 71.4% | 85.7% | 97.14 | 152.79 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Dengue | poisson_regression | disease_history | 1 | 14 | 1 | 35.7% | 57.1% | 16.57 | 24.93 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history | 3 | 14 | 1 | 21.4% | 42.9% | 13.43 | 20.29 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history | 6 | 14 | 1 | 0.0% | 14.3% | 36.00 | 54.93 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history | 12 | 14 | 1 | 28.6% | 28.6% | 22.93 | 35.14 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 1 | 14 | 1 | 28.6% | 57.1% | 16.29 | 25.14 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 3 | 14 | 1 | 14.3% | 35.7% | 14.71 | 22.29 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 6 | 14 | 1 | 7.1% | 21.4% | 30.93 | 47.21 | undercoverage | undercoverage |
| Dengue | poisson_regression | disease_history_and_climate | 12 | 14 | 1 | 42.9% | 64.3% | 19.07 | 29.21 | undercoverage | undercoverage |
| Dengue | seasonal_naive | disease_history | 1 | 14 | 1 | 50.0% | 78.6% | 142.10 | 351.01 | undercoverage | undercoverage |
| Dengue | seasonal_naive | disease_history | 3 | 14 | 1 | 35.7% | 85.7% | 141.60 | 342.72 | undercoverage | within_10_percentage_point_tolerance |
| Dengue | seasonal_naive | disease_history | 6 | 14 | 1 | 35.7% | 78.6% | 142.60 | 373.37 | undercoverage | undercoverage |
| Dengue | seasonal_naive | disease_history | 12 | 14 | 1 | 64.3% | 92.9% | 140.81 | 336.13 | undercoverage | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history | 1 | 14 | 1 | 92.9% | 100.0% | 19.71 | 30.71 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history | 3 | 14 | 1 | 85.7% | 100.0% | 16.50 | 25.43 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history | 6 | 14 | 1 | 64.3% | 92.9% | 35.36 | 55.71 | undercoverage | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history | 12 | 14 | 1 | 78.6% | 85.7% | 44.14 | 69.00 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 1 | 14 | 1 | 100.0% | 100.0% | 22.07 | 34.50 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 3 | 14 | 1 | 85.7% | 92.9% | 29.29 | 45.57 | within_10_percentage_point_tolerance | within_10_percentage_point_tolerance |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 6 | 14 | 1 | 64.3% | 71.4% | 35.64 | 55.79 | undercoverage | undercoverage |
| Leptospirosis | negative_binomial_regression | disease_history_and_climate | 12 | 14 | 1 | 50.0% | 85.7% | 26.71 | 41.71 | undercoverage | within_10_percentage_point_tolerance |
| Leptospirosis | poisson_regression | disease_history | 1 | 14 | 1 | 57.1% | 71.4% | 8.00 | 12.29 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history | 3 | 14 | 1 | 71.4% | 78.6% | 6.64 | 9.86 | within_10_percentage_point_tolerance | undercoverage |
| Leptospirosis | poisson_regression | disease_history | 6 | 14 | 1 | 28.6% | 42.9% | 9.79 | 14.64 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history | 12 | 14 | 1 | 42.9% | 50.0% | 10.79 | 16.64 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history_and_climate | 1 | 14 | 1 | 64.3% | 85.7% | 8.29 | 12.93 | undercoverage | within_10_percentage_point_tolerance |
| Leptospirosis | poisson_regression | disease_history_and_climate | 3 | 14 | 1 | 57.1% | 71.4% | 8.79 | 13.43 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history_and_climate | 6 | 14 | 1 | 14.3% | 35.7% | 8.86 | 13.57 | undercoverage | undercoverage |
| Leptospirosis | poisson_regression | disease_history_and_climate | 12 | 14 | 1 | 14.3% | 14.3% | 7.21 | 10.86 | undercoverage | undercoverage |
| Leptospirosis | seasonal_naive | disease_history | 1 | 14 | 1 | 92.9% | 100.0% | 30.27 | 58.48 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | seasonal_naive | disease_history | 3 | 14 | 1 | 100.0% | 100.0% | 28.70 | 55.52 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | seasonal_naive | disease_history | 6 | 14 | 1 | 92.9% | 100.0% | 31.49 | 61.30 | overcoverage | within_10_percentage_point_tolerance |
| Leptospirosis | seasonal_naive | disease_history | 12 | 14 | 1 | 92.9% | 100.0% | 32.34 | 63.47 | overcoverage | within_10_percentage_point_tolerance |

## Limits

All experiment outputs remain exploratory because historical dashboard classification consistency has not been officially established. Uncertainty summaries assess empirical coverage only; they do not establish prospective calibration. No confidence intervals are implied by predictive intervals. No outbreak labels or official thresholds were evaluated. Forecasting, retrospective unusual-activity detection, and outbreak threshold-exceedance probability remain distinct tasks.
