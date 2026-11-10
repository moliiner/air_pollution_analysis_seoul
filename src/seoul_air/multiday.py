"""Forecast of Seoul's daily PM2.5 one to three days ahead, issued at 17:00 KST.

The Korean forecast (NIER) is announced at 17:00 for the following days, so the forecast
here is issued at 17:00 KST of an issue day D for the target days D+1, D+2 and D+3. The
target is the city daily PM2.5: the mean of the daily means of the 25 urban stations.

Only data published before 17:00 enter a forecast:
- Pollution: hourly readings up to the hour 15:00-16:00 (start label 15:00, ISSUE_LAST_HOUR).
  Official readings are published as soon as the hour ends; one hour of margin is kept.
- Regional background (Baengnyeong) and observed weather (ERA5 as a stand-in for the
  real-time observations): the same hours.
- Weather forecasts: archived JMA forecasts made at least a day before (see `nwp`).
- CAMS: hours up to 08:00 KST of D, which come from runs started by 12 UTC of D-1.
Every window is computed from a complete hourly grid with a trailing rolling mean that
ends at the issue hour, so a value after that hour can never enter (tested).
"""
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from seoul_air.grades import pm_grade
from seoul_air.metrics import alert_scores, is_bad, regression_metrics

ISSUE_HOUR = 17
ISSUE_LAST_HOUR = 15  # start label of the last hourly reading used
CAMS_LAST_HOUR = 8
HORIZONS = (1, 2, 3)
QUANTILES = (0.1, 0.5, 0.9)
MIN_SHARE = 0.75  # share of the hours of a window that must have a value


def hourly_grid(frame):
    """Reindex an hourly frame (DatetimeIndex) to every hour, so windows count real hours."""
    full = pd.date_range(frame.index.min().normalize(), frame.index.max().normalize() + pd.Timedelta(hours=23), freq="h")
    return frame.reindex(full)


def at_issue(series, hours, issue_dates, how="mean", last_hour=ISSUE_LAST_HOUR, lag_hours=0, min_share=MIN_SHARE):
    """Statistic of the `hours` hourly values that end at `last_hour` of each issue date.

    lag_hours moves the window back (24 = the same window one day earlier). The window
    of an issue date D covers start labels from D + last_hour - lag - hours + 1 to
    D + last_hour - lag.
    """
    rolling = series.rolling(hours, min_periods=max(1, int(np.ceil(hours * min_share))))
    values = getattr(rolling, how)()
    stamps = pd.DatetimeIndex(issue_dates) + pd.Timedelta(hours=last_hour - lag_hours)
    return pd.Series(values.reindex(stamps).to_numpy(), index=pd.DatetimeIndex(issue_dates))


def air_features(city, issue_dates):
    """Pollution of the city known at issue time (city = hourly city means, complete grid)."""
    f = pd.DataFrame(index=pd.DatetimeIndex(issue_dates))
    pm25 = city["pm25"]
    f["pm25_last3h"] = at_issue(pm25, 3, issue_dates)
    f["pm25_today"] = at_issue(pm25, ISSUE_LAST_HOUR + 1, issue_dates)
    f["pm25_24h"] = at_issue(pm25, 24, issue_dates)
    f["pm25_prev_24h"] = at_issue(pm25, 24, issue_dates, lag_hours=24)
    f["pm25_7d"] = at_issue(pm25, 168, issue_dates)
    f["pm25_max_today"] = at_issue(pm25, ISSUE_LAST_HOUR + 1, issue_dates, how="max")
    f["pm25_change_24h"] = f["pm25_24h"] - f["pm25_prev_24h"]
    f["pm10_24h"] = at_issue(city["pm10"], 24, issue_dates)
    f["pm10_last3h"] = at_issue(city["pm10"], 3, issue_dates)
    f["pm_ratio_24h"] = f["pm25_24h"] / f["pm10_24h"]
    f["no2_24h"] = at_issue(city["no2"], 24, issue_dates)
    f["co_24h"] = at_issue(city["co"], 24, issue_dates)
    f["o3_max_today"] = at_issue(city["o3"], ISSUE_LAST_HOUR + 1, issue_dates, how="max")
    return f


