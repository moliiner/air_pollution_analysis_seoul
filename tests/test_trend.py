import numpy as np
import pandas as pd
import pytest

from seoul_air import trend


def _monthly(slope_per_year, years=11, noise=1.0, seed=0):
    rng = np.random.default_rng(seed)
    index = pd.period_range("2015-01", periods=12 * years, freq="M")
    t = np.arange(len(index)) / 12
    season = 5 * np.cos(2 * np.pi * index.month / 12)
    return pd.Series(25 + slope_per_year * t + season + rng.normal(0, noise, len(index)), index=index)


def test_trend_recovers_a_known_slope_and_covers_it():
    result = trend.trend(_monthly(-0.8), n_boot=300)
    assert result["slope_per_year"] == pytest.approx(-0.8, abs=0.1)
    assert result["low_95"] < -0.8 < result["high_95"]
    assert result["excludes_zero"]


def test_no_trend_gives_an_interval_with_zero():
    result = trend.trend(_monthly(0.0, noise=2.0, seed=3), n_boot=300)
    assert result["low_95"] < 0 < result["high_95"]
    assert not result["excludes_zero"]


def test_deseasonalise_removes_the_calendar_month_mean():
    anomalies = trend.deseasonalise(_monthly(0.0, noise=0.0))
    assert anomalies.abs().max() == pytest.approx(0, abs=1e-9)


def test_monthly_means_need_enough_days():
    days = pd.date_range("2015-01-01", "2015-02-28", freq="D")
    daily = pd.Series(1.0, index=days)
    daily.loc["2015-02-01":"2015-02-15"] = np.nan
    out = trend.monthly_means(daily)
    assert out.iloc[0] == 1.0 and np.isnan(out.iloc[1])


def test_years_since_start():
    index = pd.period_range("2015-01", periods=13, freq="M")
    assert trend.years_since_start(index)[-1] == pytest.approx(1.0)
