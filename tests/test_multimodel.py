import numpy as np
import pandas as pd
import pytest

from caregrid.multimodel.data import DISEASES, WEATHER_FEATURES, load_model_ready_data
from caregrid.multimodel.models import (
    NegativeBinomialCountModel,
    PoissonCountModel,
    SeasonalNaiveModel,
)


def _synthetic_panel() -> pd.DataFrame:
    rows = []
    periods = pd.period_range("2016-01", "2021-12", freq="M")
    for district_index, district in enumerate(("Alpha", "Beta")):
        for period in periods:
            seasonal = 2 + np.sin((period.month - 1) * 2 * np.pi / 12)
            cases = max(0, int(round(4 + district_index * 3 + seasonal + (period.year - 2016) / 2)))
            rows.append({
                "disease": "Dengue",
                "district": district,
                "period": str(period),
                "period_start": period.to_timestamp(),
                "month_num": period.month,
                "trend_years": period.year + (period.month - 1) / 12 - 2016,
                "cases": cases,
                "precipitation_sum_mm": 80 + period.month,
                "temperature_2m_mean_c": 25 + period.month / 10,
                "temperature_2m_min_c": 20 + period.month / 10,
                "temperature_2m_max_c": 30 + period.month / 10,
                "relative_humidity_2m_mean_pct": 70 + period.month / 10,
                "dew_point_2m_mean_c": 18 + period.month / 10,
            })
    panel = pd.DataFrame(rows).sort_values(["district", "period_start"]).reset_index(drop=True)
    panel["lag_cases"] = panel.groupby("district")["cases"].shift(1)
    panel["log_lag_cases"] = np.log1p(panel["lag_cases"])
    panel["lag3_rainfall_sum_mm"] = panel.groupby("district")[
        "precipitation_sum_mm"
    ].transform(lambda values: values.shift(1).rolling(3, min_periods=3).sum())
    for feature in WEATHER_FEATURES:
        panel[f"lag1_{feature}"] = panel.groupby("district")[feature].shift(1)
    panel["lag1_temperature_range_c"] = (
        panel["lag1_temperature_2m_max_c"] - panel["lag1_temperature_2m_min_c"]
    )
    return panel


def test_candidate_loader_validates_confirmed_panel_and_source_hashes():
    panel, metadata = load_model_ready_data()
    assert set(panel["disease"].unique()) == set(DISEASES)
    assert panel.groupby("disease").size().to_dict() == {
        "Dengue": 1680,
        "Leptospirosis": 1680,
    }
    assert panel.groupby(["disease", "district"])["period"].nunique().eq(120).all()
    assert panel["cases"].isna().sum() == 0
    assert panel["cases"].eq(0).sum() == 224
    assert metadata["provenance"]["weather_matched_rows"] == 3360
    assert metadata["provenance"]["disease_candidate_sha256"]
    assert metadata["provenance"]["reconciliation_mismatch_cells"] == 4
    assert metadata["provenance"]["confirmed_reconciliation_mismatch_cells"] == 2


@pytest.mark.parametrize(
    "model",
    [PoissonCountModel(), NegativeBinomialCountModel(), SeasonalNaiveModel()],
)
def test_models_forecast_without_using_future_actuals(model):
    panel = _synthetic_panel()
    training = panel[panel["period"].le("2020-12")].copy()
    actuals = panel[panel["period"].ge("2021-01")].copy()
    model.fit(training, climate=False)
    predictions = model.forecast(
        training,
        horizon=12,
        climate=False,
        actuals=actuals,
    )
    assert len(predictions) == 24
    assert {row["period"] for row in predictions} == {
        str(period) for period in pd.period_range("2021-01", "2021-12", freq="M")
    }
    assert all(row["predictive_mean"] >= 0 for row in predictions)
    assert all(row["actual"] >= 0 for row in predictions)
    assert all(row["prediction_interval_95_lower"] <= row["prediction_interval_95_upper"] for row in predictions)


def test_climate_forecast_is_invariant_to_future_weather():
    panel = _synthetic_panel()
    training = panel[panel["period"].le("2020-12")].copy()
    actuals = panel[panel["period"].ge("2021-01")].copy()
    baseline = PoissonCountModel().fit(training, climate=True).forecast(
        training, 3, climate=True, actuals=actuals
    )
    altered_actuals = actuals.copy()
    altered_actuals.loc[:, list(WEATHER_FEATURES)] = -9999
    altered_actuals["cases"] = 0
    repeated = PoissonCountModel().fit(training, climate=True).forecast(
        training, 3, climate=True, actuals=altered_actuals
    )
    assert [row["predictive_mean"] for row in baseline] == pytest.approx(
        [row["predictive_mean"] for row in repeated]
    )
