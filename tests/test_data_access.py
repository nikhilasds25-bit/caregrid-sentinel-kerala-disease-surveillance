from pathlib import Path

import pandas as pd
import pytest

from caregrid.data_access import DataRepository, DatasetUnavailable


ROOT = Path(__file__).resolve().parents[1]


def test_loads_validated_project_data_and_preserves_monthly_rows():
    repository = DataRepository.load(ROOT)

    assert len(repository.annual) == 280
    assert len(repository.monthly) == 96
    assert len(repository.weather) == 48
    assert len(repository.integrated) == 96
    assert set(repository.monthly["classification"]) == {
        "reported_category_status_not_split",
        "non_probable_category_probable_separate",
        "Confirmed",
    }


def test_missing_datasets_fail_without_substitutes(tmp_path):
    with pytest.raises(DatasetUnavailable, match="no substitute data was generated"):
        DataRepository.load(tmp_path)


def test_duplicate_monthly_keys_are_rejected(tmp_path):
    for relative in (
        "data/processed/kerala_district_annual_disease_2020_2024.csv",
        "data/processed/kerala_disease_monthly_2021_2024.csv",
        "data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv",
        "data/processed/kerala_disease_weather_monthly_2021_2024.csv",
    ):
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())

    path = tmp_path / "data/processed/kerala_disease_monthly_2021_2024.csv"
    frame = pd.read_csv(path)
    pd.concat([frame, frame.iloc[[0]]]).to_csv(path, index=False)
    with pytest.raises(DatasetUnavailable, match="duplicate natural keys"):
        DataRepository.load(tmp_path)
