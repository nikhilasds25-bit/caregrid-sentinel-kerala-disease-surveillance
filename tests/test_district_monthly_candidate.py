import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from caregrid.build_district_monthly_candidate import (
    METADATA_PATH,
    SOURCE_PATH,
    CandidateDataError,
    build_candidate_frame,
    load_candidate_frame,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = (
    ROOT / "data" / "candidates" / "kerala_district_monthly_disease_dashboard_2023_2025.csv"
)


def test_candidate_has_complete_source_native_district_month_keys():
    candidate = pd.read_csv(CANDIDATE_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    expected_periods = [
        f"{year}-{month:02d}"
        for year in range(2023, 2026)
        for month in range(1, 13)
    ]

    assert len(candidate) == 36 * 14 * 2 * 2
    assert sorted(candidate["period"].unique().tolist()) == expected_periods
    assert candidate["district"].nunique() == 14
    assert set(candidate["disease"]) == {"Dengue", "Leptospirosis"}
    assert set(candidate["classification"]) == {"Confirmed", "Suspected"}
    assert not candidate.duplicated(
        ["period", "district", "disease", "classification"]
    ).any()
    assert candidate["cases"].notna().all()
    assert candidate["deaths"].notna().all()
    assert (candidate[["cases", "deaths"]] >= 0).all().all()
    assert candidate["temporal_granularity"].eq("monthly").all()
    assert set(candidate["source_case_metric_key"]) == {"C"}
    assert set(candidate["source_death_metric_key"]) == {"D"}
    assert set(candidate["source_category_code"]) == {
        "DENGUE|Con",
        "DENGUE|Sus",
        "LEPTO|Con",
        "LEPTO|Sus",
    }
    assert candidate["source_sha256"].eq(metadata["sha256"]).all()
    assert candidate["source_url"].eq(metadata["source_url"]).all()


def test_candidate_rebuild_matches_hash_bound_snapshot():
    built = load_candidate_frame(SOURCE_PATH, METADATA_PATH)
    saved = pd.read_csv(CANDIDATE_PATH)
    pd.testing.assert_frame_equal(built, saved, check_dtype=False)


def test_candidate_rejects_district_aggregate_mismatch():
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    payload["2023"]["ALAPPUZHA"]["Jan"]["DENGUE|Con"]["C"] += 1

    with pytest.raises(CandidateDataError, match="does not match KERALA aggregate"):
        build_candidate_frame(payload, metadata)


def test_candidate_rejects_missing_month():
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    del payload["2024"]["KOLLAM"]["May"]

    with pytest.raises(CandidateDataError, match="missing monthly coverage"):
        build_candidate_frame(payload, metadata)


def test_candidate_rejects_modified_snapshot(tmp_path):
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    metadata["sha256"] = "0" * 64
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(CandidateDataError, match="source snapshot hash mismatch"):
        load_candidate_frame(SOURCE_PATH, metadata_path)
