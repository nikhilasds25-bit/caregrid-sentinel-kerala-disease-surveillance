import copy
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from caregrid.build_extended_disease_candidate import (
    DISTRICT_ANNUAL_COMPARISON_PATH,
    DASHBOARD_METADATA_PATH,
    DASHBOARD_SOURCE_PATH,
    METADATA_OUTPUT_PATH,
    OUTPUT_PATH,
    RECONCILIATION_PATH,
    ExtendedDiseaseDataError,
    build_extended_candidate,
    load_extended_candidate,
)

ROOT = Path(__file__).resolve().parents[1]


def _source():
    return load_extended_candidate(DASHBOARD_SOURCE_PATH, DASHBOARD_METADATA_PATH)


def test_extended_candidate_has_complete_dense_grid_and_unique_keys():
    candidate = pd.read_csv(OUTPUT_PATH)
    expected_periods = [
        f"{year}-{month:02d}"
        for year in range(2016, 2026)
        for month in range(1, 13)
    ]

    assert len(candidate) == 10 * 12 * 14 * 4
    assert sorted(candidate["period"].unique().tolist()) == expected_periods
    assert candidate["district"].nunique() == 14
    assert set(candidate["disease"]) == {"Dengue", "Leptospirosis"}
    assert set(candidate["classification"]) == {"Confirmed", "Suspected"}
    assert not candidate.duplicated(
        ["period", "district", "disease", "classification"]
    ).any()
    assert candidate["source_sha256"].nunique() == 1
    assert candidate["source_category_available"].sum() == 10 * 12 * 14 * 4 - 336
    unavailable = candidate[candidate["availability_status"].eq(
        "unavailable_source_category_absent"
    )]
    assert len(unavailable) == 336
    assert unavailable["year"].eq(2016).all()
    assert unavailable["classification"].eq("Suspected").all()
    assert unavailable[["cases", "deaths"]].isna().all().all()
    explicit_zeroes = candidate[
        candidate["availability_status"].eq("available")
        & candidate["cases"].eq(0)
    ]
    assert len(explicit_zeroes) > 0
    assert explicit_zeroes["cases_available"].all()


def test_candidate_rebuild_matches_saved_output_and_hash_metadata():
    payload, metadata = _source()
    candidate, reconciliation = build_extended_candidate(payload, metadata)
    saved = pd.read_csv(OUTPUT_PATH)
    saved_reconciliation = pd.read_csv(RECONCILIATION_PATH)
    dataset_metadata = json.loads(METADATA_OUTPUT_PATH.read_text(encoding="utf-8"))
    pd.testing.assert_frame_equal(candidate, saved, check_dtype=False)
    pd.testing.assert_frame_equal(reconciliation, saved_reconciliation, check_dtype=False)
    assert hashlib.sha256(DASHBOARD_SOURCE_PATH.read_bytes()).hexdigest() == metadata["sha256"]
    assert hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest() == (
        dataset_metadata["candidate_sha256"]
    )
    assert dataset_metadata["source_sha256"] == metadata["sha256"]


def test_reconciliation_preserves_all_known_district_state_disagreements():
    reconciliation = pd.read_csv(RECONCILIATION_PATH)
    mismatches = reconciliation[
        reconciliation["cases_reconciliation_status"].eq("mismatch")
        | reconciliation["deaths_reconciliation_status"].eq("mismatch")
    ]
    assert len(mismatches) == 4
    assert set(zip(mismatches["period"], mismatches["source_category_code"])) == {
        ("2016-05", "DENGUE|Con"),
        ("2017-07", "LEPTO|Sus"),
        ("2022-10", "DENGUE|Sus"),
        ("2022-10", "LEPTO|Con"),
    }
    assert len(reconciliation) == 10 * 12 * 4
    assert reconciliation["cases_reconciliation_status"].eq("match").sum() == 452
    assert reconciliation["deaths_reconciliation_status"].eq("match").sum() == 456


def test_dhs_monthly_comparison_preserves_2025_discrepancies_and_absent_periods():
    comparison = pd.read_csv(
        ROOT / "data" / "candidates" / "dhs_dashboard_monthly_comparison_2021_2025.csv"
    )
    assert len(comparison) == 5 * 12 * 2 * 2
    assert not comparison.duplicated(
        ["period", "disease", "dashboard_classification"]
    ).any()
    available = comparison[
        comparison["comparison_status"].eq("compared_label_semantics_unverified")
    ]
    assert available[
        (available["year"] == 2025)
        & (available["disease"] == "Dengue")
        & (available["dashboard_classification"] == "Confirmed")
    ]["deaths_difference_dashboard_minus_dhs"].sum() == -2
    assert available[
        (available["year"] == 2025)
        & (available["disease"] == "Leptospirosis")
        & (available["dashboard_classification"] == "Confirmed")
    ]["cases_difference_dashboard_minus_dhs"].sum() == 1
    assert comparison[
        (comparison["year"] == 2022)
        & (comparison["dashboard_classification"] == "Suspected")
    ]["comparison_status"].eq("no_dhs_monthly_category_counterpart").all()
    differences = available[available["year"] == 2025]
    mismatch_fields = int(
        differences["cases_difference_dashboard_minus_dhs"].fillna(0).ne(0).sum()
        + differences["deaths_difference_dashboard_minus_dhs"].fillna(0).ne(0).sum()
    )
    assert mismatch_fields == 30


def test_annual_district_comparison_retains_2025_missing_districts_and_differences():
    comparison = pd.read_csv(DISTRICT_ANNUAL_COMPARISON_PATH)
    assert len(comparison) == 6 * 14 * 2 * 2
    assert not comparison.duplicated(
        ["year", "district", "disease", "dashboard_classification"]
    ).any()
    missing_2025 = comparison[
        (comparison["year"] == 2025)
        & comparison["comparison_status"].eq("no_dhs_district_annual_counterpart")
    ]
    assert set(missing_2025["district"]) == {"Alappuzha"}
    assert len(missing_2025) == 4
    dengue_death_diff = comparison[
        (comparison["year"] == 2025)
        & (comparison["disease"] == "Dengue")
        & (comparison["dashboard_classification"] == "Confirmed")
    ]["deaths_difference_dashboard_minus_dhs"].sum()
    assert dengue_death_diff == -2
    annual = pd.read_csv(DISTRICT_ANNUAL_COMPARISON_PATH)
    annual_mismatch_count = int(
        annual["cases_difference_dashboard_minus_dhs"].fillna(0).ne(0).sum()
        + annual["deaths_difference_dashboard_minus_dhs"].fillna(0).ne(0).sum()
    )
    assert annual_mismatch_count == 23


def test_candidate_rejects_modified_snapshot_hash(tmp_path):
    _, metadata = _source()
    source_path = tmp_path / "source.json"
    metadata_path = tmp_path / "metadata.json"
    source_path.write_bytes(DASHBOARD_SOURCE_PATH.read_bytes() + b" ")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ExtendedDiseaseDataError, match="snapshot hash mismatch"):
        load_extended_candidate(source_path, metadata_path)


def test_candidate_rejects_invalid_reported_count():
    payload, metadata = _source()
    payload = copy.deepcopy(payload)
    payload["2017"]["KOLLAM"]["Jan"]["DENGUE|Con"]["C"] = -1
    with pytest.raises(ExtendedDiseaseDataError, match="non-negative integer"):
        build_extended_candidate(payload, metadata)
