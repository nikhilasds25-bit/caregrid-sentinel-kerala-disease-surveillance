# Kerala dashboard disease data audit: 2016–2025

**Audit date:** 2026-11-10
**Scope:** Four Kerala Health Department dashboard categories by month and district, source integrity, missingness, zeros, and district-to-state reconciliation. This is a source-native audit, not a harmonization decision.

## Executive findings

- The preserved [dashboard JSON snapshot](../data/raw/kerala_health_disease_data_2026-11-10.json) contains every year from 2016 through 2025, a `KERALA` aggregate, 14 district keys, and all 12 month keys for every district in each year.
- In the checked target categories, 2016 has Dengue and Leptospirosis `Confirmed` data but **no `Suspected` category**. Missing suspected cases/deaths are unavailable, not zero.
- 2017–2025 have all four source categories (`DENGUE|Con`, `DENGUE|Sus`, `LEPTO|Con`, `LEPTO|Sus`) for all 14 districts and all 12 months. Both `C` (Cases) and `D` (Deaths) are present as non-negative integer counts in every category cell present in the snapshot.
- The new dense candidate contains 6,720 district-month-category rows. Of these, 6,384 are available source observations and 336 explicitly mark unavailable 2016 suspected cells with null cases/deaths.
- Four category-month case totals do not reconcile from district sums to the dashboard's state total. All available death totals reconcile. These differences are preserved and flagged, not adjusted.
- The dashboard's recurring codes and labels are structurally stable from 2017 to 2025. The snapshot does not contain clinical definitions, method/version history, or reporting cut-off documentation; stable labels do not establish stable epidemiological meaning.

## Snapshot and reproducibility

| Property | Value |
|---|---|
| Dashboard | [Kerala Health Department disease prevalence dashboard](https://health.kerala.gov.in/static_disease_prevalence) |
| JSON endpoint linked by the dashboard | [https://health.kerala.gov.in/disease_data.json](https://health.kerala.gov.in/disease_data.json) |
| Captured server response date | `Tue, 10 Nov 2026 10:05:34 GMT` |
| Client retrieval time (UTC) | `2026-11-10T10:05:57.0743381+00:00` |
| HTTP status / bytes | 200 / 2,135,717 |
| ETag | `"2096a5-6526c5fad5595"` |
| SHA-256 | `ca401184db2f983030d3fd26eb94872aa3cc61f6be340067aef1e362bdd2101c` |
| Retrieval metadata | [`kerala_health_disease_data_2026-11-10.metadata.json`](../data/raw/kerala_health_disease_data_2026-11-10.metadata.json) |

The public JSON endpoint is mutable and the response has no dataset version. All candidate outputs are rebuilt from this captured snapshot and bind to its hash; a later refresh is a new source version, not an in-place replacement.

## Coverage and missingness by year

Each expected category has 14 districts × 12 months = 168 possible district-month cells. Cases and deaths are counted separately. The zero columns below count source cells whose corresponding numeric measure is explicitly `0`; they are not missing-value counts.

| Year | Districts | Months per district | Category coverage | Suspected district-month cells unavailable | Explicit zero cases | Explicit zero deaths |
|---:|---:|---:|---|---:|---:|---:|
| 2016 | 14 | 12 | Dengue Confirmed, Leptospirosis Confirmed | 336 | 30 | 295 |
| 2017 | 14 | 12 | All four categories | 0 | 34 | 536 |
| 2018 | 14 | 12 | All four categories | 0 | 41 | 530 |
| 2019 | 14 | 12 | All four categories | 0 | 32 | 555 |
| 2020 | 14 | 12 | All four categories | 0 | 53 | 535 |
| 2021 | 14 | 12 | All four categories | 0 | 32 | 501 |
| 2022 | 14 | 12 | All four categories | 0 | 17 | 473 |
| 2023 | 14 | 12 | All four categories | 0 | 19 | 445 |
| 2024 | 14 | 12 | All four categories | 0 | 6 | 402 |
| 2025 | 14 | 12 | All four categories | 0 | 7 | 436 |

The 2016 absence is at both district and `KERALA` aggregate levels for both Suspected categories. There are no partially populated target categories or missing numeric metrics among category records present in the captured source. The candidate contains 267 rows where both available cases and deaths are explicitly zero; these remain zeros. Other zero-valued case or death fields are preserved independently.

The source is nested by unique year, district, month, and category keys; the flattened candidate has zero duplicate `(period, district, disease, classification)` keys. JSON object structure does not represent multiple duplicate records for a key.

## District-to-state reconciliation

Statewide aggregates are **not included as rows** in the district candidate. They are stored separately in [`kerala_district_monthly_disease_dashboard_2016_2025_reconciliation.csv`](../data/candidates/kerala_district_monthly_disease_dashboard_2016_2025_reconciliation.csv), with both the 14-district sum and the dashboard's `KERALA` value.

Of the 480 year-month/category comparisons, 24 2016 Suspected category-months are unavailable. Among the remaining 456:

- 452 case totals match and 4 do not.
- All 456 death totals match.

| Period | Category | District case sum | Dashboard state cases | Difference (district sum minus state) |
|---|---|---:|---:|---:|
| 2016-05 | Dengue Confirmed | 659 | 639 | +20 |
| 2017-07 | Leptospirosis Suspected | 272 | 286 | -14 |
| 2022-10 | Dengue Suspected | 1,334 | 1,314 | +20 |
| 2022-10 | Leptospirosis Confirmed | 248 | 233 | +15 |

No value was changed to force reconciliation. Investigate these with the department before treating the state and district series as a single additive panel.

## Candidate dataset and validation

The new candidate is [`kerala_district_monthly_disease_dashboard_2016_2025.csv`](../data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.csv). It contains year, month, period, normalized and original district names, disease, source-native classification/category code, cases, deaths, source identity/URLs, snapshot date, ETag/hash, temporal grain, and explicit category/cases/deaths availability flags.

For unavailable 2016 Suspected cells it records `availability_status=unavailable_source_category_absent`, `source_category_available=false`, and null cases/deaths. It never substitutes zero. `Confirmed` and `Suspected` remain separate. The statewide reconciliation output is not appended to the candidate.

The reproducible builder is [`build_extended_disease_candidate.py`](../src/caregrid/build_extended_disease_candidate.py); source and candidate hashes/row counts are in [`kerala_district_monthly_disease_dashboard_2016_2025.metadata.json`](../data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.metadata.json). Automated tests check the 6,720-row panel, all 120 periods, category missingness versus zero, uniqueness, snapshot/output hashes, source count validation, and exact known reconciliation exceptions.

## Interpretation and limitations

This is 10 years of dashboard-reported district-month counts, not 10 years of proven comparable disease definitions. DHS comparisons and source-definition caveats are in the [source discrepancy analysis](source_discrepancy_analysis.md). The candidate is appropriate for source-native descriptive work and a controlled readiness assessment; cross-year trend or model claims require written case-definition, reporting, and revision history. No synthetic observations, population rates, or harmonized DHS categories were created.
