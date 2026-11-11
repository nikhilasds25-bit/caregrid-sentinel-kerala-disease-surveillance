"""Make predictive draws for NB2 and direct NB2 from saved mean/variance.

Writes ONLY to outputs/predictive_draws/ (new folder, never overwrites).
NB2: variance = mean + alpha * mean^2, so alpha = (variance - mean) / mean^2.
"""
from pathlib import Path
import numpy as np
import pandas as pd

N_DRAWS = 200
SEED = 20261111
out = Path("outputs/predictive_draws")
if out.exists():
    raise SystemExit(f"STOP: {out} already exists. Nothing written.")

a = pd.read_csv("reports/multimodel_experiment/predictions.csv")
b = pd.read_csv("reports/direct_model_experiment/direct_predictions.csv")
a = a[(a.model_name == "negative_binomial_regression") & (a.feature_set == "disease_history")]
p = pd.concat([a, b], ignore_index=True)
p = p.drop(columns=["experiment_spec"], errors="ignore").reset_index(drop=True)

mean = p.predictive_mean.to_numpy(float)
var = p.predictive_variance.to_numpy(float)
alpha = (var - mean) / np.maximum(mean, 1e-9) ** 2
if not np.isfinite(alpha).all() or (alpha <= 0).any():
    raise SystemExit("STOP: could not recover a positive dispersion for every row.")
size = 1.0 / alpha
prob = size / (size + mean)

rng = np.random.default_rng(SEED)
draws = rng.negative_binomial(size[:, None], prob[:, None], size=(len(p), N_DRAWS))

lo80, hi80 = np.percentile(draws, [10, 90], axis=1)
err_lo = np.abs(lo80 - p.prediction_interval_80_lower.to_numpy(float))
err_hi = np.abs(hi80 - p.prediction_interval_80_upper.to_numpy(float))
rel = (np.maximum(err_lo, err_hi) / np.maximum(p.predictive_mean.to_numpy(float), 1.0))
print("median relative gap between sampled and saved 80% bounds:", round(float(np.median(rel)), 3))
print("95th percentile of that gap:", round(float(np.percentile(rel, 95)), 3))
if np.median(rel) > 0.15:
    raise SystemExit("STOP: sampled intervals do not match saved intervals. Nothing written.")

keys = ["disease", "model_name", "feature_set", "validation_phase", "origin_period",
        "target_period", "horizon", "district", "actual", "predictive_mean"]
out.mkdir(parents=True)
meta = p[keys].copy()
meta.insert(0, "row_id", np.arange(len(p)))
meta.to_csv(out / "draw_index.csv", index=False)
np.save(out / "draws_200.npy", draws.astype(np.int32))
(out / "README.txt").write_text(
    f"draws_200.npy: int32 array, shape {draws.shape} (rows x draws). Row i matches row_id i in draw_index.csv.\n"
    f"Seed {SEED}. Negative binomial with dispersion recovered from saved variance.\n"
    "Models: NB2 history-only and direct NB2 only. Draws are marginal per district-month;\n"
    "they carry no correlation across districts or horizons. Not committed to git (size).\n",
    encoding="utf-8",
)
print("rows:", len(p), "draws per row:", N_DRAWS, "saved to", out)
