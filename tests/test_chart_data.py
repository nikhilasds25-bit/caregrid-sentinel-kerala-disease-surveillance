import numpy as np
import pandas as pd
import pytest

from caregrid.chart_data import build_forecast_band_table, build_model_comparison


def make_row(model="negative_binomial_regression", disease="Dengue", horizon=1, phase="rolling_origin",
             actual=10, mean=8.0, o80=(2.0, 12.0), o95=(0.0, 20.0), cal=None,
             origin="2019-12", district="A"):
    row = {
        "model_name": model, "feature_set": "disease_history", "disease": disease, "district": district,
        "origin_period": origin, "target_period": f"2020-{horizon:02d}", "horizon": horizon,
        "validation_phase": phase, "actual": actual, "predictive_mean": mean,
        "prediction_interval_80_lower": o80[0], "prediction_interval_80_upper": o80[1],
        "prediction_interval_95_lower": o95[0], "prediction_interval_95_upper": o95[1],
    }
    if cal:
        row.update(cal)
    return row


CAL = {"cal_80_lower": 1.0, "cal_80_upper": 30.0, "cal_95_lower": 0.0, "cal_95_upper": 50.0,
       "calibration_n_scores": 40}


def test_band_source_uses_calibrated_only_where_available():
    out = build_forecast_band_table(pd.DataFrame([make_row(horizon=1, cal=CAL), make_row(horizon=2)]))
    a = out[out.horizon == 1].iloc[0]
    b = out[out.horizon == 2].iloc[0]
    assert a.band_source_80 == "calibrated" and a.display_80_upper == 30.0
    assert a.prediction_interval_80_upper == 12.0
    assert b.band_source_80 == "original" and b.display_80_upper == 12.0
    assert b.calibration_n_scores == 0


def test_direct_model_rows_keep_original_bands():
    out = build_forecast_band_table(
        pd.DataFrame([make_row()]), pd.DataFrame([make_row(model="direct_negative_binomial")])
    )
    d = out[out.model_name == "direct_negative_binomial"].iloc[0]
    assert d.band_source_80 == "original" and d.band_source_95 == "original"
    assert d.display_95_upper == 20.0


def test_holdout_is_labelled_descriptive_only_and_unknown_phase_raises():
    out = build_forecast_band_table(
        pd.DataFrame([make_row(), make_row(phase="final_2025", origin="2024-12")])
    )
    assert dict(zip(out.validation_phase, out.evidence_role)) == {
        "rolling_origin": "development_rolling_origin",
        "final_2025": "holdout_descriptive_only",
    }
    with pytest.raises(ValueError, match="phase"):
        build_forecast_band_table(pd.DataFrame([make_row(phase="mystery")]))


def test_duplicate_forecast_keys_raise():
    dup = pd.concat([pd.DataFrame([make_row()]), pd.DataFrame([make_row()])])
    with pytest.raises(ValueError, match="duplicate"):
        build_forecast_band_table(dup)


def test_caution_flags():
    rows = [make_row(model="poisson_regression"), make_row(horizon=9), make_row(horizon=8),
            make_row(disease="Leptospirosis", horizon=10)]
    out = build_forecast_band_table(pd.DataFrame(rows))
    assert out[out.model_name == "poisson_regression"].iloc[0].caution_poisson_intervals_too_narrow
    assert out[(out.disease == "Dengue") & (out.horizon == 9)].iloc[0].caution_dengue_horizon_9_12_undercoverage
    assert not out[(out.disease == "Dengue") & (out.horizon == 8)].iloc[0].caution_dengue_horizon_9_12_undercoverage
    assert not out[(out.disease == "Leptospirosis")].iloc[0].caution_dengue_horizon_9_12_undercoverage


def test_comparison_metrics_pooling_and_holdout_separation():
    rows = [
        make_row(district="A", actual=10, mean=8.0),   # error 2, inside both bands
        make_row(district="B", actual=20, mean=8.0),   # error 12, outside 80%, on the 95% upper edge
        make_row(district="A", phase="final_2025", origin="2024-12", actual=5, mean=5.0),
    ]
    comp = build_model_comparison(build_forecast_band_table(pd.DataFrame(rows)))
    dev = comp[(comp.evidence_role == "development_rolling_origin") & (comp.horizon_scope == "pooled")].iloc[0]
    assert dev.n_forecasts == 2 and dev.mae == 7.0
    assert dev.coverage_80_original == 0.5 and dev.coverage_95_original == 1.0
    assert dev.rmse == pytest.approx(np.sqrt(74))
    hold = comp[(comp.evidence_role == "holdout_descriptive_only") & (comp.horizon_scope == "pooled")].iloc[0]
    assert hold.n_forecasts == 1 and hold.mae == 0.0
    assert {"h1", "pooled"} <= set(comp.horizon_scope)


def test_comparison_has_no_ranking_or_best_column():
    comp = build_model_comparison(build_forecast_band_table(pd.DataFrame([make_row()])))
    assert not any("rank" in c or "best" in c for c in comp.columns)
