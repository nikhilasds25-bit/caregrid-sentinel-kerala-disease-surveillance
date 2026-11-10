# DHS and Kerala dashboard source discrepancy analysis

**Analysis date:** 2026-11-10
**Scope:** Monthly statewide comparisons where local DHS monthly records exist, and annual district comparisons where DHS district-year data exist. Sources remain separate; no values are overwritten, reconciled, or category-recoded.

## Interpretation rules

The dashboard categories are `Confirmed` and `Suspected`; DHS monthly and annual reports use `Confirmed` and `Probable` in some years. Numerical comparisons of `Suspected` to `Probable` are shown only as comparisons, not as evidence that the categories are equivalent. Dashboard `Confirmed` versus an unsplit or “non-probable” DHS category is likewise not asserted to be definitionally identical.

The monthly comparison is reproducible in [`dhs_dashboard_monthly_comparison_2021_2025.csv`](../data/candidates/dhs_dashboard_monthly_comparison_2021_2025.csv). The district annual comparison is in [`dhs_dashboard_district_annual_comparison_2020_2025.csv`](../data/candidates/dhs_dashboard_district_annual_comparison_2020_2025.csv). Both retain source classes, source counts, and dashboard-minus-DHS differences.

## Monthly statewide comparison

| Year | Monthly fields compared | Numeric mismatches | Notes |
|---:|---:|---:|---|
| 2021 | 48 | 0 | Dashboard Confirmed compared numerically with the DHS `reported_category_status_not_split` series. Not a confirmed-definition equivalence. |
| 2022 | 48 | 0 | Dashboard Confirmed compared numerically with the DHS `non_probable_category_probable_separate` series. The DHS monthly table does not explicitly name it Confirmed. No month-level DHS probable counterpart was available in the local dataset. |
| 2023 | 48 | 0 | Dashboard Confirmed matches the retained DHS Confirmed transcription for both diseases, cases and deaths. Dashboard Suspected has no local DHS monthly counterpart. |
| 2024 | 96 | 0 | Dashboard Confirmed matches DHS Confirmed; dashboard Suspected numerically matches DHS Probable, but no category crosswalk is established. |
| 2025 | 96 | 30 metric fields across 25 monthly disease/category rows | Dashboard/DHS differences are listed below. Suspected-to-Probable remains a numerical-only comparison. |

