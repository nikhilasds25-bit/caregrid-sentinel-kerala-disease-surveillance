import numpy as np
import pandas as pd
import pytest

from caregrid.multimodel.calibration import (
    calibrate_predictions,
    conformal_quantile,
    relative_interval_scores,
    summarize_calibration,
)

ORIGINS = ("2018-12", "2019-12", "2020-12", "2021-12")
CAL_COLUMNS = ["cal_80_lower", "cal_80_upper", "cal_95_lower", "cal_95_upper"]


def _frame(shift: float = 0.0, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for origin in ORIGINS:
        for district in range(10):
            rows.append({
                "disease": "Dengue",
                "model_name": "m",
                "feature_set": "f",
                "validation_phase": "rolling_origin",
                "origin_period": origin,
                "horizon": 1,
                "district": f"d{district}",
                "actual": float(rng.poisson(50 * (1 + shift))),
                "predictive_mean": 50.0,
                "prediction_interval_80_lower": 45.0,
                "prediction_interval_80_upper": 55.0,
                "prediction_interval_95_lower": 40.0,
                "prediction_interval_95_upper": 60.0,
            })
    return pd.DataFrame(rows)


def test_scores_negative_inside_and_positive_outside():
    scores = relative_interval_scores([50, 60, 30], [45, 45, 45], [55, 55, 55])
    assert scores[0] < 0
    assert scores[1] == pytest.approx(0.5)
    assert scores[2] == pytest.approx(1.5)


def test_quantile_requires_enough_scores():
    assert np.isnan(conformal_quantile([0.1] * 5, 0.8, min_scores=10))
    assert np.isnan(conformal_quantile([0.1] * 10, 0.95, min_scores=10))
    assert conformal_quantile(np.arange(10) / 10, 0.8, min_scores=10) == pytest.approx(0.8)


def test_first_origin_is_not_calibrated():
    out = calibrate_predictions(_frame(), min_scores=10)
    first = out[out["origin_period"].eq("2018-12")]
    assert first["cal_80_lower"].isna().all()
    assert (first["calibration_n_scores"] == 0).all()


def test_intervals_that_were_too_narrow_get_wider():
    out = calibrate_predictions(_frame(shift=0.5), min_scores=10)
    later = out[out["origin_period"].eq("2020-12")]
    assert (later["cal_80_upper"] > later["prediction_interval_80_upper"]).all()


def test_current_and_future_actuals_are_never_used():
    base = _frame()
    changed = base.copy()
    changed.loc[changed["origin_period"].eq("2021-12"), "actual"] = 10_000.0
    a = calibrate_predictions(base, min_scores=10)
    b = calibrate_predictions(changed, min_scores=10)
    np.testing.assert_allclose(a[CAL_COLUMNS].to_numpy(), b[CAL_COLUMNS].to_numpy(), equal_nan=True)


def test_earlier_origins_do_affect_later_calibration_only():
    base = _frame()
    changed = base.copy()
    changed.loc[changed["origin_period"].eq("2020-12"), "actual"] = 10_000.0
    a = calibrate_predictions(base, min_scores=10)
    b = calibrate_predictions(changed, min_scores=10)
    early = a["origin_period"].isin(["2018-12", "2019-12", "2020-12"])
    np.testing.assert_allclose(
        a.loc[early, CAL_COLUMNS].to_numpy(), b.loc[early, CAL_COLUMNS].to_numpy(), equal_nan=True
    )
    late = a["origin_period"].eq("2021-12")
    assert not np.allclose(a.loc[late, "cal_80_upper"], b.loc[late, "cal_80_upper"])


def test_summary_reports_before_and_after_on_same_rows():
    summary = summarize_calibration(calibrate_predictions(_frame(shift=0.5), min_scores=10))
    row = summary.iloc[0]
    assert row["n_80"] == 30
    assert row["coverage_after_80"] > row["coverage_before_80"]
    assert row["width_after_80"] > row["width_before_80"]


def test_missing_columns_raise():
    with pytest.raises(ValueError):
        calibrate_predictions(pd.DataFrame({"actual": [1.0]}))
