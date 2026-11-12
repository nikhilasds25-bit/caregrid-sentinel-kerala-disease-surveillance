import pandas as pd
import pytest

from caregrid.outbreak_detection import (
    CusumDetector,
    EwmaDetector,
    load_confirmed_observations,
)

BASELINE = ("2016-01", "2018-12")


def make_obs(spike=None, n_years=6):
    rows = []
    for i in range(n_years * 12):
        year, month = 2016 + i // 12, i % 12 + 1
        period = f"{year}-{month:02d}"
        cases = 20 + (10 if 6 <= month <= 8 else 0) + (i % 3)
        if spike and period == spike[0]:
            cases = spike[1]
        rows.append({"disease": "Dengue", "district": "A", "period": period, "cases": cases})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("detector_cls", [EwmaDetector, CusumDetector])
def test_spike_is_flagged_and_quiet_period_is_not(detector_cls):
    recs = detector_cls().detect(make_obs(spike=("2021-07", 200)), baseline_period=BASELINE)
    flagged = {r.period for r in recs if r.unusual_activity_flag}
    assert "2021-07" in flagged
    assert all(p >= "2021-07" for p in flagged)
    assert min(r.period for r in recs) == "2019-01"  # scoring starts after the baseline


@pytest.mark.parametrize("detector_cls", [EwmaDetector, CusumDetector])
def test_no_future_leakage(detector_cls):
    full = detector_cls().detect(make_obs(spike=("2021-07", 200)), baseline_period=BASELINE)
    obs = make_obs(spike=("2021-07", 200))
    truncated = detector_cls().detect(obs[obs.period <= "2020-12"], baseline_period=BASELINE)
    assert truncated == [r for r in full if r.period <= "2020-12"]


def test_zero_counts_do_not_break_detectors():
    obs = make_obs()
    obs.loc[obs.period == "2020-03", "cases"] = 0
    for cls in (EwmaDetector, CusumDetector):
        recs = cls().detect(obs, baseline_period=BASELINE)
        assert all(r.anomaly_score == r.anomaly_score for r in recs)  # no NaN


def test_missing_month_raises():
    obs = make_obs()
    obs = obs[obs.period != "2020-05"]
    with pytest.raises(ValueError, match="consecutive"):
        EwmaDetector().detect(obs, baseline_period=BASELINE)


def test_short_baseline_raises():
    with pytest.raises(ValueError, match="at least"):
        EwmaDetector().detect(make_obs(), baseline_period=("2016-01", "2017-12"))


def test_loader_keeps_only_available_confirmed(tmp_path):
    csv = tmp_path / "obs.csv"
    pd.DataFrame(
        [
            {"disease": "Dengue", "district": "A", "period": "2016-01", "classification": "Confirmed", "cases_available": True, "cases": 4.0},
            {"disease": "Dengue", "district": "A", "period": "2016-01", "classification": "Suspected", "cases_available": True, "cases": 9.0},
            {"disease": "Dengue", "district": "A", "period": "2016-02", "classification": "Confirmed", "cases_available": False, "cases": None},
        ]
    ).to_csv(csv, index=False)
    out = load_confirmed_observations(csv)
    assert len(out) == 1 and out.iloc[0].cases == 4
