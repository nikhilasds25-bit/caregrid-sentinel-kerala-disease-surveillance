# Historical weather data-quality report

- Run timestamp (UTC): 2026-10-28T05:01:25+00:00
- Disease input: `data/processed/kerala_disease_monthly_2021_2024.csv`
- Weather API: [Open-Meteo Historical Weather API](https://archive-api.open-meteo.com/v1/archive)
- API documentation: [Historical Weather API documentation](https://open-meteo.com/en/docs/historical-weather-api)
- Requested daily variables: `precipitation_sum` (mm), `temperature_2m_mean`, `temperature_2m_min`, `temperature_2m_max` (°C).
- API timezone: `Asia/Kolkata`; the returned daily date is used as the local calendar date.
- Weather aggregation: monthly precipitation is each location's daily precipitation summed over the month, then averaged equally over the 14 representative locations. Monthly temperature metrics are calculated at each location, then averaged equally over those locations.
- The equal-weight location mean is a **statewide proxy**, not an official population-weighted statewide weather measurement.

## Representative location coordinates

| District representative | Latitude | Longitude |
| --- | --- | --- |
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

These approximate headquarters points are spatial representatives, not official weather stations, population-weighted centroids, or complete district-area averages.

## Validation results

| Check | Result | Details |
| --- | --- | --- |
| Disease schema and statewide scope | PASS | 96 source rows; Kerala/Statewide; source classifications retained. |
| Disease natural keys and disease coverage | PASS | No duplicate period/geography/disease/classification keys; each of 48 months has one row for each of two diseases. |
| Disease numeric values | PASS | Cases and deaths are numeric and nonnegative. |
| Disease month coverage/alignment | PASS | 2021-01 through 2024-12; no missing reporting months. |
| Disease classification consistency | PASS | Verified against source documentation without harmonization: 2021: reported_category_status_not_split; 2022: non_probable_category_probable_separate; 2023: Confirmed; 2024: Confirmed |
| Weather acquisition and response validation | PASS | 14 raw responses; 20454 daily location records; 2021-01-01 through 2024-12-31; no missing daily values. |
| Weather date/location keys | PASS | No duplicate date/location keys; each of 14 locations has 1461 distinct daily dates. |
| Weather units and physical checks | PASS | API units match mm and °C; precipitation is nonnegative; temperatures are finite, within -90 to 65 °C, and min ≤ mean ≤ max. |
| Disease/weather month alignment | PASS | 48 exact YYYY-MM matches; no unmatched months. |
| Monthly aggregation and missingness | PASS | All expected calendar days and 14 locations present per month; no values imputed. |
| Join keys and cardinality | PASS | Many-to-one YYYY-MM join; 96 records; no duplicate natural keys. |
| Measurement sanity after join | PASS | All weather measures are finite; precipitation ≥ 0; monthly temperatures remain in plausible API-validated range. |

## Caveats

- The API chooses its applicable historical reanalysis/model automatically; the model is not pinned in this script. The full response and retrieval metadata are retained in `data/raw/open_meteo_weather/` for provenance.
- API values and source data are preserved; no missing observations are replaced with zero or interpolated.
