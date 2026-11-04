import numpy as np
import pandas as pd
import pytest

from seoul_air.station_levels import (
    agreed_shifts,
    best_arc,
    change_around,
    detect_level_shifts,
    log_ratio,
    nearest_stations,
    neighbour_median,
    offset_from_city,
    offset_intervals,
    rest_of_city_mean,
    shift_pvalue,
    shuffle_blocks,
    station_outages,
)


def _table():
    return pd.DataFrame({"A": [10.0, 20.0], "B": [20.0, np.nan], "C": [30.0, 40.0]},
                        index=pd.date_range("2019-01-01", periods=2, freq="D"))


def _weekly(values):
    return pd.Series(values, index=pd.date_range("2017-01-01", periods=len(values), freq="W"))


def test_rest_of_city_excludes_the_station_and_missing_values():
    rest = rest_of_city_mean(_table())
    assert rest["A"].tolist() == [25.0, 40.0]
    assert rest["B"].iloc[1] == 30.0
    assert offset_from_city(_table())["C"].tolist() == [15.0, 20.0]


def test_a_station_alone_has_no_reference():
    table = pd.DataFrame({"A": [10.0], "B": [np.nan]})
    assert np.isnan(rest_of_city_mean(table)["A"].iloc[0])


def test_log_ratio_ignores_zero_references():
    table = pd.DataFrame({"A": [10.0, 10.0]})
    reference = pd.DataFrame({"A": [10.0, 0.0]})
    out = log_ratio(table, reference)["A"]
    assert out.iloc[0] == 0 and np.isnan(out.iloc[1])


def test_nearest_stations_order_and_self_exclusion():
    stations = pd.DataFrame({"district": ["A", "B", "C"], "latitude": [37.0, 37.0, 37.0],
                             "longitude": [127.0, 127.1, 127.5]})
    near = nearest_stations(stations, k=2)
    assert near["A"] == ["B", "C"]
    assert near["C"] == ["B", "A"]


def test_neighbour_median_uses_only_the_neighbours():
    table = pd.DataFrame({"A": [1.0], "B": [10.0], "C": [20.0], "D": [90.0]})
    out = neighbour_median(table, {"A": ["B", "C", "D"], "B": ["A"], "C": ["A"], "D": ["A"]})
    assert out["A"].iloc[0] == 20.0


def test_best_arc_finds_a_single_change_as_a_stretch_to_the_end():
    start, end, jump, _ = best_arc(np.r_[np.zeros(30), np.ones(30)], 10)
    assert jump == pytest.approx(1) or jump == pytest.approx(-1)
    assert (start, end) in {(30, 60), (0, 30)}


def test_best_arc_finds_a_change_that_reverses():
    start, end, jump, _ = best_arc(np.r_[np.zeros(30), np.ones(30), np.zeros(30)], 10)
    assert (start, end) == (30, 60)
    assert jump == pytest.approx(1)


def test_best_arc_respects_the_minimum_size():
    assert best_arc(np.zeros(9), 5) is None
    start, end, _, _ = best_arc(np.r_[1.0, np.zeros(19)], 5)
    assert 5 <= end - start <= 15


def test_shift_pvalue_is_small_for_a_real_shift_only():
    rng = np.random.default_rng(1)
    noise = rng.normal(size=120)
    shifted = noise + np.r_[np.zeros(60), np.full(60, 3.0)]
    statistic = best_arc(shifted, 26)[3]
    assert shift_pvalue(shifted - shifted.mean(), statistic, 26, 8, 199, rng) <= 0.01
    statistic = best_arc(noise, 26)[3]
    assert shift_pvalue(noise - noise.mean(), statistic, 26, 8, 199, rng) > 0.01


def test_detect_level_shifts_finds_up_and_down():
    rng = np.random.default_rng(2)
    level = np.r_[np.zeros(50), np.full(50, 0.3), np.zeros(56)]
    weekly = _weekly(level + rng.normal(scale=0.03, size=156))
    found = detect_level_shifts(weekly, n_perm=199)
    assert len(found) == 2
    assert found["jump"].iloc[0] > 0 > found["jump"].iloc[1]
    assert found["date"].tolist() == [weekly.index[50], weekly.index[100]]


def test_detect_level_shifts_ignores_small_jumps_and_noise():
    rng = np.random.default_rng(3)
    small = np.r_[np.zeros(78), np.full(78, 0.05)] + rng.normal(scale=0.005, size=156)
    assert detect_level_shifts(_weekly(small), n_perm=99).empty
    assert detect_level_shifts(_weekly(rng.normal(scale=0.05, size=156)), n_perm=99).empty


