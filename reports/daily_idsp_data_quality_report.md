# Kerala DHS Daily IDSP Surveillance Data Quality Report

## Result

The official Kerala Directorate of Health Services (DHS) IDSP index was accessed and the latest report available at retrieval was successfully downloaded and validated.

| Item | Verified value |
|---|---|
| Report date printed in PDF | 2026-11-01 |
| DHS post publication timestamp | 2026-11-02T05:15:09+00:00 |
| Latest successful retrieval timestamp | 2026-11-02T12:52:34+00:00 |
| Source index | https://dhs.kerala.gov.in/en/idsp-2/ |
| Report post | https://dhs.kerala.gov.in/en/2026/11/02/01-11-2026/ |
| Original PDF | https://dhs.kerala.gov.in/wp-content/uploads/2026/11/DR-CD-01.11.2026sd.pdf |
| Preserved file | `data/raw/idsp_daily/DR-CD-01.11.2026sd.pdf` |
| SHA-256 | `1eaa3f8501cc8676fc566844fe99ce1a1cc431c788dc90e62ab012e91cf835b3` |
| Parser / dataset version | parser 3 / `idsp-v3-1eaa3f8501cc8676` |
| Validation | Passed |

The report page links an actual PDF attachment; the attachment URL was extracted from that page. It was not guessed. The post publication timestamp is read from the official page's published `<time>` metadata; it is distinct from the report date and PDF server modification time. The district-wise daily format is embedded on page 2 of this same three-page PDF; it is not a separate linked district report.

## Source-reported statistics

The final page presents distinct Daily, Present Month, and Cumulative 2026 columns. The following figures are copied from the **Cumulative 2026** column for the report dated 1 November 2026. They are source-reported running totals, not daily counts.

| Disease | Suspected cases | Suspected deaths | Confirmed cases | Confirmed deaths |
|---|---:|---:|---:|---:|
| Dengue Fever | 35,419 | 35 | 13,244 | 44 |
| Leptospirosis | 1,455 | 92 | 2,465 | 123 |

The corresponding daily values on 1 November were 105 suspected / 80 confirmed dengue cases and 4 suspected / 10 confirmed leptospirosis cases. The report shows dashes in the corresponding daily death cells. Present-month counts are source-reported independently; the importer does not add daily or cumulative values across reports.

The statewide table contains 26 disease/subtype rows, including separate Malaria subtypes. Page 2 contains daily district reporting for all 14 official district codes: TVM, KLM, PTA, IDK, KTM, ALP, EKM, TSR, PKD, MPM, KKD, WYD, KNR, and KSD. Its 294 extracted metric rows retain the district codes and names. Dengue and leptospirosis suspected/confirmed district sums match the page's aggregate row for this report date. The district death measure is presented as a single unclassified field and is not assigned to suspected or confirmed cases.

## Retrieval and processing

