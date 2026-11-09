import numpy as np
import pandas as pd
import pytest

from seoul_air.grades import pm_grade
from seoul_air.metrics import (
    alert,
    all_metrics,
    best_threshold,
    grade_metrics,
    is_bad,
    paired_block_bootstrap,
    regression_metrics,
    threshold_scores,
)


def test_regression_metrics():
    m = regression_metrics([10, 20], [12, 16])
    assert m["mae"] == pytest.approx(3.0)
    assert m["bias"] == pytest.approx(-1.0)


def test_bad_day_recall_and_precision():
    # true Bad days: 40, 50 ; predicted Bad: 40, 10->36
    m = grade_metrics([40, 50, 10], [40, 20, 36])
    assert m["bad_recall"] == pytest.approx(0.5)
    assert m["bad_precision"] == pytest.approx(0.5)


def test_perfect_forecast():
    m = all_metrics([5, 20, 40, 80], [5, 20, 40, 80])
    assert m["mae"] == 0 and m["grade_accuracy"] == 1 and m["bad_recall"] == 1


def test_alert_and_grade_use_the_same_rounding():
    values = np.array([34.5, 35.0, 35.4, 35.5, 35.6, 36.0, 36.5, 75.4, 75.6, np.nan])
    grade_is_bad = pm_grade(np.round(values), "pm25").isin(["Bad", "Very bad"]).to_numpy()
    assert (is_bad(values) == grade_is_bad).all()
    assert is_bad([35.4]).tolist() == [False]
    assert is_bad([35.6]).tolist() == [True]


def test_a_mean_just_above_35_is_not_a_bad_day():
    # Before the fix, 35.3 counted as Bad for the alert but Moderate for the grade
    m = grade_metrics([35.3, 50.0], [35.3, 50.0])
    assert m["grade_accuracy"] == 1
    assert m["bad_precision"] == 1 and m["bad_recall"] == 1


def test_alert_with_a_threshold():
    assert alert([20.0, 30.0, 36.0]).tolist() == [False, False, True]
    assert alert([20.0, 30.0, 36.0], threshold=30).tolist() == [False, True, True]
    m = grade_metrics([40.0, 50.0, 10.0], [31.0, 29.0, 10.0], alert_threshold=30)
    assert m["bad_recall"] == pytest.approx(0.5) and m["bad_precision"] == 1


def test_threshold_scores_and_best_threshold():
    y_true = [40.0, 50.0, 10.0, 20.0]
    y_pred = [30.0, 45.0, 25.0, 10.0]
    scores = threshold_scores(y_true, y_pred, [20, 30, 40])
    assert scores["bad_recall"].tolist() == [1.0, 1.0, 0.5]
    assert best_threshold(scores) == 30


def test_best_threshold_breaks_ties_upwards():
    scores = pd.DataFrame({"threshold": [25.0, 30.0, 35.0], "bad_f1": [0.5, 0.8, 0.8]})
    assert best_threshold(scores) == 35


def test_bootstrap_of_identical_forecasts_has_no_difference():
    rng = np.random.default_rng(0)
    y = rng.uniform(0, 80, 200)
    pred = y + rng.normal(0, 5, 200)
    draws = paired_block_bootstrap(y, pred, pred, np.repeat(np.arange(20), 10), n_boot=200)
    assert (draws["mae_diff"] == 0).all() and (draws["recall_diff"].dropna() == 0).all()


def test_bootstrap_finds_a_clearly_better_forecast():
    rng = np.random.default_rng(1)
    y = rng.uniform(0, 80, 400)
    good = y + rng.normal(0, 2, 400)
    poor = y + rng.normal(0, 10, 400)
    draws = paired_block_bootstrap(y, good, poor, np.repeat(np.arange(40), 10), n_boot=500)
    assert draws["mae_diff"].quantile(0.975) < 0
    assert 0 < draws["skill"].quantile(0.025)


def test_bootstrap_keeps_blocks_together_and_matches_the_full_sample_on_average():
    y = np.array([10.0, 50.0, 20.0, 60.0])
    a = np.array([12.0, 40.0, 20.0, 70.0])
    b = y.copy()
    draws = paired_block_bootstrap(y, a, b, ["w1", "w1", "w2", "w2"], n_boot=2000, seed=3)
    # Each draw holds whole weeks: MAE of week 1 is 6, of week 2 is 5
    assert set(np.round(draws["mae_a"], 6)) <= {5.0, 5.5, 6.0}
    assert draws["mae_a"].mean() == pytest.approx(5.5, abs=0.05)
    assert draws["recall_b"].dropna().eq(1).all()
