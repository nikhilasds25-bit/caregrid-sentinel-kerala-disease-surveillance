# Extended district-location weather data readiness: 2016–2025

**Acquisition date:** 2026-11-10
**Scope:** Historical Open-Meteo archive variables at the project's existing 14 representative district locations. This is a location-level model/reanalysis product, not station-observed or district-wide weather.

## Result

A separate, hash-bound weather candidate was acquired for all 14 project coordinates for 2016-01-01 through 2025-12-31. The batched API response covers 3,653 daily dates/location (51,142 location-days total). All six requested daily variables are present for all dates at all locations: **zero missing daily values** in the captured response. The monthly product has 1,680 unique district-location-month rows (14 × 120), all flagged `complete_month`, with zero missing monthly weather features.

This extends only the new candidate. Existing 2021–2024 weather files, reports, and pipeline outputs were not replaced.

## Source provenance

| Property | Captured value |
|---|---|
| Source | [Open-Meteo Historical Weather API](https://archive-api.open-meteo.com/v1/archive) |
| API documentation | [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) |
| Request interval / timezone | 2016-01-01 to 2025-12-31 / `Asia/Kolkata` |
| Retrieval mode | One 14-location batch request using the API's multi-location response |
| Server response date | `Tue, 10 Nov 2026 10:30:25 GMT` |
| Client retrieval time (UTC) | `2026-11-10T10:30:34+00:00` |
| HTTP status | 200 |
| Preserved batch snapshot | [`district_locations_batch_2016_2025.json`](../data/raw/open_meteo_weather_2016_2025/district_locations_batch_2016_2025.json) |
| Response-body size / SHA-256 | 2,118,721 bytes / `45f64f3278afb4b7f8eb4842deef58f8bb921c174352952fce519ef040107ecc` |
| Monthly candidate | [`kerala_district_representative_weather_monthly_2016_2025.csv`](../data/candidates/kerala_district_representative_weather_monthly_2016_2025.csv) |
| Candidate SHA-256 | `85364a93b25a741b2eaf5080f958fee764ac557821e03fe1e663e7c73518e175` |
| Metadata | [`kerala_district_representative_weather_monthly_2016_2025.metadata.json`](../data/candidates/kerala_district_representative_weather_monthly_2016_2025.metadata.json) |

The API response exposes requested/returned coordinates, elevation, timezone, units, generation time, and UTC offset. It does **not** expose an explicit model/reanalysis identifier or pinned product version. The exact product/model and revision behavior therefore remain unverified; no model name is inferred. The response had no ETag.

## Coordinate mapping

These are the existing project's exact requested representative coordinates. The weather output also retains Open-Meteo's returned grid coordinates and elevation. A single returned grid point is not a district-wide mean.

| District | Project location name | Requested latitude | Requested longitude | Returned latitude | Returned longitude | Elevation (m) |
|---|---|---:|---:|---:|---:|---:|
| Thiruvananthapuram | Thiruvananthapuram | 8.5241 | 76.9366 | 8.541301 | 76.921760 | 12 |
| Kollam | Kollam | 8.8932 | 76.6141 | 8.892795 | 76.632126 | 14 |
| Pathanamthitta | Pathanamthitta | 9.2648 | 76.7870 | 9.244288 | 76.808330 | 29 |
| Alappuzha | Alappuzha | 9.4981 | 76.3388 | 9.525483 | 76.370760 | 5 |
| Kottayam | Kottayam | 9.5916 | 76.5222 | 9.595782 | 76.515680 | 30 |
| Idukki | Idukki (Painavu) | 9.8494 | 76.9720 | 9.876977 | 77.019230 | 705 |
| Ernakulam | Ernakulam (Kochi) | 9.9816 | 76.2999 | 9.947276 | 76.299210 | 5 |
| Thrissur | Thrissur | 10.5276 | 76.2144 | 10.509666 | 76.202640 | 20 |
| Palakkad | Palakkad | 10.7867 | 76.6548 | 10.790861 | 76.631300 | 77 |
| Malappuram | Malappuram | 11.0510 | 76.0711 | 11.072056 | 76.104700 | 20 |
| Kozhikode | Kozhikode | 11.2588 | 75.7804 | 11.282952 | 75.827400 | 12 |
| Wayanad | Wayanad (Kalpetta) | 11.6085 | 76.0820 | 11.634446 | 76.085790 | 749 |
| Kannur | Kannur | 11.8745 | 75.3704 | 11.845343 | 75.403220 | 18 |
| Kasaragod | Kasaragod | 12.4996 | 74.9869 | 12.478031 | 75.040650 | 24 |

## Variables, units, and aggregation

| Daily variable | Unit | Monthly aggregation |
|---|---|---|
| `precipitation_sum` | mm | Sum daily precipitation. `precipitation_sum_mm` is only populated when all days in the month are present; observed partial sum and observed/missing day counts remain available separately. |
| `temperature_2m_mean` | °C | Arithmetic mean of available daily means |
| `temperature_2m_min` | °C | Arithmetic mean of available daily minima |
| `temperature_2m_max` | °C | Arithmetic mean of available daily maxima |
| `relative_humidity_2m_mean` | % | Arithmetic mean of available daily means |
| `dew_point_2m_mean` | °C | Arithmetic mean of available daily means |

Monthly values are calculated independently per representative location and district. No equal-weight statewide aggregation, district polygon average, interpolation, or population-weighting is performed in this candidate.

## Missingness and validation

| Check | Result |
|---|---|
| Daily date range | 3,653 consecutive dates/location, 14/14 locations |
| Daily variable nulls | 0 for each of the six variables |
| Monthly rows | 1,680; 120 months × 14 locations |
| Unique monthly keys | 1,680 unique `(period, district)` keys |
| Complete / partial / unavailable monthly rows | 1,680 / 0 / 0 |
| Missing monthly feature values | 0 for each feature |
| Expected / observed location-days | 51,142 / 51,142 |
| Returned coordinates/elevation | Present for all locations; returned grid points differ slightly from requested coordinates |

The reproducible builder validates dates, duplicate keys, requested and returned coordinate proximity, units, numeric values, precipitation non-negativity, humidity bounds, and per-variable missingness. The monthly schema keeps day counts so incomplete future refreshes cannot silently become full-month rainfall totals. It can reuse the preserved batch snapshot offline.

## Disease integration readiness and leakage

The candidate district names and month keys align exactly with the extended dashboard disease candidate:

- 1,680 unique district-month weather rows, all with complete weather features.
- 6,720 disease candidate rows (including explicit unavailable cells); all map to a weather district-month.
- 6,384 disease rows have cases and deaths available and thus match complete weather features.
- 336 2016 Suspected disease rows remain unavailable, even though corresponding weather is present. Weather must not turn them into zero-case outcomes.
- Four dashboard case category-month totals do not reconcile to the dashboard state totals; see the [disease audit](historical_2016_2025_data_audit.md). These flags remain relevant after joining.

This establishes a technically complete district-location-month join, not valid district-average climate exposure or comparable disease definitions. The API data are retrospective model/reanalysis estimates, not official station observations. Before spatial interpretation, compare against quality-controlled weather observations/gridded products and review district boundaries.

Historical observed/reanalysis weather is not known at a forecast origin. Using weather from the target month to predict disease in that month leaks future information. Climate-informed forecasting requires archived weather forecast vintages with issue times/lead times (or explicit scenarios), and should propagate weather forecast uncertainty.

## Readiness decision

The data can support a **retrospective exploratory association** over the same source-native dashboard disease periods, with the representative-point and source-version limitations explicit. It is not by itself a validated forecast covariate dataset, district-wide weather surface, or official station record. No disease model was trained and the old weather products were left untouched.
