# Historical disease classification and comparability audit

**Investigation date:** 2026-11-10
**Scope:** DHS source records for 2023–2025 and the Kerala Health Department disease dashboard snapshot. No DHS and dashboard values were merged.

## Decision

A complete **source-native** 2023–2025 dashboard candidate can be built because one official dashboard endpoint provides all months, districts, and the same category codes for those years, with district sums matching its Kerala totals. This does **not** establish that the categories are epidemiologically identical across years or interchangeable with DHS `Confirmed`/`Probable` records.

The candidate is kept separate from the existing 2021–2024 dataset. Its source labels remain exactly `Confirmed` and `Suspected`; dashboard `Suspected` is not renamed to DHS `Probable`. The candidate is suitable for further source review, not yet approved as a harmonized model-training series.

## Original sources inspected

| Reporting year | Official DHS report and monthly table | Published categories in the inspected target tables | Local source |
|---|---|---|---|
| 2023 | [Kerala Communicable Disease Data 2023](https://dhs.kerala.gov.in/wp-content/uploads/2024/12/Final-IDSP-70-IDSP-STATE_DATA_MANAGER-2024-NHM-pages.pdf), PDF pages 4–5; annual validation on page 2 | Dengue and Leptospirosis `Confirmed` monthly counts | [`kerala_disease_monthly_confirmed_2023.csv`](../data/interim/kerala_disease_monthly_confirmed_2023.csv); original report linked above |
| 2024 | [Kerala Communicable Disease Data 2024](https://dhs.kerala.gov.in/wp-content/uploads/2025/06/IDSP-Annual-Data-2024.pdf), PDF page 17; annual validation on page 2 | Dengue and Leptospirosis `Confirmed` and `Probable` monthly counts | [`IDSP-Annual-Data-2024.pdf`](../data/raw/IDSP-Annual-Data-2024.pdf), [`kerala_disease_monthly_2024.csv`](../data/processed/kerala_disease_monthly_2024.csv) |
| 2025 | [Kerala Communicable Disease Data 2025](https://dhs.kerala.gov.in/wp-content/uploads/2026/09/CD-Data-2025-Approved.pdf), approved-report monthly table on PDF page 16; annual validation on page 2 | Dengue and Leptospirosis `Confirmed` and `Probable` monthly counts | [`DHS-CD-Data-2025-Approved.pdf`](../data/raw/DHS-CD-Data-2025-Approved.pdf), [`latest.json`](../data/live_surveillance/latest.json) |

The additional official source is the [Kerala Health Department disease prevalence dashboard](https://health.kerala.gov.in/static_disease_prevalence), whose page links its public [disease data JSON](https://health.kerala.gov.in/disease_data.json). The captured response is preserved as [`kerala_health_disease_data_2026-11-10.json`](../data/raw/kerala_health_disease_data_2026-11-10.json), with retrieval metadata and SHA-256 in the adjacent `.metadata.json`.

The 2023 PDF was fetched transiently from its official URL, but its text extraction was reversed/garbled and it is not preserved locally. The 2023 source-page references and values below rely on existing project source metadata/transcriptions; they were not independently re-transcribed from a readable PDF in this investigation. The 2023 cross-source comparison is therefore a check against the retained DHS source series, not an independent verification of that transcription.

## Category and measurement comparison

| Source/year | Dashboard source category | DHS monthly category | Definition evidence found in inspected source | Comparability finding |
|---|---|---|---|---|
| 2023 | `DENGUE|Con` / `LEPTO|Con` (`Confirmed`); also dashboard `Suspected` categories | `Confirmed` in the monthly tables | No clinical case definition, laboratory rule, reporting-version note, or revision history was found in the inspected table/report metadata. | Same printed `Confirmed` label and matching totals are supportive but insufficient to certify unchanged case definitions. |
| 2024 | `Confirmed` and `Suspected` | `Confirmed` and `Probable` | No explicit definition or statement equating `Suspected` with `Probable` was found. | Monthly values match by source category pairing, but the unlike labels are not treated as a semantic crosswalk. |
| 2025 | `Confirmed` and `Suspected` | `Confirmed` and `Probable` | No definition or revision note resolving the source differences was found. | There are month-level differences, including within `Confirmed`; cross-source equivalence is not established. |

Both sources publish monthly case and death counts. Dashboard JSON is nested by reporting year and month, with separate `C` and `D` fields corresponding to the dashboard's Cases and Deaths controls. These are monthly counts, not cumulative totals. Dashboard zeroes are retained as source-reported zeroes; absent values are not filled with zero.

The inspected documents and dashboard response do not establish clinical diagnostic criteria, denominator/population basis, source revision policy, reporting cut-off, or unchanged surveillance methodology across years. Do not infer these from matching labels.

## Coverage, uniqueness, and reconciliation

The dashboard snapshot has all 14 districts and all 12 months for each target category in 2023, 2024, and 2025. The candidate builder checks all 36 periods, all four disease/category codes, both metrics, and exact monthly sums from the 14 districts to the dashboard's `KERALA` aggregate. All **288** year-month/category/metric aggregate checks passed. The candidate has 2,016 unique disease-month-district-category rows: 36 months × 14 districts × 2 diseases × 2 dashboard categories. There are no duplicate natural keys or missing target months.

Dashboard district totals were compared with the retained DHS statewide monthly source series:

| Year and comparison | Monthly field comparisons | Mismatching fields | Result |
|---|---:|---:|---|
| 2023 dashboard `Confirmed` vs DHS `Confirmed` | 48 | 0 | All 12 months × 2 diseases × cases/deaths match. |
| 2024 dashboard `Confirmed` vs DHS `Confirmed`; dashboard `Suspected` vs DHS `Probable` (label comparison only) | 96 | 0 | All values match, but the `Suspected`/`Probable` label difference remains unresolved. |
| 2025 dashboard `Confirmed` vs DHS `Confirmed`; dashboard `Suspected` vs DHS `Probable` (label comparison only) | 96 | 30 | Differences occur in 2025; matching annual totals alone would conceal month-level revisions/disagreement. |

For 2025, differences below are dashboard minus DHS:

| Disease / compared source categories | Measure | Months differing | Annual difference |
|---|---|---:|---:|
| Dengue `Confirmed` vs `Confirmed` | Cases | 6 | 0 |
| Dengue `Confirmed` vs `Confirmed` | Deaths | 2 | -2 |
| Leptospirosis `Confirmed` vs `Confirmed` | Cases | 5 | +1 |
| Leptospirosis `Confirmed` vs `Confirmed` | Deaths | 0 | 0 |
| Dengue `Suspected` vs `Probable` | Cases | 6 | +18 |
| Dengue `Suspected` vs `Probable` | Deaths | 2 | +2 |
| Leptospirosis `Suspected` vs `Probable` | Cases | 6 | +7 |
| Leptospirosis `Suspected` vs `Probable` | Deaths | 3 | +1 |

Examples of non-offsetting monthly disagreement include Dengue confirmed deaths in April (dashboard 4, DHS 5) and June (8, 9); Leptospirosis confirmed cases differ in January–April and December. The dashboard 2025 annual Dengue confirmed death total is 70 versus DHS 72; Leptospirosis confirmed cases are 3,486 versus 3,485. The source material inspected does not explain whether these arise from update timing, correction, transcription, or a reporting-method change.

## Candidate dataset and decision on a 36-month series

The separate candidate is [`kerala_district_monthly_disease_dashboard_2023_2025.csv`](../data/candidates/kerala_district_monthly_disease_dashboard_2023_2025.csv). It is rebuilt offline from the raw dashboard snapshot by [`build_district_monthly_candidate.py`](../src/caregrid/build_district_monthly_candidate.py). Each row retains the source district key, dashboard category code, exact category label, cases/deaths metric keys, period, source URL, response date, ETag, retrieval time, and source hash.

The candidate does **not**:

- append records to or replace the original 2021–2024 historical files;
- mix DHS values with dashboard values;
- map dashboard `Suspected` to DHS `Probable`;
- claim that dashboard `Confirmed` definitions are unchanged across years;
- infer counts from annual district totals, or create synthetic observations.

**Answer:** a 36-month, 14-district source-native candidate has been created and structurally validated. A semantically comparable 36-month DHS-confirmed series has **not** been established. Keep the candidate marked provisional until the department clarifies category definitions and the 2025 differences.

## Missing periods and next checks

- The captured dashboard JSON spans 2016–2025. Target categories are complete for 2023–2025; the earlier dashboard response has a different completeness profile (2016 Suspected categories are absent). Historical expansion before 2023 needs its own period-by-period audit.
- No historical 2026 monthly DHS target series was established here. Daily IDSP reports are a different reporting product and are not monthly replacements.
- Request written definitions for dashboard `Confirmed`/`Suspected`, DHS `Confirmed`/`Probable`, reporting cut-offs, correction/version history, and district coding from the responsible department.
- Preserve future snapshots and compare their hashes/ETags before replacing any candidate. Re-run the source and cross-source checks after any refresh.

No forecasting or outbreak model was implemented or trained.
