# Live Kerala Health Monitor — source and data-quality record

## Status at investigation

The monitor has a validated snapshot from the Kerala Directorate of Health Services (DHS), titled **Kerala - Communicable Disease Data for 2025**. It covers January–December 2025. It is the latest official DHS report linked by the DHS communicable-disease index during this investigation, but it is **not live surveillance and does not provide current 2026 figures**.

The report's formal publication date is not stated in the PDF or the listing page. The PDF server returned an HTTP `Last-Modified` date of 2026-09-23; the embedded PDF metadata gives a July 2026 modification timestamp. These are file metadata, not a confirmed publication date. The current snapshot was retrieved from the exact DHS PDF URL at 2026-11-02 11:16:58 UTC (client timestamp); the server's HTTP `Date` header was 2026-11-02 11:16:56 GMT. The earlier saved copy's original retrieval time was not preserved.

## Verified sources and access

| Source | URL | Investigation result |
|---|---|---|
| Kerala Health Department — static disease prevalence | https://health.kerala.gov.in/static_disease_prevalence | Page did not load reliably from this environment; no API endpoint was assumed. |
| Kerala Health Department — Department Data | https://health.kerala.gov.in/department-data | Page did not load reliably from this environment; no live feed was assumed. |
| Kerala DHS — communicable-disease reports | https://dhs.kerala.gov.in/en/data-on-communicable-diseases/ | Official report index inspected; it linked the approved 2025 PDF. The index intermittently returned HTTP 500. |
| Kerala DHS — approved 2025 report | https://dhs.kerala.gov.in/wp-content/uploads/2026/09/CD-Data-2025-Approved.pdf | Direct PDF retrieval succeeded. The original 17-page PDF is preserved in `data/raw/DHS-CD-Data-2025-Approved.pdf`. |

No public API or structured CSV/Excel download was identified for the DHS report. The integration therefore imports only the exact, verified DHS PDF URL or a locally saved copy of that same official report. It does not silently switch to another source.

## Imported observations

- Reporting coverage: 2025-01 through 2025-12.
- DHS monthly statewide table: 27 source disease/category series, 12 months each (324 records).
- DHS annual statewide table: 32 rows, including separate fever outpatient and inpatient measures.
- DHS annual district tables: 416 rows for 13 named districts. **Alappuzha is absent** and is not imputed or displayed as zero.
- Monthly confirmed/probable categories are kept separate. Categories not split by the source remain labelled “Not split by source.”
- Monthly categories explicitly prefixed “Con” remain `Confirmed`; “Prob” remains `Probable`; the source label “Sus Rabies” remains `Suspected`. Where the annual table does not split a category, annual and monthly labels are kept distinct.
- Fever outpatient visits, inpatient admissions and their source-reported deaths are retained as separate metrics, not combined with communicable-disease case counts.
- Latest monthly cards compare December 2025 with November 2025 for the same disease/category. A percentage change is omitted when the previous count is zero or no valid comparator exists.

The latest monthly values shown by the monitor are:

| Disease | Classification | December 2025 cases / deaths | November 2025 cases / deaths |
|---|---|---:|---:|
| Dengue | Confirmed | 633 / 8 | 645 / 10 |
| Dengue | Probable | 1,375 / 0 | 1,435 / 1 |
| Leptospirosis | Confirmed | 266 / 20 | 379 / 24 |
| Leptospirosis | Probable | 190 / 17 | 208 / 13 |

### Selected statewide annual totals

| Disease | Source classification | Cases | Deaths |
|---|---|---:|---:|
| Dengue | Confirmed | 10,909 | 72 |
| Dengue | Probable | 29,060 | 6 |
| Leptospirosis | Confirmed | 3,485 | 237 |
| Leptospirosis | Probable | 2,151 | 161 |

These are official-report counts, not incidence rates, forecasts, diagnoses, or outbreak findings.

## Validation performed

The importer checks the official PDF signature, expected report title and issuing authority, 17-page layout, 2025 reporting period, expected table structures, numeric non-negative whole-number counts, source disease labels, month order, district mapping, duplicate natural keys, source hash, and snapshot schema. It also flags a record when reported deaths exceed cases; none of the 772 imported monthly/statewide/district rows met that condition.

All 27 monthly statewide series have exactly 12 ordered months. Monthly totals reconcile with the annual tables using exact source classifications where they agree; where a monthly category corresponds to a single annual row with no classification split, values are checked while retaining both labels; where monthly/annual categories differ, only the disease subtotal is checked and the categories remain separate. Snapshot validation rejects missing values, invalid reporting periods, duplicate records, and unknown districts.

The district sums do **not** fully reconcile to DHS statewide annual totals. Differences are retained and exposed by the source-status API; they are not corrected or used to infer missing district values. Examples (13 district subtotal minus statewide annual total):

| Disease | Classification | Case difference | Death difference |
|---|---|---:|---:|
| Dengue | Confirmed | −299 | 0 |
| Dengue | Probable | −938 | 0 |
| Leptospirosis | Confirmed | −159 | −10 |
| Leptospirosis | Probable | −111 | −2 |

Other source disease/category subtotals also differ. Some district pages may be absent or the official tables may use differing coverage/definitions. District counts are sorted by absolute reported count only; there are no population denominators, and the dashboard does not label districts as high-risk.

## Freshness and interpretation

- **Verified and recent:** reserved for a verified report whose reporting-period end is at most 90 days old.
- **Official but delayed:** report-period end is more than 90 days but no more than 24 months old.
- **Historical:** report-period end is more than 24 months old.
- **Source unavailable:** last retrieval attempt failed; a previously validated snapshot remains available if one exists.
- **Data not available:** no valid official snapshot is present.

The DHS source is an annual report with monthly tables, not a daily feed. The monitor always states that current 2026 surveillance is unavailable. An increase/decrease is described only as a change in reported counts versus the previous comparable month; it is not evidence of an outbreak or a causal relationship.

Historical CareGrid data remain separate: statewide monthly historical disease records end in December 2024; district historical disease records are annual through 2024; historical weather is a 14-location equal-weight proxy. The DHS 2025 tables are not merged into those historical data or assigned district-month values. The unresolved 2021 dengue discrepancy remains documented in the historical data-quality report.

## Reproducible import and API

From the project root, fetch only the verified DHS PDF and validate/import it:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_official_surveillance_report.py --download
```

For an already downloaded PDF, use the manual workflow and include its HTTP `Last-Modified` value when known:

```powershell
.\.venv\Scripts\python.exe .\src\caregrid\import_official_surveillance_report.py --pdf .\data\raw\DHS-CD-Data-2025-Approved.pdf --last-modified "Wed, 23 Sep 2026 13:51:49 GMT"
```

Raw source PDFs are preserved. The dataset version includes the source hash and importer version; every successful retrieval/import creates a separately timestamped immutable snapshot, and the latest pointer is written atomically. Failed refreshes record the error and retain the previous validated snapshot. For a manually imported local PDF, the recorded timestamp is the local import time because the original network-retrieval timestamp is not available; the HTTP `Last-Modified` and `Date` values are recorded separately when supplied by the source response.

The read-only API is namespaced separately from historical endpoints:

- `GET /api/live-surveillance/summary`
- `GET /api/live-surveillance/diseases`
- `GET /api/live-surveillance/districts`
- `GET /api/live-surveillance/trends`
- `GET /api/live-surveillance/source-status`
- `GET /api/live-surveillance/last-update`
- `GET /api/live-surveillance/source`
