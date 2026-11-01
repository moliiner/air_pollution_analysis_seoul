import numpy as np
import pandas as pd

from seoul_air.features import FEATURE_COLUMNS, make_forecast_table


def _daily(n_days=20):
    dates = pd.date_range("2017-01-01", periods=n_days, freq="D")
    frames = []
    for code, offset in [(101, 0.0), (102, 100.0)]:
        frames.append(pd.DataFrame({
            "station_code": code, "date": dates,
            "pm25": np.arange(n_days, dtype=float) + offset,
            "pm10": 1.0, "no2": 1.0, "co": 1.0, "o3": 1.0, "so2": 1.0,
        }))
    return pd.concat(frames, ignore_index=True)


def test_target_is_next_day_of_same_station():
    t = make_forecast_table(_daily())
    row = t[(t["station_code"] == 102) & (t["date"] == "2017-01-05")].iloc[0]
    assert row["pm25_d0"] == 104.0
    assert row["target"] == 105.0
    assert row["target_date"] == pd.Timestamp("2017-01-06")


def test_no_feature_uses_the_target_day():
    t = make_forecast_table(_daily())
    row = t[(t["station_code"] == 101) & (t["date"] == "2017-01-10")].iloc[0]
    # pm25 grows by 1 per day, so any feature equal to the target would leak
    for col in ["pm25_d0"] + [c for c in FEATURE_COLUMNS if c.startswith("pm25_lag")]:
        assert row[col] < row["target"]
    assert row["pm25_lag1"] == row["pm25_d0"] - 1


def test_last_day_has_no_target_and_lags_do_not_cross_stations():
    t = make_forecast_table(_daily())
    first_102 = t[(t["station_code"] == 102)].sort_values("date").iloc[0]
    assert np.isnan(first_102["pm25_lag1"])
    last_101 = t[(t["station_code"] == 101)].sort_values("date").iloc[-1]
    assert np.isnan(last_101["target"])


def test_all_feature_columns_present():
    t = make_forecast_table(_daily())
    assert set(FEATURE_COLUMNS) <= set(t.columns)
