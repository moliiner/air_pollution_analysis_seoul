"""Next-day PM2.5 forecast: validation folds, models, alert calibration and evaluation.

Every choice (settings, model, alert threshold) is made on validation folds inside
the fit period. The evaluation rows are used only to score the final forecasts.
"""
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from seoul_air import config
from seoul_air.features import FEATURE_COLUMNS
from seoul_air.metrics import (alert, alert_scores, all_metrics, best_threshold, is_bad,
                               paired_block_bootstrap, threshold_scores)

CATEGORICAL = ["station_code", "target_weekday"]
NUMERIC = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL]
RIDGE_GRID = {"ridge__alpha": [0.1, 1, 10, 100]}
HGB_GRID = {
    "learning_rate": [0.03, 0.1],
    "max_leaf_nodes": [15, 31],
    "min_samples_leaf": [20, 80],
    "max_iter": [200, 400],
    "loss": ["squared_error", "absolute_error"],
}
ALERT_CANDIDATES = np.arange(20, 45.5, 0.5)
# Gradient boosting reads the categorical columns as integer codes, so it gets floats
NEEDS_FLOAT = {"ridge": False, "hist_gradient_boosting": True}


def split_by_target_date(table, train_end=config.TRAIN_END, test_start=config.TEST_START):
    """Fit rows (target up to train_end) and evaluation rows (target from test_start)."""
    train = table[table["target_date"] <= train_end].reset_index(drop=True)
    test = table[table["target_date"] >= test_start].reset_index(drop=True)
    return train, test


def quarterly_folds(target_dates, year=2018):
    """Expanding-window folds with one forecast origin at the start of each quarter.

    Each fold fits on every row before its origin and validates on that quarter.
    """
    target_dates = pd.Series(pd.to_datetime(target_dates)).reset_index(drop=True)
    folds, names = [], []
    for origin in pd.date_range(f"{year}-01-01", periods=4, freq="QS"):
        end = origin + pd.offsets.QuarterEnd(0)
        fit_idx = np.where(target_dates < origin)[0]
        val_idx = np.where((target_dates >= origin) & (target_dates <= end))[0]
        folds.append((fit_idx, val_idx))
        names.append(f"{origin.year}Q{origin.quarter}")
    return folds, names


def persistence_forecast(rows, fallback):
    """Tomorrow = today; the 7-day mean, then a fallback, when today is missing."""
    return rows["pm25_d0"].fillna(rows["pm25_roll7"]).fillna(fallback).to_numpy()


def climatology_forecast(train, rows):
    """Mean target of the same station and month in the fit rows."""
    means = train.groupby([train["station_code"], train["target_date"].dt.month])["target"].mean()
    keys = list(zip(rows["station_code"], rows["target_date"].dt.month))
    return pd.Series(means.reindex(keys).to_numpy()).fillna(train["target"].mean()).to_numpy()


def make_model(name):
    if name == "ridge":
        return make_pipeline(
            ColumnTransformer([
                ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), NUMERIC),
                ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ]),
            Ridge(),
        )
    if name == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(
            categorical_features=[FEATURE_COLUMNS.index(c) for c in CATEGORICAL], random_state=42)
    raise ValueError(f"unknown model: {name}")


def features(rows, name):
    X = rows[FEATURE_COLUMNS]
    return X.astype(float) if NEEDS_FLOAT.get(name, False) else X


def tune(name, train, folds, grid):
    """Grid search of one model on the validation folds, refit on all fit rows."""
    search = GridSearchCV(make_model(name), grid, cv=folds, scoring="neg_mean_absolute_error")
    return search.fit(features(train, name), train["target"])


def out_of_fold(train, folds, name=None, estimator=None):
    """Validation forecasts, each from a model fit only on the rows before its origin.

    Without a name and estimator, the forecast is persistence.
    """
    predictions = np.full(len(train), np.nan)
    for fit_idx, val_idx in folds:
        fit, val = train.iloc[fit_idx], train.iloc[val_idx]
        if estimator is None:
            predictions[val_idx] = persistence_forecast(val, fit["target"].mean())
        else:
            model = clone(estimator).fit(features(fit, name), fit["target"])
            predictions[val_idx] = model.predict(features(val, name))
    return predictions


