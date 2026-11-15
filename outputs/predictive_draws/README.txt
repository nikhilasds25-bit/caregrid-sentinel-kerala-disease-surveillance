draws_200.npy: int32 array, shape (4704, 200) (rows x draws). Row i matches row_id i in draw_index.csv.
Seed 20261111. Negative binomial with dispersion recovered from saved variance.
Models: NB2 history-only and direct NB2 only. Draws are marginal per district-month;
they carry no correlation across districts or horizons. Approximate: 200 draws, so tail quantiles are noisy.
