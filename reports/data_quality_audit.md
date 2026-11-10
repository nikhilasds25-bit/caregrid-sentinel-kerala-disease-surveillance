# Data audit — Kerala districtwise cases/deaths 2020–2024

## What the uploaded Excel files contain

- `Districtwise Disease Cases 2020 to 2024`: annual disease case counts, one worksheet per year.
- `Districtwise Disease Death 2020-2024`: annual disease death counts, one worksheet per year.
- Each year has 14 district columns, including rows for `Dengue Fever: Confirmed`, `Dengue Fever: Probable`, `Leptospirosis : Confirmed`, and `Leptospirosis : Probable`.
- The disease rows and district values are annual totals; these files do **not** supply monthly district-level time series.

## Curated data

- Tidy panel: 280 rows.
- Panel design: 5 years × 14 districts × 2 diseases × 2 source classifications.
- Coverage: 2020–2024, all 14 Kerala districts.
- Metrics: cases and deaths; classification retained as Confirmed / Probable.
- District code `TCR` on the 2023 tabs is normalized to `TSR` for Thrissur; the original labels are preserved in source-label columns.

## Quality issues and cautions

1. The `CD DEATH_2024` worksheet tab is named for 2024, but its title cell reads `Number of Death 2021`. The curated CSV records this title discrepancy in `source_header_note`; the year is assigned from the worksheet tab.
2. The 2021 statewide monthly series labels its disease counts `reported_category_status_not_split`, while the district workbook separately lists Confirmed and Probable. For dengue, the district workbook's confirmed case sum is 3,261 versus 3,251 in the statewide monthly series (a difference of +10). This requires source review.
3. Other 2021 numeric totals and 2022 numeric totals in the monthly series match the district workbook's confirmed-row sums for these two diseases, but numeric agreement does not itself prove identical case-definition semantics. Explicit Confirmed labels align directly in 2023–2024.
4. District counts are not adjusted for district population. Do not label the highest raw counts as highest incidence/risk without population denominators and other context.
5. This dataset can support annual district burden comparisons and early hotspot exploration, but not a district-month weather-lag forecast. We still need month-by-district cases to test climate lead/lag relationships.

## Cross-check summary (district confirmed row vs statewide monthly series)

| Year | Disease | Monthly series cases | District confirmed sum | Difference | Case-label comparability |
|---|---|---:|---:|---:|---|
| 2021 | Dengue | 3,251 | 3,261 | +10 | needs review |
| 2021 | Leptospirosis | 1,745 | 1,745 | +0 | labels differ |
| 2022 | Dengue | 4,468 | 4,468 | +0 | labels differ |
| 2022 | Leptospirosis | 2,482 | 2,482 | +0 | labels differ |
| 2023 | Dengue | 16,766 | 16,766 | +0 | both labelled Confirmed |
| 2023 | Leptospirosis | 2,417 | 2,417 | +0 | both labelled Confirmed |
| 2024 | Dengue | 20,674 | 20,674 | +0 | both labelled Confirmed |
| 2024 | Leptospirosis | 3,552 | 3,552 | +0 | both labelled Confirmed |

## Suggested use

- Use `data/processed/kerala_district_annual_disease_2020_2024.csv` for annual district-level descriptive summaries and maps.
- Keep `reports/statewide_monthly_vs_district_annual_crosscheck_2021_2024.csv` attached to the data pipeline so source differences remain visible.
- Continue seeking monthly district-wise disease data before fitting climate-aware district forecasts.