def test_detect_level_shifts_skips_missing_weeks():
    level = np.r_[np.zeros(60), np.full(60, 0.5)]
    values = level + np.random.default_rng(4).normal(scale=0.03, size=120)
    values[10:20] = np.nan
    assert len(detect_level_shifts(_weekly(values), n_perm=99)) == 1


def test_offset_intervals_cover_the_true_order():
    rng = np.random.default_rng(5)
    weeks = pd.date_range("2017-01-01", periods=150, freq="W")
    weekly = pd.DataFrame({
        "High": 5 + rng.normal(size=150), "Mid": rng.normal(size=150), "Low": -5 + rng.normal(size=150),
    }, index=weeks)
    out = offset_intervals(weekly, n_boot=300)
    assert out.loc["High", "offset_low"] > 0 > out.loc["Low", "offset_high"]
    assert out.loc["High", "rank_high"] == 1
    assert out.loc["Low", "rank_low"] == 3
    assert (out["offset_low"] <= out["offset"]).all() and (out["offset"] <= out["offset_high"]).all()


def test_a_change_near_the_end_of_the_series_is_found():
    level = np.r_[np.zeros(132), np.full(24, 0.4)]
    weekly = _weekly(level + np.random.default_rng(6).normal(scale=0.03, size=156))
    found = detect_level_shifts(weekly, n_perm=199)
    assert found["date"].tolist() == [weekly.index[132]]


def _hourly(hours):
    index = pd.date_range("2019-01-01", periods=hours, freq="h")
    return pd.concat([
        pd.DataFrame({"datetime": index, "district": d, "pm25": 10.0}) for d in ["A", "B"]
    ], ignore_index=True)


def test_station_outages_finds_long_runs_of_one_station():
    hourly = _hourly(200)
    hourly.loc[(hourly["district"] == "A") & (hourly["datetime"] >= "2019-01-02")
               & (hourly["datetime"] < "2019-01-06"), "pm25"] = np.nan
    hourly.loc[(hourly["district"] == "B") & (hourly["datetime"] < "2019-01-01 05:00"), "pm25"] = np.nan
    out = station_outages(hourly, "pm25")
    assert out["district"].tolist() == ["A"]
    assert out["days"].iloc[0] == 4.0
    assert out["start"].iloc[0] == pd.Timestamp("2019-01-02")


def test_station_outages_ignores_network_gaps():
    hourly = _hourly(200)
    hourly.loc[hourly["datetime"] < "2019-01-05", "pm25"] = np.nan
    assert station_outages(hourly, "pm25").empty


def test_change_around_compares_both_sides():
    weekly = _weekly(np.r_[np.zeros(20), np.ones(20)])
    assert change_around(weekly, weekly.index[20]) == pytest.approx(1)


def _shifts(dates, jumps):
    return pd.DataFrame({"date": pd.to_datetime(dates), "jump": jumps, "p_value": 0.01})


def test_agreed_shifts_need_the_same_sign_and_a_close_date():
    by_city = _shifts(["2018-01-07", "2018-06-03", "2019-01-06"], [0.3, 0.2, -0.3])
    by_near = _shifts(["2018-02-04", "2018-06-03", "2019-08-04"], [0.2, -0.2, -0.3])
    out = agreed_shifts(by_city, by_near)
    assert out["date"].tolist() == [pd.Timestamp("2018-01-07")]
    assert out["date_near"].tolist() == [pd.Timestamp("2018-02-04")]


def test_agreed_shifts_with_nothing_to_agree():
    empty = _shifts([], [])
    assert agreed_shifts(empty, empty).empty
    assert agreed_shifts(_shifts(["2018-01-07"], [0.3]), empty).empty


def test_shuffle_blocks_keeps_every_position_and_the_blocks():
    positions = shuffle_blocks(10, 4, np.random.default_rng(0))
    assert sorted(positions.tolist()) == list(range(10))
    start = positions.tolist().index(4)
    assert positions.tolist()[start:start + 4] == [4, 5, 6, 7]


def test_agreed_shifts_with_the_empty_result_of_the_detector():
    empty = detect_level_shifts(_weekly(np.zeros(156)), n_perm=9)
    out = agreed_shifts(_shifts(["2018-01-07"], [0.3]), empty)
    assert out.empty


def test_agreed_shifts_counts_a_repeated_detection_once():
    by_city = _shifts(["2017-12-03", "2017-12-10", "2019-07-07"], [-0.15, -0.20, 0.2])
    by_near = _shifts(["2017-12-17", "2019-07-28"], [-0.2, 0.3])
    out = agreed_shifts(by_city, by_near)
    assert out["date"].tolist() == [pd.Timestamp("2017-12-10"), pd.Timestamp("2019-07-07")]
