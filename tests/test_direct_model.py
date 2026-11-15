import numpy as np
import pandas as pd
import pytest

from caregrid.multimodel.direct_model import DirectNegativeBinomialModel, build_direct_training
from caregrid.multimodel.models import CountModelError


def make_panel():
    rng = np.random.default_rng(0)
    rows = []
    for district in ("A", "B"):
        for period in pd.period_range("2016-01", "2020-12", freq="M"):
            mean = 60 + 30 * np.sin(period.month / 12 * 2 * np.pi)
            rows.append({
                "district": district,
                "period": str(period),
                "period_start": period.to_timestamp(),
                "month_num": period.month,
                "trend_years": period.year + (period.month - 1) / 12 - 2016,
                "cases": float(rng.poisson(mean)),
            })
    return pd.DataFrame(rows)


def make_actuals():
    rows = []
    for district in ("A", "B"):
        for period in pd.period_range("2021-01", "2021-12", freq="M"):
            rows.append({"district": district, "period": str(period), "cases": 70.0})
    return pd.DataFrame(rows)


def test_lag_is_exactly_h_months_earlier():
    panel = make_panel()
    table = build_direct_training(panel, 5)
    row = table[(table.district == "B") & (table.period == "2020-06")].iloc[0]
    expected = panel[(panel.district == "B") & (panel.period == "2020-01")]["cases"].iloc[0]
    assert row["lag_cases"] == expected


def test_missing_month_drops_row_and_is_not_zero():
    panel = make_panel()
    panel = panel[~((panel.district == "A") & (panel.period == "2019-05"))]
    table = build_direct_training(panel, 3)
    assert not ((table.district == "A") & (table.period == "2019-08")).any()
    assert (table["lag_cases"] > 0).all()


def test_forecast_shape_and_keys():
    panel = make_panel()
    model = DirectNegativeBinomialModel().fit(panel)
    out = model.forecast(panel, 12, actuals=make_actuals())
    assert len(out) == 2 * 12
    assert {r["horizon"] for r in out} == set(range(1, 13))
    assert "prediction_interval_80_lower" in out[0] and "predictive_log_score" in out[0]


def test_forecast_does_not_use_actuals():
    panel = make_panel()
    model = DirectNegativeBinomialModel().fit(panel)
    first = model.forecast(panel, 12, actuals=make_actuals())
    changed = make_actuals()
    changed["cases"] = 500.0
    second = model.forecast(panel, 12, actuals=changed)
    assert [r["predictive_mean"] for r in first] == [r["predictive_mean"] for r in second]


def test_climate_is_rejected():
    with pytest.raises(CountModelError):
        DirectNegativeBinomialModel().fit(make_panel(), climate=True)
