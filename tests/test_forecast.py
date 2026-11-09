import numpy as np
import pandas as pd
import pytest

from seoul_air.features import FEATURE_COLUMNS
from seoul_air.forecast import (
    calibrate_threshold,
    climatology_forecast,
    evaluate,
    out_of_fold,
    persistence_forecast,
    quarterly_folds,
    run_forecast,
    split_by_target_date,
    validation_mae,
)

SMALL_GRIDS = {"ridge": {"ridge__alpha": [1, 10]},
               "hist_gradient_boosting": {"max_iter": [20], "learning_rate": [0.1]}}


def _table(seed=0):
    """Two stations, daily targets from 2017 to 2019, PM2.5 that persists from day to day."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2017-01-01", "2019-12-30", freq="D")
    frames = []
    for code in (101, 102):
        level = 25 + 15 * np.sin(2 * np.pi * dates.dayofyear / 365.25) + rng.normal(0, 3, len(dates))
        series = pd.Series(level).ewm(alpha=0.4).mean().to_numpy() + rng.normal(0, 4, len(dates))
        frame = pd.DataFrame({"station_code": code, "date": dates, "pm25_d0": series})
        for column in FEATURE_COLUMNS:
            if column not in frame:
                frame[column] = rng.normal(size=len(dates))
        frame["pm25_roll7"] = pd.Series(series).rolling(7, min_periods=1).mean().to_numpy()
        frame["target_weekday"] = (dates + pd.Timedelta(days=1)).weekday
        frame["target_date"] = dates + pd.Timedelta(days=1)
        frame["target"] = np.r_[series[1:], np.nan]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).dropna(subset=["target"]).reset_index(drop=True)


def test_split_by_target_date():
    train, test = split_by_target_date(_table())
    assert train["target_date"].max() <= pd.Timestamp("2018-12-31")
    assert test["target_date"].min() >= pd.Timestamp("2019-01-01")


def test_quarterly_folds_never_fit_on_the_future():
    train, _ = split_by_target_date(_table())
    folds, names = quarterly_folds(train["target_date"])
    assert names == ["2018Q1", "2018Q2", "2018Q3", "2018Q4"]
    for (fit_idx, val_idx), origin in zip(folds, pd.date_range("2018-01-01", periods=4, freq="QS")):
        assert train["target_date"].iloc[fit_idx].max() < origin
        assert train["target_date"].iloc[val_idx].min() >= origin
        assert train["target_date"].iloc[val_idx].max() <= origin + pd.offsets.QuarterEnd(0)
    validated = np.concatenate([v for _, v in folds])
    assert train["target_date"].iloc[validated].dt.year.eq(2018).all()
    assert len(set(validated)) == (train["target_date"].dt.year == 2018).sum()


def test_persistence_falls_back_in_order():
    rows = pd.DataFrame({"pm25_d0": [10.0, np.nan, np.nan], "pm25_roll7": [5.0, 7.0, np.nan]})
    assert persistence_forecast(rows, 99.0).tolist() == [10.0, 7.0, 99.0]


def test_climatology_uses_station_and_month():
    train = pd.DataFrame({"station_code": [101, 101, 102], "target": [10.0, 20.0, 40.0],
                          "target_date": pd.to_datetime(["2018-01-05", "2018-01-20", "2018-01-05"])})
    rows = pd.DataFrame({"station_code": [101, 102, 101],
                         "target_date": pd.to_datetime(["2019-01-10", "2019-01-10", "2019-02-10"])})
    assert climatology_forecast(train, rows).tolist() == pytest.approx([15.0, 40.0, 70 / 3])


def test_out_of_fold_matches_a_model_fit_on_earlier_rows_only():
    from sklearn.linear_model import LinearRegression

    train, _ = split_by_target_date(_table())
    folds, _ = quarterly_folds(train["target_date"])

    oof = out_of_fold(train, folds, "linear", LinearRegression())
    fit_idx, val_idx = folds[2]
    manual = LinearRegression().fit(train.iloc[fit_idx][FEATURE_COLUMNS], train.iloc[fit_idx]["target"])
    expected = manual.predict(train.iloc[val_idx][FEATURE_COLUMNS])
    assert np.allclose(oof[val_idx], expected)
    validated = np.concatenate([v for _, v in folds])
    assert np.isnan(np.delete(oof, validated)).all()


def test_validation_mae_has_a_mean_row():
    train, _ = split_by_target_date(_table())
    folds, names = quarterly_folds(train["target_date"])
    table = validation_mae({"persistence": out_of_fold(train, folds)}, train, folds, names)
    assert list(table.index) == [*names, "mean of folds"]
    assert table.loc["mean of folds", "persistence"] == pytest.approx(table.loc[names, "persistence"].mean())


def test_calibrate_threshold_picks_the_best_f1():
    threshold, scores = calibrate_threshold([40.0, 50.0, 10.0, 20.0], [30.0, 45.0, 25.0, 10.0], [20, 30, 40])
    assert threshold == 30
    assert len(scores) == 3


def test_evaluate_scores_both_alert_rules():
    y = pd.Series([40.0, 50.0, 10.0, 20.0])
    leaderboard, alerts = evaluate(y, {"a": np.array([30.0, 45.0, 25.0, 10.0]), "b": y.to_numpy()}, {"a": 30})
    assert leaderboard.index[0] == "b"
    assert alerts.loc[("a", "grade rule"), "bad_recall"] == 0.5
    assert alerts.loc[("a", "calibrated"), "bad_recall"] == 1.0


def test_run_forecast_end_to_end():
    result = run_forecast(_table(), grids=SMALL_GRIDS, n_boot=200)
    assert result["selected"] in SMALL_GRIDS
    assert set(result["leaderboard"].index) == {"ridge", "hist_gradient_boosting", "persistence", "climatology"}
    assert result["thresholds"][result["selected"]] in set(np.arange(20, 45.5, 0.5))
    assert len(result["intervals"]) == 4


def test_choices_do_not_depend_on_the_evaluation_year():
    table = _table()
    changed = table.copy()
    in_2019 = changed["target_date"] >= "2019-01-01"
    changed.loc[in_2019, "target"] = changed.loc[in_2019, "target"] * 3 + 50
    a = run_forecast(table, grids=SMALL_GRIDS, n_boot=50)
    b = run_forecast(changed, grids=SMALL_GRIDS, n_boot=50)
    assert a["selected"] == b["selected"]
    assert a["thresholds"] == b["thresholds"]
    assert {k: s.best_params_ for k, s in a["searches"].items()} == \
           {k: s.best_params_ for k, s in b["searches"].items()}
    pd.testing.assert_frame_equal(a["by_fold"], b["by_fold"])
    assert not a["leaderboard"].equals(b["leaderboard"])