def validation_mae(oof, train, folds, names):
    """MAE of each out-of-fold forecast by fold, and its mean over the folds."""
    rows = {}
    for name, pred in oof.items():
        rows[name] = [np.mean(np.abs(pred[v] - train["target"].to_numpy()[v])) for _, v in folds]
    table = pd.DataFrame(rows, index=names)
    table.loc["mean of folds"] = table.mean()
    return table


def calibrate_threshold(y_true, y_pred, candidates=ALERT_CANDIDATES):
    """Alert threshold with the highest F1, and the scores of every candidate."""
    scores = threshold_scores(y_true, y_pred, candidates)
    return best_threshold(scores), scores


def evaluate(y_true, predictions, thresholds):
    """Leaderboard of the forecasts, and alert scores with the grade rule and calibrated."""
    leaderboard = pd.DataFrame(
        [{"model": name, **all_metrics(y_true, pred)} for name, pred in predictions.items()]
    ).set_index("model").sort_values("mae")
    rows = []
    for name, threshold in thresholds.items():
        for label, value in [("grade rule", None), ("calibrated", threshold)]:
            rows.append({"forecast": name, "alert": label, "threshold": 35.5 if value is None else value,
                         **alert_scores(is_bad(y_true), alert(predictions[name], value))})
    return leaderboard, pd.DataFrame(rows).set_index(["forecast", "alert"])


def bootstrap_intervals(y_true, pred, base, blocks, threshold, base_threshold, n_boot=4000, seed=0):
    """95% intervals of pred minus base: MAE difference, skill and alert recall."""
    rows = []
    for label, alert_a, alert_b in [
        ("grade rule", None, None),
        ("calibrated", alert(pred, threshold), alert(base, base_threshold)),
    ]:
        draws = paired_block_bootstrap(y_true, pred, base, blocks, alert_a=alert_a, alert_b=alert_b,
                                       n_boot=n_boot, seed=seed)
        stats = ["mae_diff", "skill", "recall_diff"] if label == "grade rule" else ["recall_diff"]
        for stat in stats:
            low, high = draws[stat].quantile([0.025, 0.975])
            rows.append({"statistic": stat, "alert": label if stat == "recall_diff" else "",
                         "low_95": low, "high_95": high, "excludes_zero": bool(low > 0 or high < 0)})
    return pd.DataFrame(rows)


def run_forecast(table, grids=None, n_boot=4000):
    """Tune, choose, calibrate and evaluate the forecast end to end.

    Returns a dict with every intermediate result the notebook shows. Only the fit
    rows reach the choices; the evaluation rows are scored at the end.
    """
    grids = grids or {"ridge": RIDGE_GRID, "hist_gradient_boosting": HGB_GRID}
    train, test = split_by_target_date(table)
    folds, names = quarterly_folds(train["target_date"])

    searches = {name: tune(name, train, folds, grid) for name, grid in grids.items()}
    oof = {name: out_of_fold(train, folds, name, s.best_estimator_) for name, s in searches.items()}
    oof["persistence"] = out_of_fold(train, folds)
    by_fold = validation_mae(oof, train, folds, names)
    # Persistence is reported for comparison; the forecast chosen is the best tuned model
    selected = by_fold.loc["mean of folds", list(searches)].idxmin()

    validated = np.concatenate([v for _, v in folds])
    y_val = train["target"].to_numpy()[validated]
    calibration = {name: calibrate_threshold(y_val, oof[name][validated]) for name in [selected, "persistence"]}
    thresholds = {name: threshold for name, (threshold, _) in calibration.items()}

    fallback = train["target"].mean()
    predictions = {
        "persistence": persistence_forecast(test, fallback),
        "climatology": climatology_forecast(train, test),
        **{name: s.predict(features(test, name)) for name, s in searches.items()},
    }
    leaderboard, alerts = evaluate(test["target"], predictions, thresholds)
    weeks = test["target_date"].dt.to_period("W").astype(str)
    intervals = bootstrap_intervals(test["target"], predictions[selected], predictions["persistence"], weeks,
                                    thresholds[selected], thresholds["persistence"], n_boot=n_boot)
    return {
        "train": train, "test": test, "folds": folds, "fold_names": names, "searches": searches,
        "oof": oof, "validated": validated, "by_fold": by_fold, "selected": selected,
        "calibration": calibration, "thresholds": thresholds,
        "predictions": predictions, "leaderboard": leaderboard, "alerts": alerts,
        "intervals": intervals, "weeks": weeks,
    }
