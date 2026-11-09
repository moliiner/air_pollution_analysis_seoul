import numpy as np
import pandas as pd
import pytest

from seoul_air import ozone


def test_daily_max_8h():
    hours = pd.date_range("2020-07-01", periods=48, freq="h")
    values = pd.Series(0.02, index=hours)
    values.iloc[2:10] = 0.08  # an 8-hour block early on the first day, so no window reaches the second day
    out = ozone.daily_max_8h(values)
    assert out.iloc[0] == pytest.approx(0.08)
    assert out.iloc[1] == pytest.approx(0.02)


def test_daily_max_8h_needs_six_hours():
    hours = pd.date_range("2020-07-01", periods=24, freq="h")
    values = pd.Series(np.nan, index=hours)
    values.iloc[0:5] = 0.05
    assert np.isnan(ozone.daily_max_8h(values).iloc[0])


def test_daily_max_1h_needs_most_of_the_day():
    hours = pd.date_range("2020-07-01", periods=48, freq="h")
    values = pd.Series(0.03, index=hours)
    values.iloc[30:40] = np.nan
    out = ozone.daily_max_1h(values)
    assert out.iloc[0] == pytest.approx(0.03) and np.isnan(out.iloc[1])
