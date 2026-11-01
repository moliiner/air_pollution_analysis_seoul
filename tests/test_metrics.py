import pytest

from seoul_air.metrics import all_metrics, grade_metrics, regression_metrics


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