Run the importer from the repository root using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_idsp_daily.py
```

The importer:

1. Requests the official DHS IDSP index using a bounded response size and request timeouts.
2. Finds dated report posts in the page itself and tries the newest entries first, up to eight candidates.
3. Extracts each report PDF link from the corresponding official post and rejects non-HTTPS/non-Kerala-government hosts.
4. Verifies the PDF content type/signature, report date, DHS identity, expected report structure and source's preliminary-data note.
5. Saves the original PDF under `data/raw/idsp_daily/`, hashes the exact bytes and records retrieval/HTTP metadata. A downloaded PDF is preserved even if parsing fails.
6. Keeps daily, present-month and cumulative values in separate fields; validates all 14 district codes and reconciles selected district totals without rewriting source counts.
7. Archives a versioned JSON snapshot and atomically updates the latest snapshot/status. If download or validation fails, the last successful snapshot remains in place and the failed attempt is recorded.

The current raw file response had HTTP `Date: Mon, 02 Nov 2026 11:55:16 GMT` and `Last-Modified: Mon, 02 Nov 2026 05:14:47 GMT`. The post is dated 2 November; the reporting date is the 1 November date printed in the PDF. Retrieval time is client UTC time, not a DHS publication timestamp.

## Validation and conventions

- The PDF contains three pages and the printed report date matches the official dated post.
- The statewide table yielded 26 nonduplicate disease/subtype keys. The district table yielded 294 rows and the expected 14 district codes.
- Disease names/subtypes and source labels are preserved; suspected and confirmed values remain separate.
- Daily, Present Month, and Cumulative 2026 values are separate metrics. Cumulative totals are never summed across dates.
- A printed hyphen (`-`) is retained verbatim with numeric `null` and status `source_dash_uninterpreted`; the PDF provides no legend defining its meaning. Blank cells are `not_reported` with numeric `null`. Only an explicitly printed `0` is numeric zero.
- Selected dengue and leptospirosis district case totals reconcile with the report's district-table aggregate row. No district annual or historical data is used as a replacement.
- Import validation rejects invalid reporting dates, duplicate natural keys, unexpected source URLs, malformed counts, unsupported district mappings, and incompatible snapshot versions.
- Daily freshness is labeled **Verified and recent** through two calendar days, **Official but delayed** for 3–7 days, and **Historical** after 7 days. These are application display thresholds for the daily reporting series, not DHS guarantees about publication schedules. A failed refresh is separately labeled source unavailable while the last valid snapshot is retained.

## 2026 historical backfill

The fetched DHS index page exposed 100 actual dated 2026 report posts, spanning 25 July through 1 November 2026. **97 distinct dates** were downloaded, parsed, validated, and imported as parser-version-3 snapshots. All 97 contain a valid daily district table for the 14 official districts. Every successfully imported snapshot records the source PDF URL, publication metadata when present, retrieval time, source SHA-256, parser version, report date, and validation status.

The three discovered reports below were downloaded and preserved with their source URLs, retrieval timestamps, original PDF file paths, and SHA-256 hashes in `data/live_surveillance/daily_idsp/backfill_2026_status.json`, but remain unimported because all three pages are image-only and contain no extractable text/tables. No OCR engine is installed or used, so no counts are inferred from these images:

| Report date | Preserved file | SHA-256 |
|---|---|---|
| 2026-08-30 | `data/raw/idsp_daily/IDSP-Daily-Report-30.08.2026.pdf` | `71fb17ba802be6266050fc2b24f7afbe7a5db265f0a74a63b69e0feb7ceb3446` |
| 2026-10-27 | `data/raw/idsp_daily/IDSP-Daily-Report-27.10.2026-1.pdf` | `b9df0c8dacfed78bddd2765a594705808e695f8ad9fbd0b9333a506cb033ea74` |
| 2026-10-29 | `data/raw/idsp_daily/IDSP-Daily-Report-29.10.2026.pdf` | `d2f20ea74954375168519cb281ddc289d001fd3fb1450f2281463124bda5fbf8` |

The captured index page did not list 205 calendar dates from 1 January through 31 October 2026. These are **not confirmed unpublished dates**; absence from the fetched page is not evidence that a report does not exist. The manifest contains the date list and explicitly separates it from the three discovered-but-unparseable reports. The original PDFs for all 100 discovered posts are preserved under `data/raw/idsp_daily/`.

The importer accepts the actual observed date-header formats (`dd-mm-yy`, `dd-mm-yyyy`, `dd/mm-yy`, `dd/mm/yyyy`) while requiring the parsed table date to equal the date of the official dated post. A parser-version update was made for this behavior and for the previously omitted 31-column district table layout. Re-running `--backfill-2026` skips validated same-version report dates; it does not add or fabricate missing observations.

The historical daily series includes only successfully validated report dates. It identifies report-date gaps; a gap is absent reporting, not a zero-case report. Daily, 7-day, and 30-day summaries use daily metrics only (never cumulative totals) and are withheld for a metric unless both equivalent comparison windows contain every expected report date and a numeric value for that metric. Source dashes and blank cells make the relevant metric window incomplete. All source counts are provisional.

## Provisional status and limitations

The PDF itself states that the report is preliminary and values are liable to change after laboratory tests and death audits. The monitor repeats this warning. The report is an official observation snapshot, not an always-on live feed; retrieval runs only when the importer is invoked. One report date cannot establish an increase, trend, outbreak, or cause. Three image-only reports remain unavailable for structured analysis, and dates not listed by the captured index remain unknown rather than confirmed missing publications.

District values are absolute reported counts, not population-adjusted rates or risk scores. The report's single district death field has no suspected/confirmed split. The importer currently publishes district rows only when the embedded district table is present and validates; otherwise statewide data can be retained while district data are marked unavailable. No older annual district values are substituted.

The 2025 DHS annual report and the 2021–2024 historical datasets remain separate from this 2026 daily source. Their classifications, reporting periods, and units are not merged. The separate hospital simulator continues to accept hypothetical inputs only. No verified official hospital bed occupancy, ICU occupancy, available-bed, oxygen-capacity, or hospital-wise patient-load feed was identified in the DHS pages inspected or connected to this application.

The Health Department `department-data` page could not be loaded in the browser during this work (`ERR_FAILED`); no conclusions about a data feed on that page are made here.
