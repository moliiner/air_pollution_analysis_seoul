import numpy as np
import pandas as pd
import pytest

from seoul_air import deweather, policy


def _synthetic(days=1461, seed=0):
    """Daily PM2.5 = slow decline + season + a strong effect of wind, which varies by chance."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2015-01-01", periods=days, freq="D")
    doy = dates.dayofyear.to_numpy()
    wind = rng.gamma(2.0, 1.2, days)
    weather = pd.DataFrame({"date": dates, **{c: rng.normal(size=days) for c in deweather.WEATHER_COLUMNS}})
    weather["wind_speed_mean_ms"] = wind
    trend = 30 - 2.0 * np.arange(days) / 365.25
    season = 6 * np.cos(2 * np.pi * (doy - 60) / 365.25)
    pm25 = pd.Series(trend + season - 4 * (wind - wind.mean()) + rng.normal(0, 1, days), index=dates)
    return pm25, weather, trend + season


def test_build_table_adds_lags_and_time():
    pm25, weather, _ = _synthetic(days=40)
    table = deweather.build_table(pm25, weather)
    assert np.isnan(table["wind_speed_mean_ms_lag1"].iloc[0])
    assert table["wind_speed_mean_ms_lag1"].iloc[1] == weather["wind_speed_mean_ms"].iloc[0]
    assert table["time_years"].iloc[0] == 0
    assert set(deweather.TIME_COLUMNS) <= set(table.columns)


def test_leave_one_year_out_never_trains_on_the_predicted_year():
    pm25, weather, _ = _synthetic()
    table = deweather.build_table(pm25, weather)
    shifted = table.copy()
    shifted.loc[shifted.index.year == 2016, "pm25"] += 1000
    a = deweather.leave_one_year_out(table, {"max_iter": 50})
    b = deweather.leave_one_year_out(shifted, {"max_iter": 50})
    # Changing 2016 cannot change its own predictions, only those of other years
    assert np.allclose(a[a.index.year == 2016], b[b.index.year == 2016])
    assert not np.allclose(a[a.index.year == 2017], b[b.index.year == 2017])


def test_normalisation_removes_the_weather_and_keeps_the_trend():
    pm25, weather, expected = _synthetic()
    table = deweather.build_table(pm25, weather)
    model = deweather.make_model().fit(table[deweather.features(table)], table["pm25"])
    normalised = deweather.normalise(model, table, n_samples=60)
    noise_raw = (pm25 - expected).std()
    noise_normalised = (normalised - pd.Series(expected, index=pm25.index)).std()
    assert noise_normalised < 0.5 * noise_raw
    yearly = normalised.groupby(normalised.index.year).mean()
    assert yearly.iloc[-1] < yearly.iloc[0] - 4  # the 2 ug/m3 a year decline survives


def test_score_by_year_has_an_overall_row():
    dates = pd.date_range("2015-01-01", periods=4, freq="180D")
    scores = deweather.score_by_year(pd.Series([1.0, 2, 3, 4], index=dates), pd.Series([1.0, 2, 3, 5], index=dates))
    assert scores.loc["all", "mae"] == pytest.approx(0.25)
    assert scores.loc["all", "days"] == 4


def test_season_of():
    dates = pd.to_datetime(["2019-12-15", "2020-03-31", "2020-04-01", "2019-11-30"])
    assert policy.season_of(dates).tolist()[:2] == [2019, 2019]
    assert policy.season_of(dates).isna().tolist() == [False, False, True, True]


def _monthly(values_by_month):
    index = pd.period_range("2015-01", periods=len(values_by_month), freq="M")
    return pd.Series(values_by_month, index=index, dtype=float)


def test_season_means_need_four_months():
    monthly = _monthly(np.arange(36, dtype=float))  # 2015-01 to 2017-12
    seasons = policy.season_means(monthly)
    assert list(seasons.index) == [2015, 2016]  # 2014 has only Jan-Mar 2015, 2017 only December
    assert seasons[2015] == pytest.approx(np.mean([11, 12, 13, 14]))


def test_before_after_with_an_exact_permutation_test():
    values = pd.Series([10.0, 11, 12, 1, 2, 3], index=[2016, 2017, 2018, 2019, 2020, 2021])
    result = policy.before_after(values)
    assert result["difference"] == pytest.approx(-9)
    # The observed split is the most extreme of the 20 ways (and its mirror): p = 2/20
    assert result["p_value"] == pytest.approx(0.1)
    assert policy.before_after(values, exclude=(2020,))["post_seasons"] == 2


def test_season_minus_other_pairs_each_season_with_the_following_months():
    season = pd.Series([20.0, 20, 14, 14], index=[2017, 2018, 2019, 2020])
    other = pd.Series([10.0, 10, 8, 8], index=[2018, 2019, 2020, 2021])
    gap = policy.season_minus_other(season, other)
    assert gap.to_dict() == {2017: 10, 2018: 10, 2019: 6, 2020: 6}
    assert policy.before_after(gap)["difference"] == -4  # (14 - 20) - (8 - 10)
    relative = policy.season_minus_other(season, other, log=True)
    assert relative[2019] == pytest.approx(np.log(14 / 8))


def test_trend_gap_is_zero_when_the_trend_continues():
    index = pd.period_range("2015-01", "2024-12", freq="M")
    t = np.arange(len(index)) / 12
    noise = np.random.default_rng(0).normal(0, 0.2, len(index))
    anomaly = pd.Series(-1.0 * t + noise, index=index)
    level = pd.Series(30 - 1.0 * t, index=index)
    result = policy.trend_gap(anomaly, policy.season_means(level), n_boot=200)
    assert result["pre_slope_per_year"] == pytest.approx(-1.0, abs=0.1)
    assert result["gap_low_95"] < 0 < result["gap_high_95"]
    assert abs(result["gap"]) < 0.5


def test_trend_gap_finds_a_step():
    index = pd.period_range("2015-01", "2024-12", freq="M")
    t = np.arange(len(index)) / 12
    noise = np.random.default_rng(1).normal(0, 0.2, len(index))
    step = np.where(index >= pd.Period("2019-12", "M"), -3.0, 0.0)
    anomaly = pd.Series(-0.5 * t + noise + step, index=index)
    result = policy.trend_gap(anomaly, policy.season_means(pd.Series(30 - 0.5 * t + step, index=index)),
                              n_boot=200)
    assert result["gap"] == pytest.approx(-3, abs=0.4)
    assert result["gap_high_95"] < 0
