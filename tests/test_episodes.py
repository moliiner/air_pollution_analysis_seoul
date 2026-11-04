import numpy as np
import pandas as pd

from seoul_air.episodes import find_episodes, find_runs


def _series(values):
    return pd.Series(values, index=pd.date_range("2019-01-01", periods=len(values), freq="D"), dtype=float)


def test_find_runs_groups_consecutive_days():
    runs = find_runs(_series([1, 1, 0, 1, 0, 1, 1, 1]) == 1)
    assert runs["days"].tolist() == [2, 1, 3]
    assert runs["start"].iloc[2] == pd.Timestamp("2019-01-06")
    assert runs["end"].iloc[2] == pd.Timestamp("2019-01-08")


def test_find_runs_without_any_day():
    assert find_runs(_series([0, 0]) == 1).empty


def test_episode_threshold_uses_the_rounded_mean():
    assert len(find_episodes(_series([35.4, 10]))) == 0
    assert len(find_episodes(_series([35.6, 10]))) == 1


def test_gap_ends_a_run_and_is_flagged():
    runs = find_episodes(_series([40, np.nan, 50, 60, 10, 45]))
    assert runs["days"].tolist() == [1, 2, 1]
    assert runs["gap_after"].tolist() == [True, False, False]
    assert runs["gap_before"].tolist() == [False, True, False]
    assert runs["peak_pm25"].tolist() == [40, 60, 45]


def test_series_edges_are_not_gaps():
    runs = find_episodes(_series([40, 50]))
    assert not runs["gap_before"].iloc[0] and not runs["gap_after"].iloc[0]
