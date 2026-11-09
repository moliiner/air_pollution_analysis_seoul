import numpy as np
import pandas as pd
import pytest

from seoul_air import cai


@pytest.mark.parametrize("pollutant,value,expected", [
    ("pm25", 0, 0), ("pm25", 15, 50), ("pm25", 16, 51), ("pm25", 35, 100), ("pm25", 36, 101),
    ("pm25", 75, 250), ("pm25", 76, 251), ("pm25", 500, 500), ("pm25", 900, 500),
    ("pm10", 80, 100), ("pm10", 81, 101),
    ("o3", 0.03, 50), ("o3", 0.031, 51), ("o3", 0.09, 100), ("o3", 0.6, 500),
    ("co", 9.0, 100), ("co", 9.01, 101),
])
def test_sub_index_at_the_breakpoints(pollutant, value, expected):
    assert cai.sub_index(pollutant, [value])[0] == pytest.approx(expected)


def test_sub_index_interpolates_inside_a_band_and_rounds_first():
    assert cai.sub_index("pm25", [25])[0] == pytest.approx(51 + 49 * (25 - 16) / (35 - 16))
    assert cai.sub_index("pm25", [15.4])[0] == pytest.approx(50)  # rounded to 15
    assert np.isnan(cai.sub_index("pm25", [np.nan])[0])


def test_grades():
    assert cai.grade([0, 50, 51, 100, 101, 250, 251]).tolist() == [
        "Good", "Good", "Moderate", "Moderate", "Unhealthy", "Unhealthy", "Very unhealthy"]


def test_predicted_average_weights_the_last_hours():
    flat = cai.predicted_24h_average(np.full(24, 20.0), threshold=30)
    assert flat.iloc[-1] == pytest.approx(20)
    rising = np.r_[np.full(20, 10.0), np.full(4, 50.0)]
    c24e = cai.predicted_24h_average(rising, threshold=70).iloc[-1]
    c12 = rising[-12:].mean()
    assert c24e == pytest.approx((12 * c12 + 12 * 50) / 24)


def test_predicted_average_discounts_high_steady_hours():
    steady = np.full(24, 100.0)
    # The ratio to C12 is 1.0 and the value is above M, so C4 counts 0.75 of it
    assert cai.predicted_24h_average(steady, threshold=70).iloc[-1] == pytest.approx((12 * 100 + 12 * 75) / 24)


def test_predicted_average_needs_enough_hours():
    series = np.r_[np.full(6, np.nan), np.full(6, 20.0)]
    assert np.isnan(cai.predicted_24h_average(series, threshold=30).iloc[-1])


def _hours(**values):
    base = {"so2": 0.003, "co": 0.4, "o3": 0.02, "no2": 0.02, "pm10": 20.0, "pm25": 10.0}
    base.update(values)
    return pd.DataFrame({k: np.full(24, v, dtype=float) for k, v in base.items()})


def test_station_cai_takes_the_highest_sub_index():
    last = cai.station_cai(_hours(o3=0.08)).iloc[-1]
    assert last["main_pollutant"] == "o3"
    assert last["cai"] == pytest.approx(cai.sub_index("o3", [0.08])[0])
    assert last["grade"] == "Moderate"


def test_bonus_for_several_unhealthy_pollutants():
    two = cai.station_cai(_hours(o3=0.12, no2=0.1)).iloc[-1]
    assert two["unhealthy_pollutants"] == 2
    assert two["cai"] == pytest.approx(max(cai.sub_index("o3", [0.12])[0], cai.sub_index("no2", [0.1])[0]) + 50)
    three = cai.station_cai(_hours(o3=0.12, no2=0.1, so2=0.1)).iloc[-1]
    assert three["unhealthy_pollutants"] == 3
    highest = max(cai.sub_index(p, [v])[0] for p, v in [("o3", 0.12), ("no2", 0.1), ("so2", 0.1)])
    assert three["cai"] == pytest.approx(highest + 75)
    assert three["main_pollutant"] == "so2"


def test_hours_without_any_reading():
    empty = _hours(so2=np.nan, co=np.nan, o3=np.nan, no2=np.nan, pm10=np.nan, pm25=np.nan)
    out = cai.station_cai(empty)
    assert out["cai"].isna().all() and out["main_pollutant"].isna().all()
