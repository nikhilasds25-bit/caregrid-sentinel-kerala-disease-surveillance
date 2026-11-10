# Official Kerala district-month disease data research

**Investigation date:** 2026-11-10
**Question:** Are official monthly Dengue and Leptospirosis counts available by Kerala district, and are they reproducible and usable without fabricating records?

## Finding

Yes. The Kerala Health Department's [disease prevalence dashboard](https://health.kerala.gov.in/static_disease_prevalence) links to a public [JSON data endpoint](https://health.kerala.gov.in/disease_data.json). The response contains monthly data by district, disease category, cases, and deaths. This endpoint was reached through the official dashboard, not guessed. A source snapshot was saved locally and its metadata preserved.

The source provides complete 14-district monthly records for the target Dengue and Leptospirosis categories for 2023–2025. This is a material improvement over the previously inspected local annual-district files; those annual files remain unchanged. The new data is **not** merged into them or into the statewide DHS historical series.

## Reproducible source snapshot

| Item | Captured value |
|---|---|
| Dashboard | [https://health.kerala.gov.in/static_disease_prevalence](https://health.kerala.gov.in/static_disease_prevalence) |
| Data URL | [https://health.kerala.gov.in/disease_data.json](https://health.kerala.gov.in/disease_data.json) |
| HTTP response | 200 |
| Server `Date` | `Tue, 10 Nov 2026 10:05:34 GMT` |
| Client retrieval (UTC) | `2026-11-10T10:05:57.0743381+00:00` |
| ETag | `"2096a5-6526c5fad5595"` |
| Size | 2,135,717 bytes |
| SHA-256 | `ca401184db2f983030d3fd26eb94872aa3cc61f6be340067aef1e362bdd2101c` |
| Raw snapshot and metadata | [`data/raw/kerala_health_disease_data_2026-11-10.json`](../data/raw/kerala_health_disease_data_2026-11-10.json), [`metadata`](../data/raw/kerala_health_disease_data_2026-11-10.metadata.json) |

The public response is mutable and has no explicit dataset version or methodology version. The local snapshot, retrieval metadata, and hash therefore form the reproducibility boundary for this candidate; they do not prove that the underlying values are immutable.

## Coverage and shape

The source is nested by year, district, and month. It includes a statewide `KERALA` aggregate and 14 district keys. Target codes are `DENGUE|Con`, `DENGUE|Sus`, `LEPTO|Con`, and `LEPTO|Sus`; each exposes `C` and `D` values. The dashboard controls identify the metrics as Cases and Deaths. Category labels are retained as `Confirmed` and `Suspected`.

| Coverage check | Result |
|---|---|
| Dashboard historical years returned | 2016–2025 |
| 2023–2025 target districts | 14 districts in each year |
| 2023–2025 target months | Jan–Dec for every district, year, disease, and category |
| 2023–2025 dashboard category codes | All four codes present for every target district-month |
| Monthly grain | Year and month are explicit in source hierarchy; totals are monthly, not cumulative |
| Measures | Cases and deaths kept in separate fields |
| District-to-state reconciliation | All 288 monthly category/metric checks passed for 2023–2025 |
| Candidate natural-key duplicates | 0 |
| Candidate missing months | 0 |

The 2023–2025 candidate contains 2,016 rows: 36 periods × 14 districts × 2 diseases × 2 source categories. Statewide totals are used only as validation; the `KERALA` aggregate is not copied into the district-level candidate. Source zeroes remain numeric zeroes; the builder rejects absent/invalid target values rather than silently filling them.

The snapshot also contains historical years before 2023. The inspected response has target-category coverage for 2017–2025, but 2016 Suspected categories are absent. The snapshot ends at 2025; no 2026 monthly values are included. Do not infer absent categories or periods to mean zero. Any pre-2023 expansion needs a separate audit of coverage, classification, source changes, and reporting revisions.

## Cross-source checks and caveats

The dashboard monthly statewide totals match the retained DHS 2023 Confirmed source-series values for all target months and measures. The 2023 PDF's text extraction was not readable enough for independent re-transcription, so this is not a fresh verification of the original table. In 2024, dashboard Confirmed matches DHS Confirmed, and dashboard Suspected values happen to match DHS Probable values. These matching values are not evidence that the differently named categories are definitionally equivalent.

For 2025, there are 30 monthly field disagreements among 96 comparisons of dashboard Confirmed/Suspected against DHS Confirmed/Probable. Dashboard Dengue confirmed deaths total 70 versus DHS 72; dashboard Leptospirosis confirmed cases total 3,486 versus DHS 3,485. See the [classification comparison](historical_classification_comparison.md) for all category-level mismatch counts and net differences. Neither source was silently corrected to match the other.

No clinical case definitions, revision history, publication cut-off, or district reporting rules were found in the inspected dashboard page/JSON schema. These omissions and the 2025 discrepancies prevent a conclusion that 2023–2025 is a fully harmonized disease series.

## District identity, weather, and other official data

- The dashboard-linked district GeoJSON was checked and contains 14 Kerala district features. A boundary-version date and an explicit epidemiological district-code crosswalk were not established. Preserve source district keys and validate boundaries/codes before spatial joins.
- The project has annual district disease workbooks for 2020–2024, but these cannot fill or validate monthly cells. The dashboard candidate does not overwrite these files.
- The dashboard does not supply corresponding district-month weather. Existing Open-Meteo values are model/reanalysis estimates at representative points, not official district stations; see [climate data readiness](climate_data_readiness.md).
- No population denominators were added. Counts must not be interpreted as population-adjusted risk; no population-weighted estimates were generated.
- The daily IDSP pipeline is separate: report-date observations, present-month totals, cumulative totals, suspected/confirmed fields, dashes, and missing reports retain their original semantics. Daily rows are not monthly dashboard observations and were not aggregated into this candidate.

## Validation and files

The candidate can be rebuilt offline with:

```powershell
$env:PYTHONPATH = "src"
python -m caregrid.build_district_monthly_candidate
```

The command verifies the raw snapshot SHA-256, 14 districts, all months, all four category codes, non-negative integer cases/deaths, and exact district-to-Kerala monthly sums. It refuses to overwrite an existing candidate unless `--overwrite` is explicitly supplied. Five tests cover panel completeness, unique natural keys, source reproducibility, aggregate mismatch, missing month, and snapshot integrity.

The source snapshot, metadata, builder, test, and candidate are separate from the original historical datasets, daily IDSP pipeline, and forecasting experiment. No forecasting or outbreak model was run.

## Next research step

Ask Kerala Health Department to confirm the category definitions, district-code convention, publication/revision policy, and 2025 discrepancies. Independently validate the dashboard's district boundary version and obtain population denominators only from a reliable, date-aligned official source if rates or population offsets are later required.
