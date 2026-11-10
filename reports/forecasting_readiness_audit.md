# Forecasting readiness audit

- Generated (UTC): 2026-11-02T17:31:07+00:00
- Monthly disease source: `data/processed/kerala_disease_monthly_2021_2024.csv`
- Coverage: 2021-01 to 2024-12 (48 months; 96 disease/classification records).
- Unit: statewide monthly reported cases; annual district records are excluded.

## Candidate series coverage

| Disease | Source classification | Valid observations | Reporting range | Missing months | Duplicate months | Zero cases | IQR flags for review | Source files |
|---|---|---:|---|---:|---:|---:|---|---|
| Dengue | reported_category_status_not_split | 12 | 2021-01 to 2021-12 | 0 | 0 | 0 | [{'period': '2021-06', 'cases': 508}, {'period': '2021-07', 'cases': 938}] | DATA-ON-COMMUNICABLE-DISEASE-2021.pdf |
| Dengue | non_probable_category_probable_separate | 12 | 2022-01 to 2022-12 | 0 | 0 | 0 | [] | CD-Data-2022_Signed.pdf |
| Dengue | Confirmed | 24 | 2023-01 to 2024-12 | 0 | 0 | 0 | [] | Final-IDSP-70-IDSP-STATE_DATA_MANAGER-2024-NHM-pages.pdf; IDSP-Annual-Data-2024.pdf |
| Leptospirosis | reported_category_status_not_split | 12 | 2021-01 to 2021-12 | 0 | 0 | 0 | [] | DATA-ON-COMMUNICABLE-DISEASE-2021.pdf |
| Leptospirosis | non_probable_category_probable_separate | 12 | 2022-01 to 2022-12 | 0 | 0 | 0 | [] | CD-Data-2022_Signed.pdf |
| Leptospirosis | Confirmed | 24 | 2023-01 to 2024-12 | 0 | 0 | 0 | [] | Final-IDSP-70-IDSP-STATE_DATA_MANAGER-2024-NHM-pages.pdf; IDSP-Annual-Data-2024.pdf |

Classifications remain separate: 2021 `reported_category_status_not_split`, 2022 `non_probable_category_probable_separate`, and 2023–2024 `Confirmed`. The labels and notes do not justify merging 2021 or 2022 into a confirmed-case target. The 2023 and 2024 confirmed records use different source documents; both explicitly label the monthly case series `Confirmed`, but this document transition is a comparability limitation requiring source review.

The Tukey 1.5×IQR flags are screening indicators only, not errors or grounds for removal. In particular, flagged dengue observations in 2021 remain intact and belong to their own unharmonized source category.

## Evaluation readiness

The proposed 2021–2023 training / 2024 test is **not feasible as one compatible series**, because the source classifications differ. For the exact `Confirmed` category, a limited 2023 training / 2024 holdout is complete and unique (12 months in each year) for both diseases. This one-year holdout is exploratory and cannot establish stable future performance.

Only 24 adjacent, explicitly Confirmed observations are available (2023-2024). A 12-month initial training period and 12-month horizon yields only one origin, not repeated rolling-origin validation.

The 2025 annual DHS import, 2026 daily IDSP reports, and annual district panel are excluded. No monthly values are filled, interpolated, or constructed from annual district totals.

## Climate feature readiness

The monthly weather file aligns on `24` confirmed disease-month records. Equal-weight proxy of 14 representative district locations; not population weighted.
The compatible training window has only 12 months, insufficient for defensible climate-lag selection or multivariable estimation. Observed 2024 weather is also not a feature available at a 2023 forecast origin; using it for the 2024 horizon would leak future information.