def background_features(background, issue_dates):
    """Baengnyeong readings known at issue time (background = hourly, complete grid)."""
    f = pd.DataFrame(index=pd.DatetimeIndex(issue_dates))
    f["bg_pm25_6h"] = at_issue(background["pm25"], 6, issue_dates)
    f["bg_pm25_24h"] = at_issue(background["pm25"], 24, issue_dates)
    f["bg_pm25_prev_24h"] = at_issue(background["pm25"], 24, issue_dates, lag_hours=24)
    f["bg_pm10_24h"] = at_issue(background["pm10"], 24, issue_dates)
    f["bg_pm10_6h"] = at_issue(background["pm10"], 6, issue_dates)
    return f


def observed_weather_features(weather, issue_dates):
    """Observed weather up to the issue time (weather = hourly ERA5 in KST, complete grid)."""
    f = pd.DataFrame(index=pd.DatetimeIndex(issue_dates))
    hours = ISSUE_LAST_HOUR + 1
    for column, name in [("temperature_c", "temp"), ("relative_humidity_pct", "rh"), ("wind_speed_ms", "wind"),
                         ("wind_u_ms", "wind_u"), ("wind_v_ms", "wind_v"), ("boundary_layer_height_m", "blh")]:
        f[f"obs_{name}_today"] = at_issue(weather[column], hours, issue_dates)
    f["obs_precip_24h"] = at_issue(weather["precipitation_mm"], 24, issue_dates, how="sum")
    pressure = weather["surface_pressure_hpa"]
    f["obs_pressure_change_24h"] = (at_issue(pressure, 1, issue_dates)
                                    - at_issue(pressure, 1, issue_dates, lag_hours=24))
    return f


def cams_features(cams, issue_dates):
    """CAMS PM2.5 and dust upwind, 24 hours ending at 08:00 KST of the issue day."""
    f = pd.DataFrame(index=pd.DatetimeIndex(issue_dates))
    for (variable, point) in cams.columns:
        if variable in ("pm2_5", "dust"):
            f[f"cams_{variable}_{point}"] = at_issue(cams[(variable, point)], 24, issue_dates,
                                                    last_hour=CAMS_LAST_HOUR)
    return f


def calendar_features(target_dates):
    dates = pd.DatetimeIndex(target_dates)
    doy = dates.dayofyear.to_numpy()
    return pd.DataFrame({"target_doy_sin": np.sin(2 * np.pi * doy / 365.25),
                         "target_doy_cos": np.cos(2 * np.pi * doy / 365.25),
                         "target_weekday": dates.weekday}, index=dates)


def build_tables(city_daily, issue_features, nwp_daily=None, horizons=HORIZONS):
    """One table per horizon: features of the issue day, calendar of the target day, target.

    issue_features: features indexed by issue date (all known at 17:00 KST).
    nwp_daily: `nwp.daily_forecasts` output (columns by horizon), or None.
    """
    tables = {}
    for h in horizons:
        issue = issue_features.index
        target_dates = issue + pd.Timedelta(days=h)
        table = issue_features.copy()
        table["target_date"] = target_dates
        table = table.join(calendar_features(target_dates).set_axis(issue))
        if nwp_daily is not None:
            table = table.join(nwp_daily[h].reindex(target_dates).set_axis(issue))
        table["target"] = city_daily.reindex(target_dates).to_numpy()
        tables[h] = table
    return tables


def climatology(train_dates, train_values, dates, window_days=15, quantile=None):
    """Mean (or quantile) of the training values within window_days of each date's day of year."""
    train_doy = pd.DatetimeIndex(train_dates).dayofyear.to_numpy()
    values = np.asarray(train_values, dtype=float)
    out = np.empty(len(dates))
    for i, doy in enumerate(pd.DatetimeIndex(dates).dayofyear.to_numpy()):
        distance = np.abs(train_doy - doy)
        near = np.minimum(distance, 366 - distance) <= window_days
        sample = values[near & ~np.isnan(values)]
        out[i] = sample.mean() if quantile is None else np.quantile(sample, quantile)
    return out


def make_ridge(alpha=10.0):
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=alpha))
    return TransformedTargetRegressor(model, func=np.log1p, inverse_func=np.expm1)


def make_hgb(seed=0, loss="squared_error", quantile=None, **params):
    options = {"max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 30,
               "l2_regularization": 1.0}
    options.update(params)
    if loss == "quantile":
        return HistGradientBoostingRegressor(loss="quantile", quantile=quantile, random_state=seed, **options)
    return HistGradientBoostingRegressor(loss=loss, random_state=seed, **options)


