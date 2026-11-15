import numpy as np
import pandas as pd
import pytest

from caregrid.exceedance import (
    METHOD_ALL, METHOD_SEASON, build_threshold_table, compute_thresholds,
    score_exceedances, to_probability_records,
)


def make_obs(years=7):
    rows = []
    for i in range(years * 12):
        year, month = 2016 + i // 12, i % 12 + 1
        rows.append({"disease": "Dengue", "district": "A",
                     "period": f"{year}-{month:02d}", "cases": 100 if month == 7 else 10})
    return pd.DataFrame(rows)


def pick(th, method, month):
    return th[(th.method == method) & (th.target_calendar_month == month)].iloc[0]


def test_basic_and_season_thresholds_differ_for_a_seasonal_peak():
    th = compute_thresholds(make_obs(), origin="2021-12", min_values_season=12)
    basic, season = pick(th, METHOD_ALL, 7), pick(th, METHOD_SEASON, 7)
    assert basic.threshold == 10 and basic.n_reference_values == 72
    assert season.threshold == 100 and season.n_reference_values == 18
    assert basic.reference_start == "2016-01" and basic.reference_end == "2021-12"


def test_no_future_leakage():
    obs = make_obs()
    changed = obs.copy()
    changed.loc[changed.period > "2021-12", "cases"] = 9999
    a = compute_thresholds(obs, origin="2021-12", min_values_season=12)
    b = compute_thresholds(changed, origin="2021-12", min_values_season=12)
    pd.testing.assert_frame_equal(a, b)


def test_insufficient_reference_gives_no_threshold():
    th = compute_thresholds(make_obs(), origin="2016-12")
    row = pick(th, METHOD_ALL, 1)
    assert row.status == "insufficient_reference" and np.isnan(row.threshold)


def test_invalid_observations_raise():
    dup = pd.concat([make_obs(), make_obs().iloc[[0]]])
    with pytest.raises(ValueError, match="duplicate"):
        compute_thresholds(dup, origin="2021-12")


def make_draw_index():
    return pd.DataFrame([
        {"row_id": 0, "disease": "Dengue", "model_name": "m", "origin_period": "2021-12",
         "target_period": "2022-07", "horizon": 7, "district": "A", "actual": 100},
        {"row_id": 1, "disease": "Dengue", "model_name": "m", "origin_period": "2021-12",
         "target_period": "2022-02", "horizon": 2, "district": "A", "actual": 10},
    ])


def test_strict_inequality_and_probabilities():
    th = build_threshold_table(make_obs(), ["2021-12"], min_values_season=12)
    draws = np.array([[100] * 200, [5] * 100 + [11] * 100], dtype=np.int32)
    s = score_exceedances(make_draw_index(), draws, th)
    get = lambda r, m: s[(s.row_id == r) & (s.method == m)].iloc[0]
    # July: basic threshold 10 -> exceeds; season threshold 100 -> equal is NOT an exceedance
    assert get(0, METHOD_ALL).observed_exceedance == True  # noqa: E712
    assert get(0, METHOD_ALL).predicted_probability == 1.0
    assert get(0, METHOD_SEASON).observed_exceedance == False  # noqa: E712
    assert get(0, METHOD_SEASON).predicted_probability == 0.0
    # February: actual 10 equals the threshold 10 -> not an exceedance; half the draws are above
    assert get(1, METHOD_ALL).observed_exceedance == False  # noqa: E712
    assert get(1, METHOD_ALL).predicted_probability == 0.5


def test_insufficient_rows_have_no_probability():
    th = build_threshold_table(make_obs(), ["2021-12"])  # season default minimum 20 > 18
    draws = np.full((2, 200), 50, dtype=np.int32)
    s = score_exceedances(make_draw_index(), draws, th)
    bad = s[s.method == METHOD_SEASON]
    assert (bad.status == "insufficient_reference").all()
    assert bad.predicted_probability.isna().all() and bad.observed_exceedance.isna().all()


def test_misaligned_draws_raise():
    with pytest.raises(ValueError, match="align"):
        score_exceedances(make_draw_index(), np.zeros((3, 200), dtype=np.int32),
                          build_threshold_table(make_obs(), ["2021-12"]))


def test_records_are_labelled_exploratory():
    th = build_threshold_table(make_obs(), ["2021-12"], min_values_season=12)
    s = score_exceedances(make_draw_index(), np.full((2, 200), 50, dtype=np.int32), th)
    recs = to_probability_records(s)
    assert recs and all(r.calibration_status == "uncalibrated_exploratory" for r in recs)
