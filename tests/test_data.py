import pandas as pd

from seoul_air.data import complete_hourly_grid, daily_means, keep_valid_readings, to_wide


def _long():
    return pd.DataFrame({
        "datetime": pd.to_datetime(["2017-01-01 00:00"] * 3 + ["2017-01-01 01:00"]),
        "station_code": [101, 101, 102, 101],
        "pollutant": ["pm25", "pm10", "pm25", "pm25"],
        "value": [20.0, 40.0, -1.0, 30.0],
        "status": [0, 0, 0, 9],
    })


def test_keep_valid_readings_drops_flagged_and_negative():
    out = keep_valid_readings(_long())
    assert len(out) == 2
    assert (out["status"] == 0).all() and (out["value"] >= 0).all()


def test_to_wide_one_column_per_pollutant():
    wide = to_wide(keep_valid_readings(_long()))
    assert list(wide.columns) == ["datetime", "station_code", "pm10", "pm25"]
    assert len(wide) == 1


def test_complete_hourly_grid_adds_missing_hours():
    wide = to_wide(keep_valid_readings(_long()))
    grid = complete_hourly_grid(wide, "2017-01-01 00:00", "2017-01-01 02:00", [101, 102])
    assert len(grid) == 6
    assert grid["pm25"].notna().sum() == 1


def test_daily_means_require_min_hours():
    hours = pd.date_range("2017-01-01", periods=48, freq="h")
    hourly = pd.DataFrame({"datetime": hours, "station_code": 101, "pm25": 10.0})
    hourly.loc[24:24 + 7, "pm25"] = None  # day 2 keeps 16 of 24 readings
    daily = daily_means(hourly, ["pm25"], min_hours=18)
    assert daily["pm25"].tolist()[0] == 10.0
    assert pd.isna(daily["pm25"].tolist()[1])
