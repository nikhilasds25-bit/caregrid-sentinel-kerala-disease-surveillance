# Multi-model experiment data readiness

## Result

The separate dashboard-native Confirmed panel is structurally usable for an exploratory district-month comparison. This is not a finding that its disease definitions are stable over time or equivalent to DHS categories.

| Check | Result |
|---|---:|
| Districts | 14 |
| Monthly periods | 120 (2016-01 through 2025-12) |
| Confirmed disease rows | 3360 |
| Rows per disease | {"Dengue": 1680, "Leptospirosis": 1680} |
| Missing Confirmed counts | 0 |
| Explicit Confirmed zeros | 224 |
| Dashboard district/state case mismatch cells (all classifications) | 4 |
| Confirmed mismatch cells | 2 |
| Confirmed district rows linked to a mismatch cell | 28 |
| Disease-weather matched rows | 3360 |

Suspected records are excluded from model targets and remain a distinct source-native classification. The DHS Probable category is not mapped to dashboard Suspected. All four source reconciliation mismatch cells remain in the reconciliation output; the two Confirmed mismatch cells are attached to each affected district row as flags. District observations were not adjusted.

## Source integrity

- Disease candidate: `data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.csv`; SHA-256 `283c202f132261b77f86710c32649f6102ce258e0cc54eaadd83d4fd808c0f23`.
- Source snapshot SHA-256: `ca401184db2f983030d3fd26eb94872aa3cc61f6be340067aef1e362bdd2101c`.
- Weather candidate: `data/candidates/kerala_district_representative_weather_monthly_2016_2025.csv`; SHA-256 `85364a93b25a741b2eaf5080f958fee764ac557821e03fe1e663e7c73518e175`.
- Reconciliation SHA-256: `be1527ecb468f0bfa811314605b3c2835af6b8e4fa149cc055393e6a599c7486`.
- Both candidate hashes and the reconciliation hash were verified by the loader against their sidecar metadata before the experiment.

## Feature readiness and limits

The history-only regressions use district, month-of-year, a linear time trend, and the previous month's Confirmed case count. Climate variants add origin-known previous-month rainfall, a preceding-three-month rainfall sum, mean temperature, temperature range, relative humidity, and dew point. Numerical features are standardized from each training fold only.

All 3,360 Confirmed district-month rows match complete representative-location weather rows. These weather data are single representative points per district, not district-wide areal averages. Climate predictors for each forecast are frozen at the forecast origin; no realized target-period weather is used.

No values were imputed, no source categories were merged, and no district-to-state discrepancies were corrected. The 2025 period is reserved as a final chronological holdout; it does not participate in fitting or model tuning.
