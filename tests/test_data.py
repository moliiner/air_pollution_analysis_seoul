import pandas as pd

from seoul_air.data import (
    complete_hourly_grid,
    daily_means,
    flag_rate_by_network_level,
    keep_valid_readings,
    network_gap_days,
    plausible_flagged,
    to_wide,
)


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


def test_network_gap_days_keeps_partial_hours():
    hours = pd.date_range("2019-03-01", periods=72, freq="h")
    hourly = pd.DataFrame({"datetime": hours, "station_code": 101, "pm25": 20.0})
    hourly.loc[24:24 + 13, "pm25"] = None  # day 2 keeps 10 hours
    hourly.loc[48:, "pm25"] = None  # day 3 has nothing
    daily = daily_means(hourly, ["pm25"])
    gaps = network_gap_days(daily, hourly)
    assert gaps["date"].dt.strftime("%m-%d").tolist() == ["03-02", "03-03"]
    assert gaps["hours_with_data"].tolist() == [10, 0]
    assert gaps["partial_city_mean"].iloc[0] == 20.0
    assert pd.isna(gaps["partial_city_mean"].iloc[1])


def _flags():
    hours = pd.to_datetime(["2019-01-01 00:00"] * 4 + ["2019-01-01 01:00"] * 2)
    return pd.DataFrame({
        "datetime": hours,
        "value": [100.0, 100.0, 90.0, 985.0, 10.0, 7.0],
        "status": [0, 0, 9, 9, 0, 1],
    })


def test_plausible_flagged_needs_a_value_near_the_network():
    assert plausible_flagged(_flags()).tolist() == [False, False, True, False, False, True]


def test_flag_rate_by_network_level_counts_each_level():
    t = flag_rate_by_network_level(_flags(), [0, 50, 200], ["low", "high"]).set_index("network_level")
    assert t.loc["high", "readings"] == 4
    assert t.loc["high", "flagged"] == 2
    assert t.loc["high", "plausible_flagged"] == 1
    assert t.loc["high", "flagged_%"] == 50.0
    assert t.loc["low", "flagged"] == 1
    assert t.loc["No reference", "readings"] == 0


def test_hours_without_normal_readings_have_no_reference():
    df = pd.DataFrame({"datetime": pd.to_datetime(["2019-01-01"] * 2), "value": [5.0, 6.0], "status": [9, 9]})
    t = flag_rate_by_network_level(df, [0, 50], ["low"]).set_index("network_level")
    assert t.loc["No reference", "flagged"] == 2