def make_classifier(seed=0, **params):
    options = {"max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 30,
               "l2_regularization": 1.0}
    options.update(params)
    return HistGradientBoostingClassifier(random_state=seed, **options)


def rolling_origins(table, origins, fit_predict, train_start=None):
    """Out-of-sample predictions: for each origin, fit on the past and forecast its period.

    origins: list of (start, end) Timestamps; the rows issued in [start, end] are forecast
    by a model fit on rows whose target date is before start. fit_predict(train, test)
    returns a DataFrame of predictions indexed like test.
    """
    out = []
    rows = table.dropna(subset=["target"])
    for start, end in origins:
        train = rows[rows["target_date"] < start]
        if train_start is not None:
            train = train[train.index >= pd.Timestamp(train_start)]
        test = rows[(rows.index >= start) & (rows.index <= end)]
        if len(test) == 0:
            continue
        predictions = fit_predict(train, test)
        predictions["origin"] = start
        out.append(predictions)
    return pd.concat(out)


def yearly_origins(years):
    return [(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-31")) for y in years]


def quarterly_origins(first, last):
    starts = pd.date_range(first, last, freq="QS")
    return [(s, s + pd.offsets.QuarterEnd(0)) for s in starts]


def scores(y_true, y_pred, alert=None):
    """Regression, grade and Bad-or-worse alert scores (POD, FAR, CSI) of one forecast."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    keep = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_true, y_pred = y_true[keep], y_pred[keep]
    alert = is_bad(y_pred) if alert is None else np.asarray(alert, dtype=bool)[keep]
    bad = is_bad(y_true)
    tp, fp, fn = int((bad & alert).sum()), int((~bad & alert).sum()), int((bad & ~alert).sum())
    grade_true = pm_grade(np.round(y_true), "pm25")
    grade_pred = pm_grade(np.round(np.clip(y_pred, 0, None)), "pm25")
    alerts = alert_scores(bad, alert)
    return {
        "days": int(len(y_true)), **regression_metrics(y_true, y_pred),
        "grade_accuracy": float(np.mean(np.asarray(grade_true) == np.asarray(grade_pred))),
        "bad_days": int(bad.sum()), "alerts": int(alert.sum()),
        "pod": alerts["bad_recall"], "far": fp / (tp + fp) if tp + fp else float("nan"),
        "csi": tp / (tp + fp + fn) if tp + fp + fn else float("nan"), "f1": alerts["bad_f1"],
    }


def pinball(y_true, y_pred, quantile):
    error = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.nanmean(np.maximum(quantile * error, (quantile - 1) * error)))


def interval_scores(y_true, low, high, nominal=0.8):
    y_true = np.asarray(y_true, dtype=float)
    inside = (y_true >= np.asarray(low)) & (y_true <= np.asarray(high))
    return {"nominal": nominal, "coverage": float(np.mean(inside)), "mean_width": float(np.mean(np.asarray(high) - np.asarray(low)))}


def best_probability_threshold(bad_true, probability, candidates=np.arange(0.05, 0.951, 0.01)):
    """Probability threshold with the highest F1 (ties: the highest threshold)."""
    rows = [(t, alert_scores(bad_true, probability >= t)["bad_f1"]) for t in candidates]
    frame = pd.DataFrame(rows, columns=["threshold", "f1"])
    best = frame["f1"].max()
    return float(frame.loc[frame["f1"] == best, "threshold"].max())


def conformal_widening(y_true, low, high, coverage=0.8):
    """Amount to move both ends of an interval out so that it covers `coverage` of these days.

    Conformalised quantile regression (Romano et al. 2019): the score of a day is how far
    the observation lies outside the interval (negative inside); the widening is the
    finite-sample quantile of the scores. It is computed on validation days and applied
    unchanged to later days.
    """
    y_true, low, high = (np.asarray(a, dtype=float) for a in (y_true, low, high))
    keep = ~np.isnan(y_true)
    score = np.maximum(low[keep] - y_true[keep], y_true[keep] - high[keep])
    n = len(score)
    level = min(1.0, np.ceil((n + 1) * coverage) / n)
    return float(np.quantile(score, level, method="higher"))
