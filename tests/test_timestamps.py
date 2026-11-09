import pandas as pd

from seoul_air.data import label_lag_matches, load_api_samples, to_official_label


def _long():
    hours = pd.date_range("2019-01-01 00:00", periods=4, freq="h")
    return pd.DataFrame({
        "datetime": list(hours) * 2,
        "station_code": [101] * 8,
        "pollutant": pd.Categorical(["pm25"] * 4 + ["no2"] * 4),
        "value": [10.0, 20.0, 30.0, 40.0, 0.01, 0.02, 0.03, 0.04],
    })


def test_matches_reveal_a_one_hour_offset():
    # Official label 02:00 holds the value the dataset labels 01:00
    samples = pd.DataFrame({
        "official_label": pd.to_datetime(["2019-01-01 02:00", "2019-01-01 03:00"]),
        "station_code": [101, 101],
        "pollutant": ["pm25", "no2"],
        "value": [20.0, 0.03],
    })
    out = label_lag_matches(_long(), samples, lags=(-1, 0)).set_index("dataset_hour_minus_official_label")
    assert out.loc[-1, "identical"] == 2 and out.loc[-1, "identical_%"] == 100
    assert out.loc[0, "identical"] == 0 and out.loc[0, "compared"] == 2


def test_missing_dataset_hours_are_not_compared():
    samples = pd.DataFrame({"official_label": pd.to_datetime(["2019-01-01 00:00"]),
                            "station_code": [101], "pollutant": ["pm25"], "value": [10.0]})
    out = label_lag_matches(_long(), samples, lags=(-1, 0)).set_index("dataset_hour_minus_official_label")
    assert out.loc[-1, "compared"] == 0
    assert out.loc[0, "identical"] == 1


def test_official_label_is_one_hour_later():
    assert to_official_label(pd.Timestamp("2019-12-31 23:00")) == pd.Timestamp("2020-01-01 00:00")


def test_api_samples_file():
    samples = load_api_samples()
    assert samples["official_label"].dt.year.between(2017, 2019).all()
    assert set(samples["pollutant"]) == {"so2", "no2", "co", "o3", "pm10", "pm25"}
    assert not samples.duplicated(["official_label", "station_code", "pollutant"]).any()
    assert samples["station_code"].between(101, 125).all()
