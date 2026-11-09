"""Forecast metrics: errors on the concentration and on the Korean PM2.5 grade."""
import numpy as np
import pandas as pd

from seoul_air.grades import pm_grade

BAD_THRESHOLD_PM25 = 35  # a 24-hour mean above this, once rounded, is graded Bad or Very bad
BAD_GRADES = ("Bad", "Very bad")


def is_bad(values):
    """Bad-or-worse PM2.5 grade, with the rounding used by pm_grade.

    Grades have integer bounds, so a continuous daily mean is rounded first:
    35.4 is Moderate and 35.6 is Bad. Missing values are not Bad.
    """
    return np.round(np.asarray(values, dtype=float)) > BAD_THRESHOLD_PM25


def regression_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_pred - y_true
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "bias": float(np.mean(err)),
    }


def alert_scores(bad_true, alert):
    """Precision, recall and F1 of an alert against the days that were Bad or worse."""
    bad_true = np.asarray(bad_true, dtype=bool)
    alert = np.asarray(alert, dtype=bool)
    tp = int((bad_true & alert).sum())
    precision = tp / alert.sum() if alert.sum() else float("nan")
    recall = tp / bad_true.sum() if bad_true.sum() else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall > 0 else float("nan"))
    return {"bad_precision": float(precision), "bad_recall": float(recall), "bad_f1": float(f1)}


def alert(y_pred, threshold=None):
    """Bad-or-worse alert from a forecast.

    Without a threshold the alert follows the grade of the forecast (is_bad); with
    one, it is raised when the forecast reaches the threshold.
    """
    if threshold is None:
        return is_bad(y_pred)
    return np.asarray(y_pred, dtype=float) >= threshold


def grade_metrics(y_true, y_pred, alert_threshold=None):
    """Grade accuracy, and precision / recall / F1 of the Bad-or-worse alert."""
    g_true = pm_grade(np.round(y_true), "pm25")
    g_pred = pm_grade(np.round(np.clip(y_pred, 0, None)), "pm25")
    return {
        "grade_accuracy": float((pd.Series(g_true) == pd.Series(g_pred)).mean()),
        **alert_scores(is_bad(y_true), alert(y_pred, alert_threshold)),
    }


def all_metrics(y_true, y_pred, alert_threshold=None):
    return {**regression_metrics(y_true, y_pred), **grade_metrics(y_true, y_pred, alert_threshold)}


def threshold_scores(y_true, y_pred, thresholds):
    """Alert precision, recall and F1 for each candidate threshold."""
    bad_true = is_bad(y_true)
    rows = [{"threshold": t, **alert_scores(bad_true, alert(y_pred, t))} for t in thresholds]
    return pd.DataFrame(rows)


def best_threshold(scores):
    """Threshold with the highest F1; ties go to the highest threshold (fewer alerts)."""
    best = scores["bad_f1"].max()
    return float(scores.loc[scores["bad_f1"] == best, "threshold"].max())


def paired_block_bootstrap(y_true, pred_a, pred_b, blocks, alert_a=None, alert_b=None,
                           n_boot=2000, seed=0):
    """Bootstrap draws of the MAE and alert recall of two forecasts of the same rows.

    Whole blocks (for example weeks) are resampled, so that rows of the same block,
    which are not independent, stay together. Both forecasts are scored on the same
    draw, which makes their difference precise. Alerts default to the grade rule.
    """
    y_true = np.asarray(y_true, dtype=float)
    codes, _ = pd.factorize(np.asarray(blocks))
    n_blocks = codes.max() + 1
    bad = is_bad(y_true)
    alert_a = is_bad(pred_a) if alert_a is None else np.asarray(alert_a, dtype=bool)
    alert_b = is_bad(pred_b) if alert_b is None else np.asarray(alert_b, dtype=bool)

    def per_block(values):
        return np.bincount(codes, weights=np.asarray(values, dtype=float), minlength=n_blocks)

    rows = per_block(np.ones_like(y_true))
    err_a = per_block(np.abs(np.asarray(pred_a, dtype=float) - y_true))
    err_b = per_block(np.abs(np.asarray(pred_b, dtype=float) - y_true))
    bad_days = per_block(bad)
    hits_a = per_block(bad & alert_a)
    hits_b = per_block(bad & alert_b)

    rng = np.random.default_rng(seed)
    weights = np.stack([np.bincount(rng.integers(0, n_blocks, n_blocks), minlength=n_blocks)
                        for _ in range(n_boot)])
    n = weights @ rows
    # A draw without Bad days has no recall, and a perfect forecast b no skill: NaN or inf
    with np.errstate(divide="ignore", invalid="ignore"):
        mae_a = weights @ err_a / n
        mae_b = weights @ err_b / n
        recall_a = weights @ hits_a / (weights @ bad_days)
        recall_b = weights @ hits_b / (weights @ bad_days)
        skill = 1 - mae_a / mae_b
    return pd.DataFrame({
        "mae_a": mae_a, "mae_b": mae_b, "mae_diff": mae_a - mae_b, "skill": skill,
        "recall_a": recall_a, "recall_b": recall_b, "recall_diff": recall_a - recall_b,
    })
