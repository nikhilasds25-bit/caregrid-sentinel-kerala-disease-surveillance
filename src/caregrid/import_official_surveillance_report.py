"""Import the verified DHS 2025 PDF without replacing prior report snapshots."""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pdfplumber
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from caregrid.surveillance import (
    EXPECTED_DISTRICTS,
    LIVE_DIR,
    PARSER_VERSION,
    ROOT,
    SOURCE_ID,
    SOURCE_INDEX_URL,
    SOURCE_NAME,
    SOURCE_PDF_URL,
    SurveillanceUnavailable,
    find_suspicious_value_flags,
    record_refresh_failure,
    record_refresh_success,
    sha256_bytes,
    validate_snapshot,
)

IMPORTER_VERSION = PARSER_VERSION
MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
DISTRICT_SOURCE_NAMES = {
    "TRIVANDRUM": "Thiruvananthapuram",
    "KOLLAM": "Kollam",
    "PATHANAMTHITTA": "Pathanamthitta",
    "ALAPPUZHA": "Alappuzha",
    "KOTTAYAM": "Kottayam",
    "IDUKKI": "Idukki",
    "ERNAKULAM": "Ernakulam",
    "TRISSUR": "Thrissur",
    "THRISSUR": "Thrissur",
    "PALAKKAD": "Palakkad",
    "MALAPPURAM": "Malappuram",
    "KOZHIKKODE": "Kozhikode",
    "WAYANAD": "Wayanad",
    "KANNUR": "Kannur",
    "KASARAGODE": "Kasaragod",
}
MONTHLY_GROUPS = {
    (16, 16): [
        ("Chikungunya", "Confirmed", "Con: CG", "reported cases"),
        ("Dengue", "Probable", "Prob Dengue", "reported cases"),
        ("Dengue", "Confirmed", "Con Dengue", "reported cases"),
        ("Leptospirosis", "Probable", "Prob Lepto", "reported cases"),
        ("Leptospirosis", "Confirmed", "Con Lepto", "reported cases"),
        ("Malaria", "Not split by source", "Malaria", "reported cases"),
        ("Acute Encephalitis Syndrome", "Not split by source", "AES", "reported cases"),
        ("Japanese Encephalitis", "Not split by source", "JE", "reported cases"),
    ],
    (16, 14): [
        ("Hepatitis A", "Probable", "Prob-Hep A", "reported cases"),
        ("Hepatitis A", "Confirmed", "Con-Hep A", "reported cases"),
        ("Hepatitis E", "Not split by source", "HepE", "reported cases"),
        ("Cholera", "Not split by source", "Cholera", "reported cases"),
        ("Typhoid", "Not split by source", "Typhoid", "reported cases"),
        ("Diphtheria", "Not split by source", "Diphtheria", "reported cases"),
        ("Acute Diarrheal Disease", "Not split by source", "ADD", "reported cases"),
    ],
    (17, 14): [
        ("Fever (Undifferentiated) OP", "Not split by source", "Fever OP", "outpatient visits"),
        ("Chicken Pox", "Not split by source", "Chicken Pox", "reported cases"),
        ("Rabies", "Confirmed", "Con Rabies", "reported cases"),
        ("Rabies", "Suspected", "Sus Rabies", "reported cases"),
        ("Food Poisoning", "Not split by source", "Food Poisoning", "reported cases"),
        ("Scrub Typhus", "Confirmed", "Con Scrub Typhus", "reported cases"),
        ("Influenza", "Not split by source", "Influenza", "reported cases"),
    ],
    (17, 10): [
        ("Shigella", "Confirmed", "Con Shigella", "reported cases"),
        ("West Nile", "Confirmed", "Con West Nile", "reported cases"),
        ("Mpox", "Confirmed", "Con M Pox", "reported cases"),
        ("Nipah", "Confirmed", "Con Nipah", "reported cases"),
        ("Amoebic Meningoencephalitis", "Confirmed",
         "Con Amoebic Meningoencephalitis", "reported cases"),
    ],
}
ANNUAL_DISEASES = {
    "Dengue Fever": "Dengue",
    "Malaria": "Malaria",
    "Chikungunya": "Chikungunya",
    "AES": "Acute Encephalitis Syndrome",
    "Acute Encephalitis Syndrome": "Acute Encephalitis Syndrome",
    "Japanese Encephalitis (JE)": "Japanese Encephalitis",
    "Leptospirosis": "Leptospirosis",
    "Hepatitis - A": "Hepatitis A",
    "Hepatitis - E": "Hepatitis E",
    "Cholera": "Cholera",
    "Diphtheria": "Diphtheria",
    "Typhoid": "Typhoid",
    "Acute Diarrheal Disease": "Acute Diarrheal Disease",
    "Food Poisoning": "Food Poisoning",
    "Shigella": "Shigella",
    "Scrub Typhus": "Scrub Typhus",
    "Kala Azar": "Kala Azar",
    "Kysanur Forest Disease": "Kysanur Forest Disease",
    "Influenza (H1N1, H3N2, Infl A, Infl B)": "Influenza",
    "Rabies": "Rabies",
    "Zika": "Zika",
    "West Nile": "West Nile",
    "Prob West Nile": "West Nile",
    "M Pox": "Mpox",
    "Nipah": "Nipah",
    "Amoebic Meningo Encephalitis": "Amoebic Meningoencephalitis",
    "Chicken Pox": "Chicken Pox",
}


