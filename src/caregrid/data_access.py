"""Validated read-only access to the project's curated CareGrid datasets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATASETS = {
    "district_annual": Path("data/processed/kerala_district_annual_disease_2020_2024.csv"),
    "disease_monthly": Path("data/processed/kerala_disease_monthly_2021_2024.csv"),
    "weather_monthly": Path(
        "data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv"
    ),
    "disease_weather_monthly": Path(
        "data/processed/kerala_disease_weather_monthly_2021_2024.csv"
    ),
}
REQUIRED_COLUMNS = {
    "district_annual": {
        "year", "district", "district_code", "disease", "classification", "cases", "deaths",
        "temporal_granularity", "case_source_title", "case_source_url",
        "death_source_title", "death_source_url",
    },
    "disease_monthly": {
        "period", "year", "month_num", "month_name", "geography", "geography_level",
        "disease", "classification", "classification_note", "cases", "deaths",
        "source_file", "source_url",
    },
    "weather_monthly": {
        "period", "precipitation_sum_mm", "temperature_2m_mean_c",
        "temperature_2m_min_c", "temperature_2m_max_c", "weather_location_count",
        "weather_days_in_month", "aggregation_method", "weather_scope",
    },
    "disease_weather_monthly": {
        "period", "year", "month_num", "geography", "geography_level", "disease",
        "classification", "classification_note", "cases", "deaths", "source_file",
        "source_url", "precipitation_sum_mm", "temperature_2m_mean_c",
        "temperature_2m_min_c", "temperature_2m_max_c", "weather_location_count",
        "weather_scope",
    },
}


class DatasetUnavailable(Exception):
    """A required curated dataset is missing or fails a structural check."""


@dataclass(frozen=True)
class DataRepository:
    annual: pd.DataFrame
    monthly: pd.DataFrame
    weather: pd.DataFrame
    integrated: pd.DataFrame

    @classmethod
    def load(cls, root: Path = ROOT) -> "DataRepository":
        paths = {name: root / relative for name, relative in DATASETS.items()}
        missing = [path.relative_to(root).as_posix() for path in paths.values() if not path.is_file()]
        if missing:
            raise DatasetUnavailable(
                "Required project datasets are missing; no substitute data was generated: "
                + ", ".join(missing)
            )

        frames: dict[str, pd.DataFrame] = {}
        for name, path in paths.items():
            try:
                frame = pd.read_csv(path)
            except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
                raise DatasetUnavailable(f"Could not read {path.relative_to(root)}: {exc}") from exc
            missing_columns = sorted(REQUIRED_COLUMNS[name] - set(frame.columns))
            if missing_columns:
                raise DatasetUnavailable(
                    f"{path.relative_to(root)} is missing required columns: "
                    + ", ".join(missing_columns)
                )
            frames[name] = frame

        annual = frames["district_annual"].copy()
        monthly = frames["disease_monthly"].copy()
        weather = frames["weather_monthly"].copy()
        integrated = frames["disease_weather_monthly"].copy()

        _check_keys(annual, ["year", "district", "disease", "classification"], "annual district")
        _check_keys(
            monthly, ["period", "geography", "disease", "classification"], "monthly statewide"
        )
        _check_keys(weather, ["period"], "monthly weather")
        _check_keys(
            integrated,
            ["period", "geography", "disease", "classification"],
            "integrated monthly",
        )
        if not annual["temporal_granularity"].astype(str).eq("annual").all():
            raise DatasetUnavailable("Annual district dataset contains unexpected temporal granularity.")
        if not monthly["geography_level"].astype(str).eq("Statewide").all():
            raise DatasetUnavailable("Monthly disease dataset contains non-statewide rows.")
        if not integrated["geography_level"].astype(str).eq("Statewide").all():
            raise DatasetUnavailable("Integrated monthly dataset contains non-statewide rows.")

        for name, frame, cols in (
            ("annual district", annual, ["year", "cases", "deaths"]),
            ("statewide monthly disease", monthly, ["year", "month_num", "cases", "deaths"]),
            (
                "monthly weather",
                weather,
                [
                    "precipitation_sum_mm", "temperature_2m_mean_c", "temperature_2m_min_c",
                    "temperature_2m_max_c",
                ],
            ),
            (
                "integrated monthly",
                integrated,
                [
                    "year", "month_num", "cases", "deaths", "precipitation_sum_mm",
                    "temperature_2m_mean_c",
                ],
            ),
        ):
            for col in cols:
                converted = pd.to_numeric(frame[col], errors="coerce")
                if converted.isna().any() or not np.isfinite(converted.to_numpy(dtype=float)).all():
                    raise DatasetUnavailable(f"{name} dataset has invalid numeric values in {col}.")
        for name, frame in (("annual district", annual), ("statewide monthly disease", monthly)):
            if (frame[["cases", "deaths"]].apply(pd.to_numeric, errors="coerce") < 0).any().any():
                raise DatasetUnavailable(f"{name} dataset contains negative case or death counts.")
        if (monthly["deaths"] > monthly["cases"]).any() or (annual["deaths"] > annual["cases"]).any():
            raise DatasetUnavailable("Disease datasets contain deaths greater than reported cases.")
        if (weather["precipitation_sum_mm"] < 0).any():
            raise DatasetUnavailable("Monthly weather dataset contains negative precipitation.")
        if not (
            (weather["temperature_2m_min_c"] <= weather["temperature_2m_mean_c"])
            & (weather["temperature_2m_mean_c"] <= weather["temperature_2m_max_c"])
        ).all():
            raise DatasetUnavailable("Monthly weather temperature measures are inconsistent.")
        for frame_name, frame in (("statewide monthly disease", monthly), ("monthly weather", weather)):
            period_dates = pd.to_datetime(
                frame["period"].astype(str) + "-01", format="%Y-%m-%d", errors="coerce"
            )
            if period_dates.isna().any():
                raise DatasetUnavailable(f"{frame_name} dataset contains invalid month keys.")
            if "year" in frame and not (period_dates.dt.year == frame["year"]).all():
                raise DatasetUnavailable(f"{frame_name} dataset has inconsistent year/month keys.")

        if not set(monthly["classification"].astype(str)).issubset(
            set(integrated["classification"].astype(str))
        ):
            raise DatasetUnavailable("Integrated monthly data lost source classifications.")
        if set(monthly["period"].astype(str)) != set(weather["period"].astype(str)):
            raise DatasetUnavailable("Monthly statewide disease and weather coverage differs.")
        if len(monthly) != len(integrated):
            raise DatasetUnavailable("Integrated monthly row count differs from disease source.")
        source_cols = [
            "period", "geography", "geography_level", "disease", "classification", "cases", "deaths",
        ]
        left = monthly[source_cols].sort_values(source_cols[:5]).reset_index(drop=True)
        right = integrated[source_cols].sort_values(source_cols[:5]).reset_index(drop=True)
        if not left.equals(right):
            raise DatasetUnavailable(
                "Integrated monthly file does not exactly preserve statewide disease records."
            )
        return cls(annual=annual, monthly=monthly, weather=weather, integrated=integrated)

    def status(self) -> dict[str, Any]:
        return {
            "status": "available",
            "datasets": {
                name: {
                    "path": relative.as_posix(),
                    "rows": len(getattr(self, _frame_name(name))),
                }
                for name, relative in DATASETS.items()
            },
        }


def _frame_name(dataset_name: str) -> str:
    return {
        "district_annual": "annual",
        "disease_monthly": "monthly",
        "weather_monthly": "weather",
        "disease_weather_monthly": "integrated",
    }[dataset_name]


def _check_keys(frame: pd.DataFrame, keys: list[str], name: str) -> None:
    if frame[keys].isna().any().any():
        raise DatasetUnavailable(f"{name} dataset has missing natural-key values.")
    if frame.duplicated(keys).any():
        raise DatasetUnavailable(f"{name} dataset has duplicate natural keys: {keys}.")
