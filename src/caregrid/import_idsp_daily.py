"""Discover, download, and validate Kerala DHS daily IDSP reports."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import pdfplumber
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from caregrid.daily_surveillance import (  # noqa: E402
    DAILY_DIR,
    EXPECTED_DISTRICT_CODES,
    INDEX_URL,
    PARSER_VERSION,
    ROOT,
    DailySurveillanceUnavailable,
    find_daily_quality_flags,
    record_daily_refresh_failure,
    record_daily_refresh_success,
    load_daily_history,
    sha256_bytes,
    validate_daily_snapshot,
)


SOURCE_NAME = "Kerala Directorate of Health Services — IDSP daily reports"
MAX_INDEX_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 20 * 1024 * 1024
MAX_REPORT_CANDIDATES = 8
MAX_BACKFILL_REPORTS = 120
BACKFILL_REQUEST_DELAY_SECONDS = 0.25
COUNT_FIELDS = (
    "suspected_cases",
    "suspected_deaths",
    "confirmed_cases",
    "confirmed_deaths",
)
PERIOD_LABELS = {
    "daily": "Daily",
    "present_month": "Present Month",
    "cumulative_2026": "Cumulative 2026",
}
STATE_DISEASE_LABELS = {
    "Fever": ("Fever", None),
    "Malaria": ("Malaria", "Indigenous"),
    "Dengue Fever": ("Dengue", None),
    "Chikungunya": ("Chikungunya", None),
    "Con JE": ("Japanese Encephalitis", None),
    "AES": ("Acute Encephalitis Syndrome", None),
    "Leptospirosis": ("Leptospirosis", None),
    "Hepatitis-A": ("Hepatitis A", None),
    "Hepatitis-E": ("Hepatitis E", None),
    "Cholera": ("Cholera", None),
    "Typhoid": ("Typhoid", None),
    "ADD": ("Acute Diarrheal Disease", None),
    "Measles": ("Measles", None),
    "Mumps": ("Mumps", None),
    "Chicken Pox": ("Chicken Pox", None),
    "Influenza": ("Influenza", None),
    "Scrub Typhus": ("Scrub Typhus", None),
    "Diphtheria": ("Diphtheria", None),
    "Rabies": ("Rabies", None),
    "Zika": ("Zika", None),
    "Nipah": ("Nipah", None),
    "M Pox": ("Mpox", None),
    "Shigella": ("Shigella", None),
    "West Nile": ("West Nile", None),
    "Amebic Meningoencephalitis": ("Amoebic Meningoencephalitis", None),
}
DISTRICT_COLUMN_MAP = (
    ("Fever", "OP", 2, "outpatient visits", None),
    ("Fever", "IP", 3, "inpatient admissions", None),
    ("Chikungunya", None, 4, "reported cases", "suspected"),
    ("Chikungunya", None, 5, "reported cases", "confirmed"),
    ("Chikungunya", None, 6, "reported deaths", "unclassified"),
    ("Dengue", None, 7, "reported cases", "suspected"),
    ("Dengue", None, 8, "reported cases", "confirmed"),
    ("Dengue", None, 9, "reported deaths", "unclassified"),
    ("Leptospirosis", None, 10, "reported cases", "suspected"),
    ("Leptospirosis", None, 11, "reported cases", "confirmed"),
    ("Leptospirosis", None, 12, "reported deaths", "unclassified"),
    ("Acute Diarrheal Disease", None, 13, "reported cases", "unclassified"),
    ("Chicken Pox", None, 14, "reported cases", "unclassified"),
    ("Hepatitis A", None, 15, "reported cases", "unclassified"),
    ("Cholera", None, 16, "reported cases", "suspected"),
    ("Cholera", None, 17, "reported deaths", "suspected"),
    ("Cholera", None, 18, "reported cases", "confirmed"),
    ("Cholera", None, 19, "reported deaths", "confirmed"),
    ("Acute Encephalitis Syndrome", None, 20, "reported cases", "unclassified"),
    ("Japanese Encephalitis", None, 21, "reported cases", "confirmed"),
    ("Malaria", "Plasmodium vivax imported", 22, "reported cases", "unclassified"),
    ("Malaria", "Plasmodium vivax indigenous", 23, "reported cases", "unclassified"),
    ("Malaria", "Plasmodium falciparum imported", 24, "reported cases", "unclassified"),
    ("Malaria", "Plasmodium falciparum indigenous", 25, "reported cases", "unclassified"),
    ("Malaria", "Mixed infection imported", 26, "reported cases", "unclassified"),
    ("Malaria", "Mixed infection indigenous", 27, "reported cases", "unclassified"),
    ("Malaria", None, 28, "reported deaths", "unclassified"),
    ("Scrub Typhus", None, 29, "reported cases", "unclassified"),
    ("Measles", None, 30, "reported cases", "unclassified"),
    ("Influenza", None, 31, "reported cases", "unclassified"),
)


class ReportImportError(ValueError):
    """Official daily report discovery or validation failed."""

    def __init__(
        self,
        message: str,
        *,
        source_url: str | None = None,
        source_sha256: str | None = None,
        original_file: str | None = None,
        retrieved_at_utc: str | None = None,
    ) -> None:
        super().__init__(message)
        self.source_url = source_url
        self.source_sha256 = source_sha256
        self.original_file = original_file
        self.retrieved_at_utc = retrieved_at_utc


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self._active_href = dict(attrs).get("href")
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_href is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._active_href is not None:
            self.anchors.append((self._active_href, " ".join(" ".join(self._active_text).split())))
            self._active_href = None
            self._active_text = []


class _PostPublicationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        value = None
        if tag.casefold() == "time" and "published" in (attributes.get("class") or "").split():
            value = attributes.get("datetime")
        elif tag.casefold() == "meta" and (
            (attributes.get("property") or "").casefold() == "article:published_time"
            or (attributes.get("itemprop") or "").casefold() == "datepublished"
        ):
            value = attributes.get("content")
        if value:
            self.candidates.append(value)


def extract_post_published_at(post_html: str) -> str | None:
    parser = _PostPublicationParser()
    parser.feed(post_html)
    for candidate in parser.candidates:
        try:
            published = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            continue
        if published.tzinfo is not None:
            return published.isoformat()
    return None


def _official_kerala_url(value: str, base_url: str) -> str:
    absolute = urljoin(base_url, value)
    parsed = urlparse(absolute)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not (
        hostname == "kerala.gov.in" or hostname.endswith(".kerala.gov.in")
    ):
        raise ReportImportError(f"Refusing a non-Kerala-government source URL: {absolute}")
    return absolute


def _parse_listing_date(label: str) -> date | None:
    text = " ".join(unquote(label).split())
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", text)
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def discover_reports(page_html: str, page_url: str = INDEX_URL) -> list[dict[str, Any]]:
    parser = _AnchorParser()
    parser.feed(page_html)
    discovered: dict[str, dict[str, Any]] = {}
    for href, label in parser.anchors:
        report_date = _parse_listing_date(label)
        if report_date is None or not href:
            continue
        try:
            post_url = _official_kerala_url(href, page_url)
        except ReportImportError:
            continue
        discovered.setdefault(report_date.isoformat(), {
            "report_date": report_date.isoformat(),
            "post_url": post_url,
            "listing_label": label,
        })
    return sorted(discovered.values(), key=lambda row: row["report_date"], reverse=True)


def discover_pdf_link(post_html: str, post_url: str) -> str:
    parser = _AnchorParser()
    parser.feed(post_html)
    candidates = []
    for href, _label in parser.anchors:
        if not href:
            continue
        try:
            absolute = _official_kerala_url(href, post_url)
        except ReportImportError:
            continue
        if urlparse(absolute).path.casefold().endswith(".pdf"):
            candidates.append(absolute)
    if not candidates:
        raise ReportImportError(f"No directly linked official PDF was found on the DHS post {post_url}.")
    if len(set(candidates)) != 1:
        raise ReportImportError(
            f"DHS daily post contains multiple PDF links and no report attachment can be selected safely: {post_url}."
        )
    return candidates[0]


def _fetch_html(session: requests.Session, url: str, max_bytes: int) -> str:
    try:
        with session.get(url, timeout=(10, 30), allow_redirects=True, stream=True) as response:
            response.raise_for_status()
            final_url = _official_kerala_url(response.url, url)
            if final_url != url:
                raise ReportImportError(f"Official DHS page redirected unexpectedly to {final_url}.")
            chunks, length = [], 0
            for chunk in response.iter_content(chunk_size=32 * 1024):
                if not chunk:
                    continue
                length += len(chunk)
                if length > max_bytes:
                    raise ReportImportError(f"Official DHS page exceeded the {max_bytes}-byte limit.")
                chunks.append(chunk)
            return b"".join(chunks).decode(response.encoding or "utf-8", errors="strict")
    except (requests.RequestException, UnicodeDecodeError) as exc:
        raise ReportImportError(f"Could not retrieve official DHS page {url}: {exc}") from exc


def _fetch_pdf(session: requests.Session, url: str) -> tuple[bytes, dict[str, str], str]:
    try:
        with session.get(url, timeout=(10, 45), allow_redirects=True, stream=True) as response:
            response.raise_for_status()
            final_url = _official_kerala_url(response.url, url)
            if final_url != url:
                raise ReportImportError(f"Official DHS PDF redirected unexpectedly to {final_url}.")
            if "pdf" not in response.headers.get("Content-Type", "").casefold():
                raise ReportImportError("The linked daily-report document did not return PDF content.")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_REPORT_BYTES:
                raise ReportImportError("Daily IDSP PDF exceeds the 20 MiB download limit.")
            chunks, total = [], 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_REPORT_BYTES:
                    raise ReportImportError("Daily IDSP PDF exceeds the 20 MiB download limit.")
                chunks.append(chunk)
            content = b"".join(chunks)
            if not content.startswith(b"%PDF-"):
                raise ReportImportError("Linked DHS document has no PDF signature.")
            return content, dict(response.headers), response.url
    except (requests.RequestException, ValueError) as exc:
        raise ReportImportError(f"Could not retrieve official DHS PDF {url}: {exc}") from exc


def _parse_count(value: Any, label: str) -> tuple[int | None, str]:
    raw = "" if value is None else str(value).strip()
    if raw in {"", "–", "—", "-"}:
        return None, raw
    normalized = raw.replace(",", "")
    if not normalized.isdigit():
        raise ReportImportError(f"Invalid {label} in DHS table: {raw!r}.")
    return int(normalized), raw


def _parse_table_report_date(value: Any) -> date:
    raw = _clean(value)
    for pattern in ("%d-%m-%y", "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue
    raise ReportImportError(f"Unrecognized reporting date in DHS table: {raw!r}.")


def _source_value_status(raw: str) -> str:
    if raw == "-":
        return "source_dash_uninterpreted"
    if raw in {"", "–", "—"}:
        return "not_reported"
    return "reported"


def _row_values(row: list[Any], offset: int) -> tuple[dict[str, int | None], dict[str, str]]:
    values, raw_values = {}, {}
    for index, field in enumerate(COUNT_FIELDS):
        parsed, raw = _parse_count(row[offset + index], field)
        values[field] = parsed
        raw_values[field] = raw
    return values, raw_values


def _state_disease_name(raw_name: str, subtype: str) -> tuple[str, str | None]:
    if raw_name not in STATE_DISEASE_LABELS:
        raise ReportImportError(f"Unexpected disease label in the daily IDSP table: {raw_name!r}.")
    disease, default_subtype = STATE_DISEASE_LABELS[raw_name]
    if raw_name == "Malaria":
        if subtype not in {"Ind.", "Imp."}:
            raise ReportImportError(f"Unexpected malaria subtype in daily report: {subtype!r}.")
        return disease, "Indigenous" if subtype == "Ind." else "Imported"
    if subtype:
        raise ReportImportError(f"Unexpected disease subtype {subtype!r} for {raw_name!r}.")
    return disease, default_subtype


def _parse_statewide_table(
    table: list[list[Any]], report_date: date
) -> list[dict[str, Any]]:
    if len(table) < 29 or len(table[0]) != 15:
        raise ReportImportError("Unexpected statewide daily IDSP table dimensions.")
    header_date = _clean(table[0][11])
    try:
        parsed_header_date = _parse_table_report_date(header_date)
    except ReportImportError:
        parsed_header_date = None
    if parsed_header_date != report_date:
        raise ReportImportError(
            f"PDF statewide table date {header_date!r} does not match discovered post date {report_date.isoformat()}."
        )
    expected_period_headers = (
        _clean(table[1][3]),
        _clean(table[1][7]),
        _clean(table[1][11]),
    )
    if expected_period_headers != ("Daily", "Present Month", "Cumulative 2026"):
        raise ReportImportError(f"Unexpected daily IDSP period headers: {expected_period_headers!r}.")
    records: list[dict[str, Any]] = []
    active_disease: str | None = None
    for row in table[3:29]:
        if len(row) != 15:
            raise ReportImportError("A statewide daily IDSP row has an unexpected number of columns.")
        row_number = _clean(row[0])
        raw_label = _clean(row[1])
        subtype = _clean(row[2])
        if row_number.isdigit():
            active_disease = raw_label
        elif not raw_label and active_disease == "Malaria":
            pass
        else:
            continue
        if active_disease is None:
            raise ReportImportError("Statewide IDSP row is missing its disease name.")
        disease, mapped_subtype = _state_disease_name(active_disease, subtype)
        metrics = {}
        raw_metrics = {}
        value_status = {}
        for period, offset in (("daily", 3), ("present_month", 7), ("cumulative_2026", 11)):
            metrics[period], raw_metrics[period] = _row_values(row, offset)
            value_status[period] = {
                field: _source_value_status(raw_metrics[period][field])
                for field in COUNT_FIELDS
            }
        records.append({
            "disease": disease,
            "disease_subtype": mapped_subtype,
            "source_label": f"{active_disease}{' ' + subtype if subtype else ''}",
            **metrics,
            "source_values": raw_metrics,
            "source_value_status": value_status,
            "source_period_labels": PERIOD_LABELS,
        })
    if len(records) != 26:
        raise ReportImportError(
            f"Expected 26 daily statewide disease/subtype rows in the DHS report; found {len(records)}."
        )
    return records


def _parse_district_table(
    table: list[list[Any]], report_date: date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(table) != 40 or len(table[5]) not in {31, 32}:
        raise ReportImportError("Unexpected district-wise daily IDSP table dimensions.")
    header_date = _clean(table[0][22])
    try:
        parsed_header_date = _parse_table_report_date(header_date)
    except ReportImportError:
        parsed_header_date = None
    if parsed_header_date != report_date:
        raise ReportImportError(
            f"PDF district table date {header_date!r} does not match discovered post date {report_date.isoformat()}."
        )
    found_codes: list[str] = []
    records = []
    for source_row in table[5:19]:
        row = source_row + [None] if len(source_row) == 31 else source_row
        if len(row) != 32:
            raise ReportImportError("A district daily report row has an unexpected number of columns.")
        if not any(_clean(value) for value in row):
            continue
        code = _clean(row[1]).upper()
        if code not in EXPECTED_DISTRICT_CODES:
            raise ReportImportError(f"Unknown official DHS district code in daily report: {code!r}.")
        if code in found_codes:
            raise ReportImportError(f"Duplicate district code in daily report: {code}.")
        found_codes.append(code)
        grouped: dict[tuple[str, str | None], dict[str, Any]] = {}
        raw_grouped: dict[tuple[str, str | None], dict[str, Any]] = {}
        for disease, subtype, column, unit, category in DISTRICT_COLUMN_MAP:
            value, raw = _parse_count(row[column], f"{disease} {unit}")
            key = (disease, subtype)
            record = grouped.setdefault(key, {
                "disease": disease,
                "disease_subtype": subtype,
                "source_label": disease if subtype is None else f"{disease} — {subtype}",
                "metric_unit": unit,
                "suspected_cases": None,
                "confirmed_cases": None,
                "suspected_deaths": None,
                "confirmed_deaths": None,
                "reported_cases": None,
                "reported_deaths": None,
            })
            raw_record = raw_grouped.setdefault(key, {})
            raw_record[str(column)] = raw
            if category in {"suspected", "confirmed"} and unit == "reported cases":
                field = f"{category}_cases"
                record[field] = value
                record.setdefault("field_source_status", {})[field] = _source_value_status(raw)
            elif category in {"suspected", "confirmed"} and unit == "reported deaths":
                field = f"{category}_deaths"
                record[field] = value
                record.setdefault("field_source_status", {})[field] = _source_value_status(raw)
            elif category == "unclassified" and unit == "reported cases":
                record["reported_cases"] = value
                record.setdefault("field_source_status", {})["reported_cases"] = _source_value_status(raw)
            elif category == "unclassified" and unit == "reported deaths":
                record["reported_deaths"] = value
                record.setdefault("field_source_status", {})["reported_deaths"] = _source_value_status(raw)
            elif disease == "Fever":
                record["reported_cases"] = value
                record.setdefault("field_source_status", {})["reported_cases"] = _source_value_status(raw)
        for key, record in grouped.items():
            if any(value.strip() for value in raw_grouped[key].values()):
                record["source_values"] = raw_grouped[key]
                record["source_value_status"] = {
                    column: _source_value_status(raw_value)
                    for column, raw_value in raw_grouped[key].items()
                }
                record["district_code"] = code
                record["district"] = EXPECTED_DISTRICT_CODES[code]
                records.append(record)
    if not found_codes:
        raise ReportImportError(
            "District daily report contains no usable district rows."
        )

    totals_row = table[19]
    if _clean(totals_row[1]).upper() != "TOT":
        raise ReportImportError("District daily report aggregate row is missing.")
    district_reconciliation = []
    for disease, suspected_column, confirmed_column in (
        ("Dengue", 7, 8),
        ("Leptospirosis", 10, 11),
    ):
        for category, column in (("suspected", suspected_column), ("confirmed", confirmed_column)):
            value, raw = _parse_count(totals_row[column], f"district aggregate {disease} {category}")
            if value is not None:
                district_values = [
                    next(
                        (
                            item[f"{category}_cases"]
                            for item in records
                            if item["district_code"] == code
                            and item["disease"] == disease
                        ),
                        None,
                    )
                    for code in found_codes
                ]
                district_sum = (
                    sum(district_values)
                    if all(item is not None for item in district_values)
                    else None
                )
                district_reconciliation.append({
                    "disease": disease,
                    "classification": category.title(),
                    "district_sum": district_sum,
                    "district_table_total": value,
                    "difference": district_sum - value if district_sum is not None else None,
                    "reconciles": district_sum == value if district_sum is not None else None,
                    "raw_total": raw,
                })
    if len(records) < 14:
        raise ReportImportError("District daily table contains no usable district records.")
    return records, district_reconciliation


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def parse_daily_pdf(
    content: bytes,
    *,
    report_date: date,
    source_page_url: str,
    source_url: str,
    retrieved_at_utc: str,
    source_response_date: str | None,
    source_last_modified: str | None,
    original_filename: str,
    source_post_published_at: str | None = None,
    discovery_failures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if len(content) > MAX_REPORT_BYTES:
        raise ReportImportError("Daily IDSP PDF exceeds the 20 MiB import limit.")
    if not content.startswith(b"%PDF-"):
        raise ReportImportError("Daily IDSP document does not have a PDF signature.")
    _official_kerala_url(source_page_url, INDEX_URL)
    _official_kerala_url(source_url, source_page_url)
    if not urlparse(source_url).path.casefold().endswith(".pdf"):
        raise ReportImportError("Daily IDSP source URL is not a PDF attachment.")
    try:
        pdf_context = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:
        raise ReportImportError(f"Could not parse official DHS daily PDF: {exc}") from exc
    with pdf_context as pdf:
        if len(pdf.pages) != 3:
            raise ReportImportError(f"Unexpected daily DHS IDSP PDF page count: {len(pdf.pages)}.")
        page1 = pdf.pages[0].extract_text() or ""
        if "Directorate of Health Services, Kerala" not in page1:
            raise ReportImportError("Daily PDF does not identify Kerala Directorate of Health Services.")
        expected_title = f"Communicable Diseases - Daily Report on {report_date.strftime('%B')} {report_date.day}, {report_date.year}"
        if expected_title not in page1:
            raise ReportImportError("Daily PDF title date does not match the discovered official report date.")
        state_tables = pdf.pages[2].extract_tables()
        district_tables = pdf.pages[1].extract_tables()
        if len(state_tables) != 1:
            raise ReportImportError("Daily DHS PDF is missing the expected statewide table.")
        statewide_records = _parse_statewide_table(state_tables[0], report_date)
        district_error = None
        try:
            if len(district_tables) != 1:
                raise ReportImportError("The PDF does not contain one district reporting table.")
            district_records, reconciliation = _parse_district_table(
                district_tables[0], report_date
            )
            districts_available = True
            reported_codes = sorted({row["district_code"] for row in district_records})
        except (ReportImportError, IndexError, TypeError) as exc:
            district_records, reconciliation = [], []
            districts_available = False
            reported_codes = []
            district_error = str(exc)

        note = (pdf.pages[2].extract_text() or "").replace("\n", " ")
        provisional_warning = (
            "The reported cases and deaths are based on a preliminary report and are liable "
            "to change after laboratory tests and death audits."
        )
        if "Preliminary report" not in note or "Lab tests" not in note or "Death audits" not in note:
            raise ReportImportError("The expected provisional-data warning is absent from the source PDF.")
        digest = hashlib.sha256(content).hexdigest()
        snapshot = {
            "schema_version": 1,
            "source_id": "kerala_dhs_idsp_daily_pdf",
            "source_name": SOURCE_NAME,
            "source_index_url": INDEX_URL,
            "source_page_url": source_page_url,
            "source_post_published_at": source_post_published_at,
            "source_url": source_url,
            "source_document": original_filename,
            "report_date": report_date.isoformat(),
            "retrieved_at_utc": retrieved_at_utc,
            "retrieval_timestamp_basis": "Client UTC timestamp recorded immediately after successful PDF retrieval",
            "source_response_date": source_response_date,
            "source_last_modified": source_last_modified,
            "source_sha256": digest,
            "parser_version": PARSER_VERSION,
            "dataset_version": f"idsp-v{PARSER_VERSION}-{digest[:16]}",
            "validation_status": "passed",
            "daily_district_report_available": districts_available,
            "district_report_error": district_error,
            "reported_district_codes": reported_codes,
            "district_code_mapping": EXPECTED_DISTRICT_CODES,
            "district_reconciliation": reconciliation,
            "count_dash_policy": (
                "A printed hyphen is retained as source_dash_uninterpreted and its numeric value is null "
                "because the report provides no legend defining it. Blank/en/em-dash cells are retained "
                "as not_reported and numeric null. An explicit printed 0 is numeric zero."
            ),
            "statewide_records": statewide_records,
            "district_records": district_records,
            "provisional_warning": provisional_warning,
            "discovery_failures": discovery_failures or [],
            "quality_flags": [],
        }
        snapshot["quality_flags"] = find_daily_quality_flags(snapshot)
        if snapshot["quality_flags"]:
            snapshot["validation_status"] = "passed_with_quality_flags"
        snapshot["validation_checks"] = [
            "Report post link was discovered from the official DHS IDSP index; PDF URL extracted from the post, not guessed.",
            f"Official DHS PDF title and statewide/district table dates match {report_date.isoformat()}.",
            f"Preserved {len(statewide_records)} statewide disease/subtype rows across daily, present-month and cumulative-2026 periods.",
            (
                f"District-wise daily table validates all 14 official district codes and {len(district_records)} disease/metric rows."
                if districts_available else "District-wise report is unavailable; no historical district data were substituted."
            ),
            "Raw source cell strings and explicit-value statuses are retained. Printed hyphens are not assumed to mean zero; blank cells remain not reported.",
            "Source warns that cases/deaths are preliminary and subject to laboratory tests and death audits.",
        ]
    validate_daily_snapshot(snapshot)
    return snapshot


def _store_raw_pdf(content: bytes, source_url: str) -> Path:
    filename = Path(unquote(urlparse(source_url).path)).name
    if not filename or not re.fullmatch(r"[A-Za-z0-9._-]+\.pdf", filename, re.IGNORECASE):
        raise ReportImportError("DHS attachment has an unsafe or unrecognized PDF filename.")
    raw_directory = ROOT / "data" / "raw" / "idsp_daily"
    raw_directory.mkdir(parents=True, exist_ok=True)
    target = raw_directory / filename
    digest = sha256_bytes(content)
    if target.exists():
        if sha256_bytes(target.read_bytes()) == digest:
            return target
        target = raw_directory / f"{Path(filename).stem}-{digest[:16]}.pdf"
        if target.exists():
            if sha256_bytes(target.read_bytes()) != digest:
                raise ReportImportError(f"Preserved DHS PDF changed unexpectedly: {target}")
            return target
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(target)
    return target


def retrieve_latest_report(session: requests.Session | None = None) -> dict[str, Any]:
    client = session or requests.Session()
    failures: list[dict[str, str]] = []
    try:
        index_html = _fetch_html(client, INDEX_URL, MAX_INDEX_BYTES)
        candidates = discover_reports(index_html, INDEX_URL)[:MAX_REPORT_CANDIDATES]
        if not candidates:
            raise ReportImportError("Official DHS IDSP index contains no dated daily report links.")
        for candidate in candidates:
            try:
                return retrieve_candidate_report(client, candidate, failures)
            except (ReportImportError, DailySurveillanceUnavailable, OSError, requests.RequestException) as exc:
                failures.append({
                    "report_date": candidate["report_date"],
                    "post_url": candidate["post_url"],
                    "error": str(exc)[:500],
                })
        raise ReportImportError(
            "No daily IDSP report among the latest eight official DHS entries could be downloaded "
            "and validated. " + "; ".join(item["error"] for item in failures[-3:])
        )
    except (ReportImportError, DailySurveillanceUnavailable, requests.RequestException, OSError) as exc:
        record_daily_refresh_failure(str(exc))
        raise ReportImportError(str(exc)) from exc


def retrieve_candidate_report(
    session: requests.Session,
    candidate: dict[str, Any],
    discovery_failures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    post_html = _fetch_html(session, candidate["post_url"], MAX_INDEX_BYTES)
    post_published_at = extract_post_published_at(post_html)
    pdf_url = discover_pdf_link(post_html, candidate["post_url"])
    content, headers, final_url = _fetch_pdf(session, pdf_url)
    raw_path = _store_raw_pdf(content, final_url)
    report_date = date.fromisoformat(candidate["report_date"])
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    filename = Path(unquote(urlparse(final_url).path)).name
    try:
        snapshot = parse_daily_pdf(
            content,
            report_date=report_date,
            source_page_url=candidate["post_url"],
            source_url=final_url,
            retrieved_at_utc=retrieved,
            source_response_date=headers.get("Date"),
            source_last_modified=headers.get("Last-Modified"),
            original_filename=filename,
            source_post_published_at=post_published_at,
            discovery_failures=discovery_failures,
        )
    except (ReportImportError, DailySurveillanceUnavailable) as exc:
        raise ReportImportError(
            str(exc),
            source_url=final_url,
            source_sha256=sha256_bytes(content),
            original_file=raw_path.relative_to(ROOT).as_posix(),
            retrieved_at_utc=retrieved,
        ) from exc
    snapshot["original_file"] = raw_path.relative_to(ROOT).as_posix()
    record_daily_refresh_success(snapshot)
    return snapshot


def backfill_2026_reports(
    session: requests.Session | None = None,
    *,
    max_reports: int = MAX_BACKFILL_REPORTS,
    request_delay_seconds: float = BACKFILL_REQUEST_DELAY_SECONDS,
) -> dict[str, Any]:
    if max_reports < 1 or max_reports > MAX_BACKFILL_REPORTS:
        raise ValueError(f"max_reports must be between 1 and {MAX_BACKFILL_REPORTS}.")
    if request_delay_seconds < 0:
        raise ValueError("request_delay_seconds cannot be negative.")
    client = session or requests.Session()
    try:
        index_html = _fetch_html(client, INDEX_URL, MAX_INDEX_BYTES)
        discovered = [
            row for row in discover_reports(index_html, INDEX_URL)
            if row["report_date"].startswith("2026-")
        ][:max_reports]
    except (ReportImportError, requests.RequestException, OSError) as exc:
        record_daily_refresh_failure(str(exc))
        raise ReportImportError(f"Could not discover 2026 reports from the official DHS index: {exc}") from exc
    existing_dates = {snapshot["report_date"] for snapshot in load_daily_history()}
    imported_dates = set(existing_dates)
    failures: list[dict[str, Any]] = []
    skipped_dates = []
    for candidate in discovered:
        report_date = candidate["report_date"]
        if report_date in existing_dates:
            skipped_dates.append(report_date)
            continue
        try:
            retrieve_candidate_report(client, candidate)
            imported_dates.add(report_date)
        except (ReportImportError, DailySurveillanceUnavailable, OSError, requests.RequestException) as exc:
            failure: dict[str, Any] = {
                "report_date": report_date,
                "post_url": candidate["post_url"],
                "error": str(exc)[:500],
            }
            for key in ("source_url", "source_sha256", "original_file", "retrieved_at_utc"):
                value = getattr(exc, key, None)
                if value is not None:
                    failure[key] = value
            failures.append(failure)
        if request_delay_seconds:
            time.sleep(request_delay_seconds)

    discovered_dates = sorted({row["report_date"] for row in discovered})
    missing_discovered_dates = sorted(set(discovered_dates) - imported_dates)
    latest_report_date = max(discovered_dates) if discovered_dates else None
    if latest_report_date:
        from datetime import timedelta
        start = date(2026, 1, 1)
        end = date.fromisoformat(latest_report_date)
        expected_calendar_dates = {
            (start + timedelta(days=offset)).isoformat()
            for offset in range((end - start).days + 1)
        }
    else:
        expected_calendar_dates = set()
    indexed_date_set = set(discovered_dates)
    not_listed_dates = sorted(expected_calendar_dates - indexed_date_set)
    manifest = {
        "source_index_url": INDEX_URL,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "discovered_2026_post_count": len(discovered_dates),
        "discovered_report_dates": discovered_dates,
        "imported_distinct_report_dates": sorted(imported_dates),
        "imported_date_count": len(imported_dates),
        "previously_imported_dates_skipped": sorted(skipped_dates),
        "failed_discovered_dates": failures,
        "missing_from_discovered_posts": missing_discovered_dates,
        "calendar_dates_not_listed_by_index": not_listed_dates,
        "calendar_date_range_checked": (
            ["2026-01-01", latest_report_date] if latest_report_date else []
        ),
        "index_scope_note": (
            "The fetched IDSP index page exposed only the dated post links listed in discovered_report_dates. "
            "A date absent from this listing is not evidence that DHS did not publish a report for it."
        ),
        "request_delay_seconds": request_delay_seconds,
        "validation_status": "complete" if not failures else "completed_with_failures",
    }
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    (DAILY_DIR / "backfill_2026_status.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backfill-2026",
        action="store_true",
        help="Import each not-yet-imported 2026 report linked from the current official IDSP index page.",
    )
    parser.add_argument(
        "--max-reports",
        type=int,
        default=MAX_BACKFILL_REPORTS,
        help=f"Maximum dated 2026 posts to inspect (1-{MAX_BACKFILL_REPORTS}).",
    )
    args = parser.parse_args()
    if args.backfill_2026:
        try:
            result = backfill_2026_reports(max_reports=args.max_reports)
        except (ReportImportError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(
            f"SUCCESS: {result['imported_date_count']} distinct 2026 report dates imported or already retained."
        )
        print(f"Discovered linked reports: {result['discovered_2026_post_count']}")
        print(f"Not successfully imported among discovered posts: {result['missing_from_discovered_posts']}")
        print(f"Calendar dates not listed on the index: {result['calendar_dates_not_listed_by_index']}")
        print(f"Backfill manifest: {DAILY_DIR / 'backfill_2026_status.json'}")
        return 0 if result["validation_status"] == "complete" else 1
    try:
        snapshot = retrieve_latest_report()
    except ReportImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"SUCCESS: DHS IDSP report dated {snapshot['report_date']}")
    print(f"Source page: {snapshot['source_page_url']}")
    print(f"Source PDF: {snapshot['source_url']}")
    print(f"SHA-256: {snapshot['source_sha256']}")
    print(f"Statewide disease/subtype records: {len(snapshot['statewide_records'])}")
    print(
        "District reporting: "
        f"{len(snapshot['reported_district_codes'])}/14 districts; "
        f"{len(snapshot['district_records'])} disease/metric rows"
        if snapshot["daily_district_report_available"]
        else "District daily reporting unavailable"
    )
    print(f"Retrieved: {snapshot['retrieved_at_utc']}")
    print(snapshot["provisional_warning"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
