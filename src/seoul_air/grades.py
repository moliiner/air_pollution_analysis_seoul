"""Korean particulate matter grades (Ministry of Environment, 2018 standard).

Ranges are inclusive upper bounds in ug/m3 for the 24-hour average:
PM10  Good 0-30, Moderate 31-80, Bad 81-150, Very bad 151+
PM2.5 Good 0-15, Moderate 16-35, Bad 36-75,  Very bad 76+
"""
import numpy as np
import pandas as pd

GRADE_LABELS = ["Good", "Moderate", "Bad", "Very bad"]

_UPPER_BOUNDS = {
    "pm10": [30, 80, 150],
    "pm25": [15, 35, 75],
}


def pm_grade(values, pollutant):
    """Return the Korean grade of each concentration as an ordered categorical.

    Missing or negative concentrations get a missing grade.
    """
    if pollutant not in _UPPER_BOUNDS:
        raise ValueError(f"pollutant must be one of {sorted(_UPPER_BOUNDS)}")
    values = pd.Series(values, dtype="float64")
    bins = [-np.inf, *_UPPER_BOUNDS[pollutant], np.inf]
    # Published values are integers, so (30, 31] belongs to Moderate
    grades = pd.cut(values, bins=bins, labels=GRADE_LABELS, right=True)
    return grades.where(values >= 0)
