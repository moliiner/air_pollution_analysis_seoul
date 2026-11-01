"""Forecast metrics: errors on the concentration and on the Korean PM2.5 grade."""
import numpy as np
import pandas as pd

from seoul_air.grades import pm_grade

BAD_THRESHOLD_PM25 = 35  # above this a 24-hour mean is graded Bad or Very bad


def regression_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_pred - y_true
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "bias": float(np.mean(err)),
    }


def grade_metrics(y_true, y_pred):
    """Grade accuracy, and precision / recall / F1 of the Bad-or-worse alert."""
    # Grades use integer bounds, so round the continuous means before grading
    g_true = pm_grade(np.round(y_true), "pm25")
    g_pred = pm_grade(np.round(np.clip(y_pred, 0, None)), "pm25")
    bad_true = np.asarray(y_true, dtype=float) > BAD_THRESHOLD_PM25
    bad_pred = np.asarray(y_pred, dtype=float) > BAD_THRESHOLD_PM25
    tp = int((bad_true & bad_pred).sum())
    precision = tp / bad_pred.sum() if bad_pred.sum() else float("nan")
    recall = tp / bad_true.sum() if bad_true.sum() else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall > 0 else float("nan"))
    return {
        "grade_accuracy": float((pd.Series(g_true) == pd.Series(g_pred)).mean()),
        "bad_precision": float(precision),
        "bad_recall": float(recall),
        "bad_f1": float(f1),
    }


def all_metrics(y_true, y_pred):
    return {**regression_metrics(y_true, y_pred), **grade_metrics(y_true, y_pred)}