class ReportImportError(ValueError):
    """Official source download or report validation failed."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _source_disease_and_classification(label: str) -> tuple[str, str, str]:
    cleaned = _clean(label)
    if ":" in cleaned:
        disease_text, category_text = (part.strip() for part in cleaned.split(":", 1))
    else:
        disease_text, category_text = cleaned, ""
    if disease_text not in ANNUAL_DISEASES:
        raise ReportImportError(f"Unexpected disease label in the official report: {cleaned!r}.")
    disease = ANNUAL_DISEASES[disease_text]
    normalized_category = category_text.casefold()
    if normalized_category in {"confirmed", "probable"}:
        classification = normalized_category.title()
    elif disease_text == "Prob West Nile":
        classification = "Probable"
    else:
        classification = "Not split by source"
    return disease, classification, cleaned


def _table_count(value: Any, label: str, allow_missing: bool = False) -> int | None:
    text = _clean(value).replace(",", "")
    if not text and allow_missing:
        return None
    if not text.isdigit():
        raise ReportImportError(f"Invalid or missing {label} in official PDF table: {value!r}.")
    return int(text)


def _parse_annual_table(
    table: list[list[Any]],
    year: int,
    geography: str,
    page_number: int,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    inherited_disease: str | None = None
    for row in table:
        if len(row) < 5:
            continue
        source_label = _clean(row[1])
        subsection = _clean(row[2]).upper()
        row_number = _clean(row[0])
        if source_label and row_number.isdigit():
            if source_label.startswith("Fever"):
                inherited_disease = "Fever (Undifferentiated)"
                disease = "Fever (Undifferentiated) OP"
                classification = "Not split by source"
                canonical_label = "Fever (Undifferentiated) OP"
                metric_label = "OP"
            else:
                disease, classification, canonical_label = _source_disease_and_classification(source_label)
                metric_label = subsection or "reported cases"
            cases = _table_count(row[3], "case count")
            deaths = _table_count(row[4], "death count", allow_missing=True)
            assert cases is not None
            output.append({
                "year": year,
                "district": geography if geography != "Kerala" else None,
                "disease": disease,
                "classification": classification,
                "source_label": canonical_label,
                "metric_unit": _metric_unit(disease, metric_label),
                "cases": cases,
                "deaths": deaths,
                "source_page": page_number,
            })
        elif (
            not source_label
            and not row_number
            and inherited_disease == "Fever (Undifferentiated)"
            and subsection == "IP"
        ):
            cases = _table_count(row[3], "inpatient fever count")
            assert cases is not None
            output.append({
                "year": year,
                "district": geography if geography != "Kerala" else None,
                "disease": "Fever (Undifferentiated) IP",
                "classification": "Not split by source",
                "source_label": "Fever (Undifferentiated) IP",
                "metric_unit": "inpatient admissions",
                "cases": cases,
                "deaths": None,
                "source_page": page_number,
            })
        else:
            inherited_disease = None
    if not output:
        raise ReportImportError(f"No disease records were extracted from PDF page {page_number}.")
    return output


def _metric_unit(disease: str, source_subtype: str) -> str:
    if disease.startswith("Fever (Undifferentiated)"):
        return "outpatient visits" if source_subtype == "OP" else "reported cases"
    return "reported cases"


def _parse_monthly_tables(pdf: pdfplumber.PDF) -> list[dict[str, Any]]:
    output = []
    found_groups: set[tuple[int, int]] = set()
    month_pattern = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.+)$")
    for page_number in (16, 17):
        text = pdf.pages[page_number - 1].extract_text() or ""
        group_rows: dict[int, list[tuple[str, list[int]]]] = {}
        for line in text.splitlines():
            match = month_pattern.match(line.strip())
            if not match:
                continue
            values = match.group(2).split()
            if not all(value.isdigit() for value in values):
                raise ReportImportError(
                    f"Malformed monthly row on PDF page {page_number}: {line!r}."
                )
            group_rows.setdefault(len(values), []).append(
                (match.group(1), [int(value) for value in values])
            )
        expected_lengths = (16, 14) if page_number == 16 else (14, 10)
        if set(group_rows) != set(expected_lengths):
            raise ReportImportError(
                f"Unexpected monthly table layout on PDF page {page_number}: "
                f"found value counts {sorted(group_rows)}."
            )
        for value_count in expected_lengths:
            definitions = MONTHLY_GROUPS[(page_number, value_count)]
            month_rows = group_rows[value_count]
            if len(month_rows) != 12 or [row[0] for row in month_rows] != list(MONTHS):
                raise ReportImportError(
                    f"PDF page {page_number} does not contain twelve ordered monthly records "
                    f"for the {value_count}-value table."
                )
            found_groups.add((page_number, value_count))
            for month_number, (month_name, values) in enumerate(month_rows, start=1):
                if len(values) != len(definitions) * 2:
                    raise ReportImportError(f"Unexpected measurement count on PDF page {page_number}.")
                for index, (disease, classification, source_label, metric_unit) in enumerate(definitions):
                    cases, deaths = values[index * 2:index * 2 + 2]
                    output.append({
                        "period": f"2025-{month_number:02d}",
                        "month_name": month_name,
                        "year": 2025,
                        "month_num": month_number,
                        "disease": disease,
                        "classification": classification,
                        "source_label": source_label,
                        "metric_unit": metric_unit,
                        "cases": cases,
                        "deaths": deaths,
                        "geography": "Kerala",
                        "geography_level": "Statewide",
                        "source_page": page_number,
                    })
    if found_groups != set(MONTHLY_GROUPS):
        raise ReportImportError("The PDF is missing one or more verified monthly disease tables.")
    return output


def _check_monthly_against_annual(
    monthly: list[dict[str, Any]],
    annual: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sums: dict[tuple[str, str, str], list[int]] = {}
    for row in monthly:
        key = (row["disease"], row["classification"], row["metric_unit"])
        totals = sums.setdefault(key, [0, 0])
        totals[0] += row["cases"]
        totals[1] += row["deaths"]
    annual_index: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in annual:
        annual_index.setdefault(
            (row["disease"], row["classification"], row["metric_unit"]), []
        ).append(row)
    checks = []
    unmatched: set[tuple[str, str, str]] = set()
    for key, monthly_totals in sorted(sums.items()):
        annual_rows = annual_index.get(key, [])
        reconciliation_mode = "same disease, classification and unit"
        if not annual_rows:
            unclassified_key = (key[0], "Not split by source", key[2])
            annual_rows = annual_index.get(unclassified_key, [])
            if len(annual_rows) == 1:
                reconciliation_mode = (
                    "single annual source row; monthly and annual classification labels retained separately"
                )
            else:
                unmatched.add(key)
                continue
        if len(annual_rows) != 1:
            raise ReportImportError(f"Monthly source series matches multiple annual rows: {key}.")
        annual_row = annual_rows[0]
        annual_totals = [annual_row["cases"], annual_row["deaths"]]
        if monthly_totals != annual_totals:
            raise ReportImportError(
                f"Monthly/annual official report totals do not reconcile for {key}: "
                f"monthly={monthly_totals}, annual={annual_totals}."
            )
        checks.append({
            "disease": key[0],
            "classification": key[1],
            "metric_unit": key[2],
            "reconciliation_mode": reconciliation_mode,
            "monthly_cases_sum_matches_annual": True,
            "monthly_deaths_sum_matches_annual": True,
        })
    for disease_metric in {(key[0], key[2]) for key in unmatched}:
        monthly_keys = [
            key for key in sums
            if key[0] == disease_metric[0] and key[2] == disease_metric[1]
        ]
        annual_rows = [
            row for row in annual
            if row["disease"] == disease_metric[0]
            and row["metric_unit"] == disease_metric[1]
        ]
        monthly_totals = [
            sum(sums[key][index] for key in monthly_keys)
            for index in range(2)
        ]
        annual_totals = [
            sum(row["cases"] for row in annual_rows),
            sum(row["deaths"] or 0 for row in annual_rows),
        ]
        if not annual_rows or monthly_totals != annual_totals:
            raise ReportImportError(
                f"Monthly/annual totals do not reconcile for source categories of "
                f"{disease_metric}: monthly={monthly_totals}, annual={annual_totals}."
            )
        checks.append({
            "disease": disease_metric[0],
            "classification": "Source categories differ",
            "metric_unit": disease_metric[1],
            "reconciliation_mode": (
                "aggregate disease subtotal only; source classifications remain separate"
            ),
            "monthly_cases_sum_matches_annual": True,
            "monthly_deaths_sum_matches_annual": True,
        })
    return checks


def _district_reconciliation(
    district_rows: list[dict[str, Any]],
    statewide_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sums: dict[tuple[str, str, str], list[int]] = {}
    for row in district_rows:
        key = (row["disease"], row["classification"], row["metric_unit"])
        totals = sums.setdefault(key, [0, 0])
        totals[0] += row["cases"]
        if row["deaths"] is not None:
            totals[1] += row["deaths"]
    annual_index = {
        (row["disease"], row["classification"], row["metric_unit"]): row
        for row in statewide_rows
    }
    result = []
    for key, district_totals in sorted(sums.items()):
        annual = annual_index.get(key)
        if annual is None:
            continue
        result.append({
            "disease": key[0],
            "classification": key[1],
            "metric_unit": key[2],
            "district_report_count": len({
                row["district"] for row in district_rows
                if (row["disease"], row["classification"], row["metric_unit"]) == key
            }),
            "district_case_sum": district_totals[0],
            "statewide_annual_cases": annual["cases"],
            "case_difference_district_minus_statewide": district_totals[0] - annual["cases"],
            "district_death_sum": district_totals[1],
            "statewide_annual_deaths": annual["deaths"],
            "death_difference_district_minus_statewide": (
                district_totals[1] - annual["deaths"]
                if annual["deaths"] is not None else None
            ),
            "reconciles": (
                district_totals[0] == annual["cases"]
                and (annual["deaths"] is None or district_totals[1] == annual["deaths"])
            ),
            "interpretation": (
                "District subtotal is not reconciled to statewide annual total; "
                "one or more official district pages may be absent or definitions may differ."
            ),
        })
    return result


def parse_official_pdf(
    content: bytes,
    *,
    source_url: str = SOURCE_PDF_URL,
    retrieved_at_utc: str | None = None,
    last_modified: str | None = None,
    retrieval_method: str = "Manually verified official DHS PDF import",
    retrieval_timestamp_basis: str = "Local import time; original source retrieval time was not preserved",
    source_response_date: str | None = None,
) -> dict[str, Any]:
    if source_url != SOURCE_PDF_URL:
        parsed_url = urlparse(source_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != "dhs.kerala.gov.in":
            raise ReportImportError("Report source must be the verified official DHS HTTPS domain.")
    if len(content) > 20 * 1024 * 1024:
        raise ReportImportError("Official PDF exceeds the 20 MiB import limit.")
    if not content.startswith(b"%PDF-"):
        raise ReportImportError("Downloaded source does not have a PDF signature.")

    source_hash = hashlib.sha256(content).hexdigest()
    try:
        pdf_context = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:
        raise ReportImportError(f"Could not parse official DHS PDF: {exc}") from exc
    with pdf_context as pdf:
        if len(pdf.pages) != 17:
            raise ReportImportError(
                f"Unexpected DHS report page count: expected 17, found {len(pdf.pages)}."
            )
        cover = pdf.pages[0].extract_text() or ""
        if "Kerala - Communicable Disease Data for 2025" not in cover:
            raise ReportImportError("PDF title does not match the verified 2025 DHS report.")
        if "Directorate of Health Services, Kerala" not in cover:
            raise ReportImportError("PDF does not identify the Kerala Directorate of Health Services.")
        report_year_text = pdf.pages[1].extract_text() or ""
        if "January - December 2025" not in report_year_text:
            raise ReportImportError("Official report does not cover January–December 2025.")
        state_tables = pdf.pages[1].extract_tables()
        if len(state_tables) != 1:
            raise ReportImportError("Unexpected statewide annual table layout.")
        statewide = _parse_annual_table(state_tables[0], 2025, "Kerala", 2)

        districts = []
        seen_districts = []
        for page_number in range(3, 16):
            page = pdf.pages[page_number - 1]
            lines = (page.extract_text() or "").splitlines()
            if len(lines) < 2:
                raise ReportImportError(f"District name is missing on report page {page_number}.")
            source_district = _clean(lines[1]).upper()
            district = DISTRICT_SOURCE_NAMES.get(source_district)
            if district is None:
                raise ReportImportError(
                    f"Unknown district name on report page {page_number}: {source_district!r}."
                )
            if district in seen_districts:
                raise ReportImportError(f"Duplicate district page detected for {district}.")
            seen_districts.append(district)
            tables = page.extract_tables()
            if len(tables) != 1:
                raise ReportImportError(f"Unexpected annual table count on district page {page_number}.")
            districts.extend(_parse_annual_table(tables[0], 2025, district, page_number))
        if len(seen_districts) != 13:
            raise ReportImportError(
                f"Expected the verified report layout to contain 13 district tables; found {len(seen_districts)}."
            )

        monthly = _parse_monthly_tables(pdf)
        monthly_checks = _check_monthly_against_annual(monthly, statewide)
        missing_districts = sorted(set(EXPECTED_DISTRICTS) - set(seen_districts))
        if missing_districts != ["Alappuzha"]:
            raise ReportImportError(
                f"District coverage differs from verified report layout: missing {missing_districts}."
            )
        reconciliation = _district_reconciliation(districts, statewide)
        modified_date = _parse_last_modified(last_modified)
        pdf_metadata = pdf.metadata or {}
        modified_metadata = pdf_metadata.get("ModDate")
        if isinstance(modified_metadata, str):
            modified_metadata = modified_metadata.removeprefix("D:")

        retrieved = retrieved_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
        dataset_version = f"report-v{IMPORTER_VERSION}-sha256-{source_hash[:16]}"
        draft_snapshot = {
            "monthly_records": monthly,
            "statewide_annual_records": statewide,
            "district_annual_records": districts,
        }
        suspicious_flags = find_suspicious_value_flags(draft_snapshot)
        validations = [
            "Official DHS report title, issuing Directorate, year, page count, and source URL checked.",
            f"All 27 published monthly series contain 12 ordered months; {len(monthly_checks)} monthly totals reconcile to the report's statewide annual table.",
            f"Unique annual records: {len(statewide)} statewide; {len(districts)} across 13 named district pages.",
            "District names map to the Kerala district list; Alappuzha has no district page and is not imputed.",
            "No missing monthly case/death values, duplicate natural keys, or non-numeric/negative counts.",
            f"Suspicious death counts exceeding cases: {len(suspicious_flags)} record(s) flagged and retained.",
        ]
        snapshot = {
            "schema_version": 1,
            "source_id": SOURCE_ID,
            "source_name": SOURCE_NAME,
            "source_index_url": SOURCE_INDEX_URL,
            "source_url": source_url,
            "source_document": "Kerala - Communicable Disease Data for 2025 (approved PDF)",
            "reporting_period": "2025",
            "reporting_period_start": "2025-01",
            "reporting_period_end": "2025-12",
            "frequency": "annual report with monthly statewide tables",
            "retrieval_method": retrieval_method,
            "retrieved_at_utc": retrieved,
            "retrieval_timestamp_basis": retrieval_timestamp_basis,
            "source_response_date": source_response_date,
            "publication_date": None,
            "publication_date_note": (
                "A formal publication date is not stated in the PDF or the listing page. "
                f"The PDF server returned Last-Modified date {modified_date or 'not available'}."
            ),
            "last_modified_date": modified_date,
            "pdf_metadata_mod_date": modified_metadata,
            "source_sha256": source_hash,
            "dataset_version": dataset_version,
            "validation_status": "passed_with_quality_flags" if suspicious_flags else "passed",
            "suspicious_value_flags": suspicious_flags,
            "validation_checks": validations,
            "monthly_validation_totals": monthly_checks,
            "available_variables": [
                "monthly statewide cases and deaths for 27 source disease/category series",
                    f"statewide annual cases and deaths for {len(statewide)} source table rows",
                    f"annual district cases and deaths for 13 districts and {len(districts)} source table rows",
                "outpatient fever counts and inpatient fever admissions kept as separate metrics",
            ],
            "monthly_records": monthly,
            "statewide_annual_records": statewide,
            "district_annual_records": districts,
            "reported_districts": sorted(seen_districts),
            "missing_districts": missing_districts,
            "district_reconciliation": reconciliation,
            "limitations": [
                "This is the latest official annual report linked by the DHS disease-data index at investigation time, not live or 2026 disease surveillance.",
                "The report covers January–December 2025. Its public listing has no stated formal publication date; the PDF Last-Modified date is recorded separately.",
                "The annual district section contains 13 district tables. Alappuzha is absent; the district is not filled with zero or inferred.",
                "Several 13-district subtotals do not reconcile to the report's statewide annual totals. Differences are retained and explicitly reported.",
                "District records are annual, not district-month observations. Statewide monthly records cannot be assigned to districts.",
                "Source-confirmed and source-probable categories are kept separate; categories without a split are labelled Not split by source.",
                "Reported counts are not incidence rates and do not establish outbreaks or causal effects.",
                "A DHS webpage PDF was verified; no public data API or daily update feed was found.",
                "Undifferentiated fever outpatient visits and inpatient admissions have different units and are not mixed with communicable-disease case counts.",
            ],
        }
    validate_snapshot(snapshot)
    return snapshot


def _parse_last_modified(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ReportImportError(f"Invalid official PDF Last-Modified header: {value!r}.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


def _store_raw_pdf(content: bytes) -> Path:
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(content)
    existing = ROOT / "data" / "raw" / "DHS-CD-Data-2025-Approved.pdf"
    if existing.is_file() and sha256_bytes(existing.read_bytes()) == digest:
        return existing
    path = raw_dir / f"DHS-CD-Data-2025-Approved-{digest[:16]}.pdf"
    if path.exists():
        if sha256_bytes(path.read_bytes()) != digest:
            raise ReportImportError(f"Hash collision or modified immutable raw PDF: {path}")
        return path
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return path


def fetch_official_pdf(
    session: requests.Session | None = None,
) -> tuple[bytes, str | None, str, str | None]:
    client = session or requests.Session()
    try:
        with client.get(SOURCE_PDF_URL, stream=True, timeout=(10, 30), allow_redirects=True) as response:
            response.raise_for_status()
            final_url = urlparse(response.url)
            expected_url = urlparse(SOURCE_PDF_URL)
            if (
                final_url.scheme != "https"
                or final_url.hostname != expected_url.hostname
                or final_url.path != expected_url.path
            ):
                raise ReportImportError(
                    "Official PDF request redirected outside the verified DHS report URL; "
                    "no alternative source was used."
                )
            if "pdf" not in response.headers.get("Content-Type", "").casefold():
                raise ReportImportError(
                    "Verified DHS report URL returned a non-PDF content type; "
                    "response was not imported."
                )
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 20 * 1024 * 1024:
                    raise ReportImportError("Official DHS PDF exceeds the 20 MiB download limit.")
                chunks.append(chunk)
            content = b"".join(chunks)
            if not content.startswith(b"%PDF-"):
                raise ReportImportError("Official DHS source response is not a PDF.")
            server_date = response.headers.get("Date")
            retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return content, response.headers.get("Last-Modified"), retrieved, server_date
    except requests.RequestException as exc:
        raise ReportImportError(f"Official DHS report is unavailable: {exc}") from exc


def import_report(
    *,
    pdf_path: Path | None = None,
    download: bool = False,
    source_url: str = SOURCE_PDF_URL,
    last_modified: str | None = None,
) -> dict[str, Any]:
    if download and pdf_path is not None:
        raise ReportImportError("Choose either --download or --pdf, not both.")
    try:
        if download:
            if source_url != SOURCE_PDF_URL:
                raise ReportImportError(
                    "Automated downloads are restricted to the exact DHS PDF URL that was verified."
                )
            content, last_modified_header, retrieved, server_response_date = fetch_official_pdf()
            path = _store_raw_pdf(content)
            modified = last_modified_header
            response_date = server_response_date
            method = "Exact verified DHS PDF URL over HTTPS; no API or alternate source used"
            timestamp_basis = "Client UTC timestamp recorded immediately after successful PDF retrieval"
        else:
            if pdf_path is None:
                raise ReportImportError("Provide --pdf with an official report path or explicitly pass --download.")
            resolved = pdf_path.resolve()
            if not resolved.is_file():
                raise ReportImportError(f"Official PDF file does not exist: {resolved}")
            if resolved.stat().st_size > 20 * 1024 * 1024:
                raise ReportImportError("Official PDF exceeds the 20 MiB import limit.")
            content = resolved.read_bytes()
            path = resolved
            modified = last_modified
            retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
            response_date = None
            method = "Manually imported local PDF after official DHS source verification"
            timestamp_basis = "Local import timestamp; original source retrieval timestamp was not preserved"
        if urlparse(source_url).hostname != "dhs.kerala.gov.in":
            raise ReportImportError("Manual report imports must retain the official DHS source domain.")
        snapshot = parse_official_pdf(
            content,
            source_url=source_url,
            retrieved_at_utc=retrieved,
            last_modified=modified,
            retrieval_method=method,
            retrieval_timestamp_basis=timestamp_basis,
            source_response_date=response_date,
        )
        snapshot["original_pdf_file"] = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
        record_refresh_success(snapshot)
        return snapshot
    except (ReportImportError, SurveillanceUnavailable, OSError) as exc:
        record_refresh_failure(str(exc))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--download", action="store_true", help="Fetch only the exact, verified DHS report PDF URL.")
    source.add_argument("--pdf", type=Path, help="Import a locally saved official DHS PDF.")
    parser.add_argument("--source-url", default=SOURCE_PDF_URL, help="Official DHS source URL used for provenance.")
    parser.add_argument(
        "--last-modified",
        help="HTTP Last-Modified value or YYYY-MM-DD when importing a saved official PDF.",
    )
    args = parser.parse_args()
    try:
        snapshot = import_report(
            pdf_path=args.pdf,
            download=args.download,
            source_url=args.source_url,
            last_modified=args.last_modified,
        )
    except (ReportImportError, SurveillanceUnavailable, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"SUCCESS: imported {snapshot['source_document']}")
    print(f"Reporting period: {snapshot['reporting_period_start']} to {snapshot['reporting_period_end']}")
    print(f"Monthly statewide observations: {len(snapshot['monthly_records'])}")
    print(f"Annual statewide records: {len(snapshot['statewide_annual_records'])}")
    print(
        f"Annual district records: {len(snapshot['district_annual_records'])} "
        f"across {len(snapshot['reported_districts'])}/14 districts; "
        f"missing={snapshot['missing_districts']}"
    )
    print(f"Dataset version: {snapshot['dataset_version']}")
    print(f"Last successful retrieval: {snapshot['retrieved_at_utc']}")
    print("Source snapshot retained; prior versioned snapshots were not overwritten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
