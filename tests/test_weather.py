import json

import numpy as np
import pandas as pd
import pytest

from seoul_air import weather


def _instants(times_utc, **columns):
    n = len(times_utc)
    base = {"temperature_c": np.arange(n, dtype=float), "relative_humidity_pct": 50.0, "precipitation_mm": 0.0,
            "wind_speed_ms": 2.0, "wind_direction_deg": 270.0, "boundary_layer_height_m": 500.0,
            "surface_pressure_hpa": 1010.0}
    base.update(columns)
    return pd.DataFrame({"time_utc": pd.to_datetime(times_utc), **base})


def test_wind_components_follow_the_meteorological_convention():
    u, v = weather.wind_components(np.array([2.0, 2.0]), np.array([270.0, 0.0]))
    assert u[0] == pytest.approx(2.0) and v[0] == pytest.approx(0, abs=1e-12)  # from the west: blows east
    assert v[1] == pytest.approx(-2.0)  # from the north: blows south
    assert weather.wind_direction(np.array([2.0]), np.array([0.0]))[0] == pytest.approx(270)


def test_kst_hours_label_the_start_and_average_both_ends():
    # 15:00 and 16:00 UTC on 31 Dec are 00:00 and 01:00 KST on 1 Jan
    instants = _instants(["2014-12-31 15:00", "2014-12-31 16:00", "2014-12-31 17:00"],
                         precipitation_mm=[9.0, 1.5, 0.5])
    hourly = weather.to_kst_hours(instants)
    assert hourly["datetime"].tolist() == [pd.Timestamp("2015-01-01 00:00"), pd.Timestamp("2015-01-01 01:00")]
    assert hourly["temperature_c"].tolist() == [0.5, 1.5]
    # Precipitation reported at 01:00 KST fell during 00:00-01:00 KST
    assert hourly["precipitation_mm"].tolist() == [1.5, 0.5]
    assert hourly["wind_direction_deg"].tolist() == pytest.approx([270, 270])


def test_wind_direction_is_averaged_through_components():
    instants = _instants(["2015-01-01 00:00", "2015-01-01 01:00"], wind_direction_deg=[350.0, 10.0])
    hourly = weather.to_kst_hours(instants)
    assert hourly["wind_direction_deg"].iloc[0] == pytest.approx(0, abs=1e-6) or \
        hourly["wind_direction_deg"].iloc[0] == pytest.approx(360, abs=1e-6)


def test_missing_instants_give_missing_hours():
    instants = _instants(["2015-01-01 00:00", "2015-01-01 02:00"])
    hourly = weather.to_kst_hours(instants)
    assert len(hourly) == 2 and hourly["temperature_c"].isna().all()


def test_daily_weather_needs_a_complete_day():
    hours = pd.date_range("2015-01-01", periods=47, freq="h")
    hourly = pd.DataFrame({"datetime": hours, **{c: 1.0 for c in weather.WEATHER_COLUMNS}})
    hourly["precipitation_mm"] = 0.5
    daily = weather.daily_weather(hourly)
    assert daily["precipitation_mm"].iloc[0] == 12.0
    assert daily["temperature_mean_c"].iloc[0] == 1.0
    assert np.isnan(daily["temperature_mean_c"].iloc[1])  # 23 hours only


def test_read_era5_renames_and_keeps_units(tmp_path):
    data = {"latitude": 37.5, "longitude": 127.0,
            "hourly_units": {"time": "iso8601", **{k: "x" for k in weather.VARIABLES}},
            "hourly": {"time": ["2015-01-01T00:00", "2015-01-01T01:00"], **{k: [1.0, 2.0] for k in weather.VARIABLES}}}
    path = tmp_path / "era5.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    frame = weather.read_era5([path, path])
    assert len(frame) == 2  # duplicate hours of overlapping files are dropped
    assert {"temperature_c", "boundary_layer_height_m", "time_utc"} <= set(frame.columns)
    assert frame.attrs["grid_point"] == (37.5, 127.0)


def test_era5_periods_start_the_day_before_for_kst():
    periods = weather.era5_periods(2015, 2016)
    assert periods[0] == ("2014-12-31", "2014-12-31")
    assert periods[-1] == ("2016-01-01", "2016-12-31")


def test_joins_keep_every_pollution_row():
    air = pd.DataFrame({"datetime": pd.to_datetime(["2015-01-01 00:00"] * 2), "station_code": [101, 102]})
    wx = pd.DataFrame({"datetime": pd.to_datetime(["2015-01-01 00:00"]), "temperature_c": [3.0]})
    joined = weather.join_hourly(air, wx)
    assert len(joined) == 2 and joined["temperature_c"].tolist() == [3.0, 3.0]


def test_weather_known_at_issue_never_uses_the_target_day():
    days = pd.date_range("2019-01-01", periods=5, freq="D")
    wx = pd.DataFrame({"date": days, "temperature_mean_c": [10.0, 11, 12, 13, 14]})
    table = pd.DataFrame({"date": days[1:4], "target_date": days[2:5]})
    out = weather.weather_known_at_issue(table, wx, lags=(0, 1))
    # Issue day 2019-01-02 (11 degrees), the day before (10); never the target day (12)
    assert out["temperature_mean_c_lag0"].tolist() == [11.0, 12.0, 13.0]
    assert out["temperature_mean_c_lag1"].tolist() == [10.0, 11.0, 12.0]
    target_weather = out["target_date"].map(wx.set_index("date")["temperature_mean_c"])
    assert (out["temperature_mean_c_lag0"] < target_weather).all()
    with pytest.raises(ValueError):
        weather.weather_known_at_issue(table, wx, lags=(-1,))


def test_station_observations_convert_wind_to_metres_per_second(tmp_path):
    path = tmp_path / "47108.csv"
    path.write_text("2015-01-01,3,1.0,-5.0,60,,,270,36.0,,1020,,\n2014-12-31,3,1.0,-5.0,60,,,270,36.0,,1020,,\n")
    frame = weather.read_station_observations(path)
    assert len(frame) == 1
    assert frame["wind_speed_ms"].iloc[0] == pytest.approx(10.0)
    assert frame["time_utc"].iloc[0] == pd.Timestamp("2015-01-01 03:00")


def test_daily_weather_checks_each_variable_separately():
    hours = pd.date_range("2024-06-30", periods=48, freq="h")
    hourly = pd.DataFrame({"datetime": hours, **{c: 1.0 for c in weather.WEATHER_COLUMNS}})
    hourly.loc[30, "boundary_layer_height_m"] = np.nan  # one hour missing on the second day
    daily = weather.daily_weather(hourly)
    assert daily["boundary_layer_height_mean_m"].isna().tolist() == [False, True]
    assert daily["boundary_layer_height_max_m"].isna().tolist() == [False, True]
    assert daily["temperature_mean_c"].notna().all() and daily["wind_direction_mean_deg"].notna().all()