For 2023, the source report is [DHS Communicable Disease Data 2023](https://dhs.kerala.gov.in/wp-content/uploads/2024/12/Final-IDSP-70-IDSP-STATE_DATA_MANAGER-2024-NHM-pages.pdf), referenced as PDF pages 4–5 for monthly tables. The PDF was fetched transiently in the earlier investigation, but extracted text was reversed/garbled; it is not preserved locally and was not independently re-transcribed here. Therefore, 2023 agreement is with the retained [DHS monthly transcription](../data/interim/kerala_disease_monthly_confirmed_2023.csv), not an independent fresh verification of the original PDF table.

### 2025 monthly differences

All differences are **dashboard minus DHS**. Cases and deaths are kept separate.

| Disease | Dashboard category compared to DHS | Measure | Differing months | Net difference |
|---|---|---|---:|---:|
| Dengue | Confirmed vs Confirmed | Cases | 6 | 0 |
| Dengue | Confirmed vs Confirmed | Deaths | 2 | -2 |
| Dengue | Suspected vs Probable | Cases | 6 | +18 |
| Dengue | Suspected vs Probable | Deaths | 2 | +2 |
| Leptospirosis | Confirmed vs Confirmed | Cases | 5 | +1 |
| Leptospirosis | Confirmed vs Confirmed | Deaths | 0 | 0 |
| Leptospirosis | Suspected vs Probable | Cases | 6 | +7 |
| Leptospirosis | Suspected vs Probable | Deaths | 3 | +1 |

Specific differing monthly values:

- **Dengue Confirmed cases:** April 379 vs 380 (-1); June 2,104 vs 2,106 (-2); July 1,785 vs 1,784 (+1); September 703 vs 704 (-1); November 646 vs 645 (+1); December 635 vs 633 (+2).
- **Dengue Confirmed deaths:** April 4 vs 5 (-1); June 8 vs 9 (-1). Annual totals are 70 dashboard vs 72 DHS.
- **Dengue Suspected cases vs DHS Probable:** June 6,705 vs 6,703 (+2); July 4,371 vs 4,368 (+3); August 2,436 vs 2,437 (-1); October 1,525 vs 1,523 (+2); November 1,443 vs 1,435 (+8); December 1,379 vs 1,375 (+4).
- **Dengue Suspected deaths vs DHS Probable:** April 1 vs 0 (+1); June 1 vs 0 (+1).
- **Leptospirosis Confirmed cases:** January 230 vs 231 (-1); February 130 vs 129 (+1); March 134 vs 133 (+1); April 142 vs 143 (-1); December 267 vs 266 (+1). Annual totals are 3,486 dashboard vs 3,485 DHS.
- **Leptospirosis Suspected cases vs DHS Probable:** January 105 vs 104 (+1); March 91 vs 90 (+1); May 115 vs 114 (+1); July 275 vs 277 (-2); November 211 vs 208 (+3); December 193 vs 190 (+3).
- **Leptospirosis Suspected deaths vs DHS Probable:** January 9 vs 8 (+1); August 21 vs 22 (-1); November 14 vs 13 (+1).

Equal annual totals can conceal month-level disagreement (for example Dengue Confirmed cases). The available source records do not explain whether these differences reflect update timing, correction, transcription, or methodological change.

## DHS annual district comparisons

Dashboard monthly counts were summed by district, disease, and dashboard category, then compared with the separate DHS district annual records. The 2025 DHS annual district report has 13 districts; **Alappuzha is absent** and was not imputed. Across common districts:

| Year | District/category records compared | Missing DHS district/category records | Differing case/death fields | Net case difference | Net death difference |
|---:|---:|---:|---:|---:|---:|
| 2020 | 56 | 0 | 0 | 0 | 0 |
| 2021 | 56 | 0 | 1 | -10 | 0 |
| 2022 | 56 | 0 | 3 | +35 | 0 |
| 2023 | 56 | 0 | 0 | 0 | 0 |
| 2024 | 56 | 0 | 0 | 0 | 0 |
| 2025 | 52 | 4 | 19 | +26 | +1 |

The 2021 mismatch is Dengue dashboard Confirmed vs DHS Confirmed in Ernakulam: 945 dashboard monthly cases vs 955 DHS annual cases; deaths match at 6. The 2022 differences are dashboard Suspected vs DHS Probable Dengue in Ernakulam (5,411 vs 5,401) and Kottayam (256 vs 246), plus Leptospirosis dashboard Confirmed vs DHS Confirmed in Ernakulam (273 vs 258); deaths match in each.

In 2025 the 52 comparisons cover 13 common districts × two diseases × two categories; 12 district/disease/category rows have at least one differing measure. The separate annual source also lacks four Alappuzha district/category counterparts. This is distinct from the statewide monthly comparison and must not be used to fill the missing annual district page.

The exact row-level differences and source labels are in the linked CSV. District-year totals and statewide monthly totals are not interchangeable.

## Dashboard internal district/state discrepancies

Separately, four dashboard monthly **case** totals do not reconcile between its 14 district rows and its own `KERALA` row; all available dashboard monthly death totals agree. The exceptions are 2016 May Dengue Confirmed (+20 district sum), 2017 July Leptospirosis Suspected (-14), 2022 October Dengue Suspected (+20), and 2022 October Leptospirosis Confirmed (+15). See the [reconciliation output](../data/candidates/kerala_district_monthly_disease_dashboard_2016_2025_reconciliation.csv). These are not DHS discrepancies and are not corrected.

## Source comparability and next steps

- **2016–2020:** No local DHS monthly series was found for direct month-by-month comparison. The dashboard source itself is available; local DHS annual district data begin in 2020.
- **2021–2022:** DHS and dashboard numeric totals agree at the statewide monthly level for the available categories, but their labels/source categories are not a proven clinical crosswalk. DHS 2022 probable counts are not represented in the local DHS monthly dataset.
- **2023:** The retained monthly transcription agrees, with the original PDF extraction limitation noted above.
- **2024:** Numeric agreement includes unlike Suspected/Probable labels; do not equate them without official documentation.
- **2025:** Multiple monthly/statewide and district annual differences remain unresolved. Do not select either source as corrected truth without an official revision/cut-off explanation.

Request the dashboard and DHS case definitions, classification crosswalk, district code rules, publication cut-offs, correction/revision history, and explanation of the 2025 discrepancies. Continue preserving versioned source snapshots; do not silently harmonize or replace records.
