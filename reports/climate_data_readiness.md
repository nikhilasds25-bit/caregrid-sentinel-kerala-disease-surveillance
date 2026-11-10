# Climate data readiness for Kerala disease surveillance

**Investigation date:** 2026-11-10
**Scope:** Existing weather files, spatial/temporal coverage, humidity availability, historical archive acquisition, and forecast-origin leakage. No climate-informed disease model was implemented.

## Executive decision

The project has a reproducible 2021–2024 daily precipitation and temperature archive at 14 representative Kerala district locations. Relative humidity and dew point are also available from the same Open-Meteo archive API for all 14 points over that existing period, and all requested humidity/dew-point daily entries were present in the availability check.

This is **not yet sufficient for defensible climate-informed forecasting**. The locations are approximate district-headquarters points, not station observations or district-wide averages; the historical API's selected model is not pinned in the existing pipeline; current saved weather stops at 2024; and realized historical weather is not known at a forecast origin. A transient 2016–2025 request succeeded for one representative location, but equivalent complete downloads/validation have not been performed or saved for all 14.

## Current weather holdings

| Item | Verified state |
|---|---|
| Source | [Open-Meteo Historical Weather API](https://archive-api.open-meteo.com/v1/archive); existing request implementation in [`integrate_historical_weather.py`](../src/caregrid/integrate_historical_weather.py) |
| Saved daily coverage | 2021-01-01 through 2024-12-31, 1,461 dates per location |
| Spatial coverage | 14 approximate district-headquarters locations; not district-wide grids or official station records |
| Saved variables | `precipitation_sum` (mm), `temperature_2m_mean`, `temperature_2m_min`, `temperature_2m_max` (°C) |
| Existing monthly output | Equal-weight aggregation over the 14 locations, producing a statewide proxy; it is not population weighted |
| Existing humidity fields | Not included in the saved pipeline output |
| Existing data limitations | The API-selected historical model is not pinned; the representative point does not capture within-district variation or elevation gradients |

The 14 coordinates used by the existing pipeline are:

| District/location | Latitude | Longitude |
|---|---:|---:|
| Thiruvananthapuram | 8.5241 | 76.9366 |
| Kollam | 8.8932 | 76.6141 |
| Pathanamthitta | 9.2648 | 76.7870 |
| Alappuzha | 9.4981 | 76.3388 |
| Kottayam | 9.5916 | 76.5222 |
| Idukki (Painavu) | 9.8494 | 76.9720 |
| Ernakulam (Kochi) | 9.9816 | 76.2999 |
| Thrissur | 10.5276 | 76.2144 |
| Palakkad | 10.7867 | 76.6548 |
| Malappuram | 11.0510 | 76.0711 |
| Kozhikode | 11.2588 | 75.7804 |
| Wayanad (Kalpetta) | 11.6085 | 76.0820 |
| Kannur | 11.8745 | 75.3704 |
| Kasaragod | 12.4996 | 74.9869 |

The currently saved dataset aligns in time with disease data for 2021–2024. The new dashboard candidate covers 2023–2025, so only 2023–2024 overlap with currently saved weather. No 2025 14-location weather panel is saved.

## Humidity and additional-variable availability

The Open-Meteo archive API returned `relative_humidity_2m_mean` (%) and `dew_point_2m_mean` (°C) for all 14 existing coordinates over 2021-01-01–2024-12-31: 1,461 daily entries per location and variable, with no null values in the checked responses. These values are API-provided gridded/model-derived historical estimates, not official ground-station observations.

A separate availability-only request for the Alappuzha representative coordinate (9.4981, 76.3388), 2016-01-01–2025-12-31, returned 3,653 daily entries and no nulls for precipitation sum, temperature mean/min/max, relative humidity mean, or dew point mean. This was a transient check; no new weather records were added to project data. It does not prove complete coverage for every location over that expanded interval.

Humidity and dew point are therefore **acquirable** for the selected API/model and locations. Additional possible variables (for example soil moisture or radiation) were not tested in this investigation. No official district-month weather observations or station-to-district mapping were verified. An IMD station/gridded-data investigation would be needed before calling weather observations authoritative.

## Spatial and temporal join readiness

The existing 14-point set is useful for exploratory retrospective associations if its proxy nature is retained. It is not a district mean: a single location cannot represent coastal-to-inland gradients, topography, or within-district rainfall. The current statewide monthly weather proxy equally averages locations, while the candidate disease data are district-month counts. Joining that statewide proxy to every district would duplicate a single exposure and misstate spatial information.

Before creating a district-month climate panel:

1. Acquire and preserve daily weather for all 14 points over the full disease interval being considered (potentially 2016–2025), recording endpoint, query, retrieval time, returned coordinates, units, response hash, and model/dataset choice.
2. Validate returned dates, missingness, bounds, and timezone/day-to-month aggregation rules; retain the raw point-level series.
3. Use a documented district identifier/boundary version and do not call representative-point values district-wide observations.
4. Compare available precipitation/temperature/humidity against suitable local station or official gridded sources where accessible.
5. Keep district counts, any population denominators, and weather inputs at compatible geographic and temporal resolutions.

## Forecast-origin availability and leakage

Historical archive values describe past weather estimates and cannot be treated as future-known covariates in a real forecast. In retrospective evaluation, using realized weather from the target period as a predictor leaks information unless the declared task is a post-hoc association/nowcast.

For climate-informed forecasts, every weather predictor must be available at the forecast origin: use archived weather-forecast vintages with issue times and lead times, or a clearly specified weather scenario. Do not use future observed/reanalysis values to score a disease forecast as if they were known. Weather forecast uncertainty should be propagated into disease predictive uncertainty.

## Readiness decision

| Intended use | Status | Reason |
|---|---|---|
| Descriptive statewide weather series, 2021–2024 | Available with caveats | Complete saved daily precipitation/temperature at 14 points; statewide monthly output is an equal-weight proxy. |
| Exploratory humidity availability | Confirmed for existing 14 points/2021–2024 | API returned complete relative humidity and dew point in the availability check; no humidity series is yet persisted in the project pipeline. |
| District-month weather for 2023–2024 | Partial/representative only | Point-level API data can align to districts, but it is not district areal weather or station-observed data; no integrated dataset was created. |
| District-month weather for 2025 | Not yet acquired as a 14-location panel | One-location 2016–2025 availability check is insufficient to validate all districts. |
| Climate-informed forecasting | Not ready | No pinned/validated climate dataset, no forecast-origin weather vintages, short overlap, and unresolved disease comparability. |

No weather data, climate features, or disease-weather model were added or trained.
