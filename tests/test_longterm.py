import numpy as np
import pandas as pd
import pytest

from seoul_air import longterm as lt


def _monthly(years=6, seed=0):
    rng = np.random.default_rng(seed)
    index = pd.period_range("2015-01", periods=12 * years, freq="M")
    season = 0.3 * np.cos(2 * np.pi * (index.month.to_numpy() - 2) / 12)
    return pd.Series(3.0 + season + rng.normal(0, 0.05, len(index)), index=index)


def test_seasonal_naive_scale():
    values = np.r_[np.arange(12.0), np.arange(12.0) + 2]
    assert lt.seasonal_naive_scale(values) == pytest.approx(2.0)


def test_choose_applies_the_rule_in_order():
    summary = pd.DataFrame({
        "model": ["seasonal mean", "ETS", "damped trend", "SARIMA"],
        "mase": [0.60, 0.70, 0.68, 0.69],
        "coverage_80": [0.50, 0.80, 0.82, 0.85],
    })
    # The seasonal mean has the lowest MASE but is not eligible; ETS is within 5% of the
    # damped trend and simpler, so it wins
    assert lt.choose(summary) == ("ETS", True)
    summary["coverage_80"] = 0.5
    assert lt.choose(summary) == ("seasonal mean", False)


@pytest.mark.parametrize("model", lt.MODELS[:4])
def test_simulate_returns_paths_near_the_series(model):
    series = _monthly()
    paths = lt.simulate(model, series, h=24, n=200, seed=0)
    assert paths.shape == (200, 24)
    assert abs(np.median(paths) - series.mean()) < 0.3


def test_deweathered_model_adds_whole_years_of_weather():
    series = _monthly()
    normalised = series - 0.1
    paths = lt.simulate("deweathered (ML)", series, h=12, n=50, seed=0, normalised_log=normalised)
    assert paths.shape == (50, 12)
    with pytest.raises(ValueError):
        lt.simulate("deweathered (ML)", series, h=12, n=5)


def test_annual_means_are_weighted_by_days_and_need_twelve_months():
    index = lt.month_index("2026-01", 18)
    values = np.ones((1, 18))
    values[0, 1] = 29.0  # February 2026 has 28 days
    annual = lt.annual_from_monthly(values, index)
    assert list(annual) == [2026]
    assert annual[2026][0] == pytest.approx((337 + 28 * 29) / 365)


def test_meets_standard_rounds_the_annual_mean():
    assert lt.meets_standard(np.array([15.4, 15.6, 14.0, 20.0])) == 0.5


def test_bad_days_scale_the_daily_shape():
    profiles = {m: [np.array([0.5, 1.0, 1.5])] for m in range(1, 13)}
    days = lt.bad_days(np.array([[30.0, 20.0]]), [1, 2], profiles, np.random.default_rng(0))
    assert days.tolist() == [[1, 0]]  # 45 is Bad, 35 and 30 are not


def test_stalled_scenario_keeps_the_last_level_plus_weather():
    series = _monthly(years=4)
    anomaly = pd.Series(0.0, index=series.index)
    paths = lt.scenario_paths(series, anomaly, [0.0], h=24, n=10, seed=0)
    expected = np.tile(series.iloc[-12:].to_numpy(), 2)
    assert np.allclose(paths, expected)
    rising = lt.scenario_paths(series, anomaly, [0.12], h=12, n=3, seed=0)
    assert np.allclose(rising[:, -1] - series.iloc[-1], 0.12)
