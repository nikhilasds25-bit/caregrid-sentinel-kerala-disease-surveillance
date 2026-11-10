# Historical monthly disease sources — CareGrid Sentinel

This starter dataset transcribes two monthly rows (dengue and leptospirosis, cases and deaths) for 2021–2022 from official DHS Kerala reports and combines them with the previously validated 2023–2024 series.

## Official sources

- **2021:** [Data on Communicable Disease - Kerala, January to December 2021](https://dhs.kerala.gov.in/wp-content/uploads/2022/02/DATA-ON-COMMUNICABLE-DISEASE-2021.pdf). Monthly dengue table: PDF page 2; monthly leptospirosis table: PDF page 3. Statewide annual totals: dengue 3,251 cases / 27 deaths; leptospirosis 1,745 cases / 97 deaths.
- **2022:** [Kerala — Communicable Disease Data for 2022](https://dhs.kerala.gov.in/wp-content/uploads/2023/07/CD-Data-2022_Signed.pdf). Monthly dengue table: PDF page 3; monthly leptospirosis table: PDF page 4. Annual summary on PDF page 2 separately lists probable dengue (13,355/11) and probable leptospirosis (2,833/169); the monthly tables' dengue and lepto totals (4,468/58 and 2,482/121) match the non-probable categories.
- **2023:** [Kerala — Communicable Disease Data for 2023](https://dhs.kerala.gov.in/wp-content/uploads/2024/12/Final-IDSP-70-IDSP-STATE_DATA_MANAGER-2024-NHM-pages.pdf). Monthly tables and annual summary label confirmed dengue and confirmed leptospirosis separately.
- **2024:** [Kerala — Communicable Disease Data for 2024](https://dhs.kerala.gov.in/wp-content/uploads/2025/06/IDSP-Annual-Data-2024.pdf). Monthly tables on PDF page 17, annual summary on page 2.

## Classification caveat — important

The source terminology is not identical across all four years. The 2021 statewide monthly/annual tables do not separately publish probable rows for dengue or leptospirosis. The 2022 annual summary does separately report probable categories, but the monthly table header does not use the word "confirmed" for the other categories. In 2023 and 2024, the source explicitly labels those series as "Confirmed". The CSV keeps a `classification` and `classification_note` field to preserve this distinction. Do not overwrite these fields or claim perfect diagnostic-definition equivalence without further auditing the source methodology.

## Validation

`combine_statewide_history.py` expects 12 monthly observations per year per disease and checks case/death sums against the official annual totals (8 checks, two diseases x four years). These checks test transcription consistency only; they do not validate a prediction model.

## Project limitation

The compiled records are statewide monthly totals, not district-by-month records. There are 48 monthly observations per disease across 2021–2024, which is still short for robust time-series forecasting. The next priority is to obtain multi-year district-month data from the [Kerala Health district-wise disease dashboard](https://health.kerala.gov.in/static_disease_prevalence), then join weather data at a geographically appropriate scale.

### Source-status addendum — 2026-11-10

A follow-up investigation verified that the official dashboard links a public JSON endpoint with monthly district-level Dengue and Leptospirosis records. A separate 2023–2025 source-native candidate and hash-bound source snapshot are documented in [`reports/district_monthly_data_research.md`](../../reports/district_monthly_data_research.md). This candidate does not modify or extend the statewide files above; dashboard `Suspected` remains distinct from DHS `Probable`, and the 2025 source differences remain unresolved. The earlier project limitation records the state before that follow-up.
