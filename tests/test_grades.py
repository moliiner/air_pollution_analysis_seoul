import pandas as pd
import pytest

from seoul_air.grades import pm_grade


@pytest.mark.parametrize(
    "pollutant, value, expected",
    [
        ("pm25", 0, "Good"),
        ("pm25", 15, "Good"),
        ("pm25", 16, "Moderate"),
        ("pm25", 35, "Moderate"),
        ("pm25", 36, "Bad"),
        ("pm25", 76, "Very bad"),
        ("pm10", 30, "Good"),
        ("pm10", 31, "Moderate"),
        ("pm10", 150, "Bad"),
        ("pm10", 151, "Very bad"),
    ],
)
def test_grade_boundaries(pollutant, value, expected):
    assert pm_grade([value], pollutant).iloc[0] == expected


def test_invalid_values_get_missing_grade():
    grades = pm_grade([-1, None], "pm25")
    assert grades.isna().all()


def test_unknown_pollutant_raises():
    with pytest.raises(ValueError):
        pm_grade([10], "o3")


def test_drop_with_report_counts(tiny_frame, capsys):
    from seoul_air.data import drop_with_report

    out = drop_with_report(tiny_frame, tiny_frame["pm25"] < 0, "Negative PM2.5")
    assert len(out) == 3
    assert "dropped 1 rows" in capsys.readouterr().out


def test_grade_is_ordered():
    grades = pm_grade(pd.Series([10, 50]), "pm25")
    assert grades.cat.ordered
