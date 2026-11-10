# District disease dataset: data-quality audit

- Run timestamp (UTC): 2026-10-24T04:32:22+00:00
- Input: `C:\Users\Nikhil\Desktop\CareGrid-Sentinel\data\processed\kerala_district_annual_disease_2020_2024.csv`
- Source CSV is read-only for this audit; no source values are changed.

## Scope and interpretation

This dataset contains annual district-level records, not monthly district-level observations. It does not support district-month climate-lag forecasting. Confirmed and Probable are preserved as separate source categories. Do not assume their definitions or reporting practices are identical across reporting years.

Known cross-source discrepancy: the 2021 district-wise Dengue Confirmed total was previously found to be 3,261, while the statewide monthly dataset totals 3,251 (difference +10). These values are not reconciled; review the source records and definitions before drawing conclusions.

## Dataset structure

- Shape: **280 rows × 18 columns**
- Column names (source order): `year, district, district_code, disease, classification, cases, deaths, source_case_label, source_death_label, case_source_sheet, death_source_sheet, classification_note, source_header_note, temporal_granularity, case_source_title, case_source_url, death_source_title, death_source_url`
- Years observed: `[2020, 2021, 2022, 2023, 2024]`
- Diseases observed: `['Dengue', 'Leptospirosis']`
- Classifications observed: `['Confirmed', 'Probable']`

## Check results

| Check | Result | Details |
| --- | --- | --- |
| CSV readable; required schema present | PASS | C:\Users\Nikhil\Desktop\CareGrid-Sentinel\data\processed\kerala_district_annual_disease_2020_2024.csv |
| Dataset shape and column names recorded | PASS | 280 rows × 18 columns |
| No missing values | WARN | 224 missing cells |
| No duplicate natural keys | PASS | 0 duplicate-key rows |
| Coverage of years 2020–2024 | PASS | missing=[]; unexpected=[] |
| All 14 districts represented each year | PASS | district counts by year={2020: 14, 2021: 14, 2022: 14, 2023: 14, 2024: 14} |
| Disease coverage | PASS | observed=['Dengue', 'Leptospirosis']; missing=[]; unexpected=[] |
| Classification coverage; categories retained separately | PASS | observed=['Confirmed', 'Probable']; missing=[]; unexpected=[] |
| No missing expected combinations or duplicate keys | PASS | 0 missing combinations; 0 duplicate-key rows |
| No non-numeric case/death values | PASS | cases=0; deaths=0 |
| No negative case/death values | PASS | cases=0; deaths=0 |
| No deaths greater than cases | PASS | 0 records flagged |

A WARN indicates a condition requiring inspection; records are never silently modified.

## Missing values by column

| column | missing_count |
| --- | --- |
| year | 0 |
| district | 0 |
| district_code | 0 |
| disease | 0 |
| classification | 0 |
| cases | 0 |
| deaths | 0 |
| source_case_label | 0 |
| source_death_label | 0 |
| case_source_sheet | 0 |
| death_source_sheet | 0 |
| classification_note | 0 |
| source_header_note | 224 |
| temporal_granularity | 0 |
| case_source_title | 0 |
| case_source_url | 0 |
| death_source_title | 0 |
| death_source_url | 0 |

The 224 blank `source_header_note` cells are sparse optional metadata: an empty value means no header discrepancy was recorded for that source row, not that a disease measurement is absent. The missing-value count is still reported as stored.

## District coverage by year

| year | district_count | missing_districts | unexpected_districts |
| --- | --- | --- | --- |
| 2020 | 14 |  |  |
| 2021 | 14 |  |  |
| 2022 | 14 |  |  |
| 2023 | 14 |  |  |
| 2024 | 14 |  |  |

## Totals by year, disease, and classification

Case/death totals sum parseable numeric values only. `*_numeric_records` and `record_count` make incomplete numeric groups visible; invalid source values remain in the source file and are listed in the record-flags table.

| year | disease | classification | record_count | cases | deaths | cases_numeric_records | deaths_numeric_records |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2020 | Dengue | Confirmed | 14 | 2723 | 22 | 14 | 14 |
| 2020 | Dengue | Probable | 14 | 12042 | 16 | 14 | 14 |
| 2020 | Leptospirosis | Confirmed | 14 | 1039 | 48 | 14 | 14 |
| 2020 | Leptospirosis | Probable | 14 | 1872 | 143 | 14 | 14 |
| 2021 | Dengue | Confirmed | 14 | 3261 | 27 | 14 | 14 |
| 2021 | Dengue | Probable | 14 | 9878 | 4 | 14 | 14 |
| 2021 | Leptospirosis | Confirmed | 14 | 1745 | 97 | 14 | 14 |
| 2021 | Leptospirosis | Probable | 14 | 2565 | 250 | 14 | 14 |
| 2022 | Dengue | Confirmed | 14 | 4468 | 58 | 14 | 14 |
| 2022 | Dengue | Probable | 14 | 13355 | 11 | 14 | 14 |
| 2022 | Leptospirosis | Confirmed | 14 | 2482 | 121 | 14 | 14 |
| 2022 | Leptospirosis | Probable | 14 | 2833 | 169 | 14 | 14 |
| 2023 | Dengue | Confirmed | 14 | 16766 | 153 | 14 | 14 |
| 2023 | Dengue | Probable | 14 | 41599 | 12 | 14 | 14 |
| 2023 | Leptospirosis | Confirmed | 14 | 2417 | 133 | 14 | 14 |
| 2023 | Leptospirosis | Probable | 14 | 2769 | 149 | 14 | 14 |
| 2024 | Dengue | Confirmed | 14 | 20674 | 128 | 14 | 14 |
| 2024 | Dengue | Probable | 14 | 53536 | 13 | 14 | 14 |
| 2024 | Leptospirosis | Confirmed | 14 | 3552 | 251 | 14 | 14 |
| 2024 | Leptospirosis | Probable | 14 | 2428 | 143 | 14 | 14 |

## Record-level flags

Flagged records: **0**. Deaths exceeding cases are review flags, not corrections.

See `district_data_quality_record_flags.csv` for the complete flagged-record table.

## Source metadata and header discrepancies

- Case source: `Districtwise Disease Cases 2020 to 2024` — https://health.kerala.gov.in/department-data
- Death source: `Districtwise Disease Death 2020-2024` — https://health.kerala.gov.in/department-data

Header notes recorded in the dataset:

- 2024: `CD DEATH_2024` — Source sheet is CD DEATH_2024, but the title cell incorrectly reads 'Number of Death 2021'; year assigned from sheet name.

Classification/source notes:

- Source labels preserved as confirmed/probable; definitions and reporting practices should be checked across years before time-trend modelling.

Full row-level source metadata is saved in `district_data_quality_source_metadata.csv`.

## Derived tables

- `district_data_quality_missing_values.csv`
- `district_data_quality_district_year_coverage.csv`
- `district_data_quality_missing_expected_combinations.csv`
- `district_data_quality_totals_by_year_disease_classification.csv`
- `district_data_quality_record_flags.csv`
- `district_data_quality_source_metadata.csv`

Missing expected combinations are defined over 2020–2024 × the 14 named Kerala districts × Dengue/Leptospirosis × Confirmed/Probable.
