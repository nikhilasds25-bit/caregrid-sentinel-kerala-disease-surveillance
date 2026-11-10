import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from caregrid.build_extended_weather_candidate import (
    DISTRICT_LOCATIONS,
    METADATA_PATH,
    OUTPUT_PATH,
    VARIABLE_COLUMNS,
    ExtendedWeatherError,
    aggregate_monthly_weather,
    build_weather_candidate,
)

ROOT = Path(__file__).resolve().parents[1]


def test_extended_weather_candidate_has_complete_unique_location_month_grid():
    weather = pd.read_csv(OUTPUT_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    assert len(weather) == 10 * 12 * 14
    assert weather["period"].nunique() == 120
    assert weather["district"].nunique() == 14
    assert not weather.duplicated(["period", "district"]).any()
    assert set(weather["period"]) == {
        f"{year}-{month:02d}"
        for year in range(2016, 2026)
        for month in range(1, 13)
    }
    assert set(weather["district_location"]) == {
        location for location, _, _ in DISTRICT_LOCATIONS
    }
    assert set(weather["latitude"]) == {latitude for _, latitude, _ in DISTRICT_LOCATIONS}
    assert set(weather["longitude"]) == {
        longitude for _, _, longitude in DISTRICT_LOCATIONS
    }
    assert weather["weather_availability_status"].eq("complete_month").all()
    assert weather["days_expected"].between(28, 31).all()
    for column in VARIABLE_COLUMNS.values():
        assert weather[f"{column}_observed_days"].eq(weather["days_expected"]).all()
        assert weather[f"{column}_missing_days"].eq(0).all()
    assert metadata["monthly_records"] == 10 * 12 * 14
    assert len(metadata["location_responses"]) == 14
    assert all(
        location["retrieval_status"] == "success"
        for location in metadata["location_responses"]
    )
    assert all(
        location["response_body_sha256"]
        for location in metadata["location_responses"]
    )
    assert metadata["model_metadata_status"].startswith(
        "The API response did not expose"
    )
    import hashlib
    assert hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest() == (
        metadata["candidate_csv_sha256"]
    )


def test_weather_candidate_rebuilds_offline_and_batch_snapshot_hash_matches():
    import hashlib

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    raw_path = ROOT / metadata["raw_batch_snapshot"]
    envelope = json.loads(raw_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(envelope["response_body"].encode("utf-8")).hexdigest() == (
        metadata["batch_response_sha256"]
    )
    rebuilt, rebuilt_metadata = build_weather_candidate()
    saved = pd.read_csv(OUTPUT_PATH)
    pd.testing.assert_frame_equal(rebuilt, saved, check_dtype=False, check_exact=False)
    assert rebuilt_metadata["batch_response_sha256"] == metadata["batch_response_sha256"]


def test_monthly_aggregation_uses_sum_for_rain_and_mean_for_other_variables():
    days = pd.date_range("2016-01-01", "2016-01-31", freq="D")
    daily = pd.DataFrame({"date": days})
    for column in VARIABLE_COLUMNS.values():
        daily[column] = 2.0
    daily["district_location"] = DISTRICT_LOCATIONS[0][0]
    daily["district"] = "Thiruvananthapuram"
    daily["latitude"] = DISTRICT_LOCATIONS[0][1]
    daily["longitude"] = DISTRICT_LOCATIONS[0][2]

    monthly = aggregate_monthly_weather(daily)
    location_row = monthly[
        monthly["district_location"].eq(DISTRICT_LOCATIONS[0][0])
        & monthly["period"].eq("2016-01")
    ].iloc[0]
    assert location_row["precipitation_sum_mm"] == 62
    assert location_row["precipitation_observed_sum_mm"] == 62
    assert location_row["temperature_2m_mean_c"] == 2
    assert location_row["relative_humidity_2m_mean_pct"] == 2
    assert location_row["weather_availability_status"] == "complete_month"


def test_partial_precipitation_is_not_misreported_as_full_month_total():
    days = pd.date_range("2016-01-01", "2016-01-31", freq="D")
    daily = pd.DataFrame({"date": days})
    for column in VARIABLE_COLUMNS.values():
        daily[column] = 1.0
    daily.loc[0, "precipitation_sum_mm"] = np.nan
    daily["district_location"] = DISTRICT_LOCATIONS[0][0]
    daily["district"] = "Thiruvananthapuram"
    daily["latitude"] = DISTRICT_LOCATIONS[0][1]
    daily["longitude"] = DISTRICT_LOCATIONS[0][2]

    monthly = aggregate_monthly_weather(daily)
    row = monthly[
        monthly["district_location"].eq(DISTRICT_LOCATIONS[0][0])
        & monthly["period"].eq("2016-01")
    ].iloc[0]
    assert pd.isna(row["precipitation_sum_mm"])
    assert row["precipitation_observed_sum_mm"] == 30
    assert row["precipitation_sum_mm_missing_days"] == 1
    assert row["weather_availability_status"] == "partial_month"


def test_monthly_aggregation_rejects_duplicate_daily_location_key():
    days = pd.date_range("2016-01-01", "2016-01-31", freq="D")
    daily = pd.DataFrame({"date": list(days) + [days[0]]})
    for column in VARIABLE_COLUMNS.values():
        daily[column] = 1.0
    daily["district_location"] = DISTRICT_LOCATIONS[0][0]

    with pytest.raises(ExtendedWeatherError, match="duplicate date/location"):
        aggregate_monthly_weather(daily)
