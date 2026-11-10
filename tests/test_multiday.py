import numpy as np
import pandas as pd
import pytest

from seoul_air import multiday as md
from seoul_air import nwp, regional


def _hourly(days=20, seed=0):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2020-01-01", periods=24 * days, freq="h")
    columns = ["pm25", "pm10", "no2", "o3", "co"]
    return pd.DataFrame(rng.gamma(3, 8, (len(index), len(columns))), index=index, columns=columns)


def test_at_issue_window_ends_at_the_last_published_hour():
    series = pd.Series(np.arange(48, dtype=float), index=pd.date_range("2020-01-01", periods=48, freq="h"))
    day = pd.Timestamp("2020-01-02")
    # 3 hours ending at 15:00 of 2 January: labels 13, 14, 15 -> values 37, 38, 39
    assert md.at_issue(series, 3, [day]).iloc[0] == pytest.approx(38)
    assert md.at_issue(series, 3, [day], lag_hours=24).iloc[0] == pytest.approx(14)
    assert md.at_issue(series, 3, [day], how="max").iloc[0] == 39


def test_features_never_use_hours_after_the_issue_time():
    city = _hourly()
    day = pd.Timestamp("2020-01-10")
    changed = city.copy()
    changed.loc[day + pd.Timedelta(hours=md.ISSUE_LAST_HOUR + 1):] = 1e6
    before, after = md.air_features(city, [day]), md.air_features(changed, [day])
    pd.testing.assert_frame_equal(before, after)
    changed.loc[day + pd.Timedelta(hours=md.ISSUE_LAST_HOUR)] = 1e6
    assert not md.air_features(changed, [day]).equals(before)


def test_windows_need_most_of_their_hours():
    city = _hourly()
    day = pd.Timestamp("2020-01-10")
    city.loc[day:day + pd.Timedelta(hours=md.ISSUE_LAST_HOUR), "pm25"] = np.nan
    assert np.isnan(md.air_features(city, [day])["pm25_today"].iloc[0])


def test_build_tables_aligns_target_and_forecast_days():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    city_daily = pd.Series(np.arange(10, dtype=float), index=dates)
    features = pd.DataFrame({"x": np.arange(10.0)}, index=dates)
    nwp_daily = pd.concat({h: pd.DataFrame({"nwp_temperature_mean": 100.0 * h + np.arange(10)}, index=dates)
                           for h in md.HORIZONS}, axis=1)
    tables = md.build_tables(city_daily, features, nwp_daily)
    row = tables[2].loc["2020-01-03"]
    assert row["target"] == 4  # value of 5 January
    assert row["target_date"] == pd.Timestamp("2020-01-05")
    assert row["nwp_temperature_mean"] == 204  # the horizon-2 forecast valid for 5 January
    assert np.isnan(tables[3].loc["2020-01-09", "target"])


def test_rolling_origins_fit_only_on_targets_before_the_origin():
    dates = pd.date_range("2019-12-20", "2020-01-20", freq="D")
    table = pd.DataFrame({"target": 1.0, "target_date": dates + pd.Timedelta(days=2)}, index=dates)
    seen = {}

    def fit_predict(train, test):
        seen["last_target"] = train["target_date"].max()
        seen["first_issue"] = test.index.min()
        return pd.DataFrame({"forecast": 0.0}, index=test.index)

    md.rolling_origins(table, md.yearly_origins([2020]), fit_predict)
    assert seen["last_target"] < pd.Timestamp("2020-01-01") <= seen["first_issue"]


def test_climatology_uses_the_window_around_the_day_of_year():
    train_dates = pd.to_datetime(["2019-01-01", "2019-01-10", "2019-07-01"])
    out = md.climatology(train_dates, [10.0, 20.0, 100.0], pd.to_datetime(["2020-01-05"]), window_days=15)
    assert out[0] == pytest.approx(15)


def test_scores_pod_far_csi():
    y_true = np.array([40.0, 40, 10, 10])
    alert = np.array([True, False, True, False])
    s = md.scores(y_true, y_true, alert=alert)
    assert s["pod"] == 0.5 and s["far"] == 0.5 and s["csi"] == pytest.approx(1 / 3)


def test_conformal_widening_reaches_the_coverage():
    rng = np.random.default_rng(1)
    y = rng.normal(size=2000)
    widening = md.conformal_widening(y, np.full(2000, -0.5), np.full(2000, 0.5), coverage=0.8)
    inside = np.mean((y >= -0.5 - widening) & (y <= 0.5 + widening))
    assert 0.79 <= inside <= 0.82


def test_jma_offset_was_made_before_the_issue_time():
    # Target day D+k, last hour 23:00 KST; issue at 17:00 KST of D
    for horizon in md.HORIZONS:
        issue = pd.Timestamp("2024-01-10 17:00")
        last_valid = issue.normalize() + pd.Timedelta(days=horizon, hours=23)
        predicted_at = last_valid - pd.Timedelta(days=nwp.offset_for(horizon))
        assert predicted_at < issue - pd.Timedelta(hours=12)


def test_airkorea_labels_move_to_the_start_of_the_hour():
    times = regional.label_to_start(["2015010101", "2015010124"])
    assert list(times) == [pd.Timestamp("2015-01-01 00:00"), pd.Timestamp("2015-01-01 23:00")]
