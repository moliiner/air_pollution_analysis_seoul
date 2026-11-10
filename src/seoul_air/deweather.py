"""Weather normalisation ("deweathering") of the daily PM2.5 of Seoul with gradient boosting.

A model learns daily PM2.5 from the weather of the day and the day before, the time of
year, the weekday and a time variable for the long-term change. To remove the weather of a
particular day, the day is predicted many times with the weather of other days from the
same part of the year (any year), keeping its date, and the predictions are averaged. The
result keeps the seasonal cycle and the long-term change but not the weather of that
specific day, in the spirit of Grange et al. (2018) and the rmweather package.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

WEATHER_COLUMNS = [
    "temperature_mean_c", "temperature_min_c", "temperature_max_c", "relative_humidity_mean_pct",
    "precipitation_mm", "wind_speed_mean_ms", "wind_u_mean_ms", "wind_v_mean_ms",
    "boundary_layer_height_mean_m", "boundary_layer_height_max_m", "surface_pressure_mean_hpa",
]
LAGGED_COLUMNS = ["precipitation_mm", "wind_speed_mean_ms", "boundary_layer_height_mean_m",
                  "temperature_mean_c", "relative_humidity_mean_pct"]
TIME_COLUMNS = ["time_years", "doy_sin", "doy_cos", "weekday"]


def build_table(pm25, weather_daily):
    """One row per day: PM2.5, the weather of the day and of the day before, and time features.

    `pm25` is a daily Series with a DatetimeIndex; `weather_daily` has a `date` column.
    """
    weather = weather_daily.set_index("date")[WEATHER_COLUMNS].sort_index()
    lagged = weather[LAGGED_COLUMNS].shift(1, freq="D").add_suffix("_lag1")
    table = pd.DataFrame({"pm25": pm25}).join(weather, how="inner").join(lagged, how="left")
    dates = table.index
    table["time_years"] = (dates - pd.Timestamp("2015-01-01")).days / 365.25
    doy = dates.dayofyear
    table["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    table["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    table["weekday"] = dates.weekday
    return table


def weather_features(table):
    return [c for c in table.columns if c in WEATHER_COLUMNS or c.endswith("_lag1")]


def features(table):
    return weather_features(table) + TIME_COLUMNS


def make_model(seed=0, **params):
    options = {"max_iter": 400, "learning_rate": 0.05, "max_leaf_nodes": 31, "min_samples_leaf": 20}
    options.update(params)
    return HistGradientBoostingRegressor(random_state=seed, **options)


def leave_one_year_out(table, params=None):
    """Out-of-year predictions: each year is predicted by a model fit on all other years."""
    params = params or {}
    rows = table.dropna(subset=["pm25"])
    predictions = pd.Series(np.nan, index=rows.index)
    for year in sorted(rows.index.year.unique()):
        test = rows.index.year == year
        model = make_model(**params).fit(rows.loc[~test, features(rows)], rows.loc[~test, "pm25"])
        predictions[test] = model.predict(rows.loc[test, features(rows)])
    return predictions


def forward_chaining(table, first_test_year, params=None):
    """Predictions of each year from a model fit only on the earlier years."""
    params = params or {}
    rows = table.dropna(subset=["pm25"])
    predictions = pd.Series(np.nan, index=rows.index)
    for year in range(first_test_year, rows.index.year.max() + 1):
        train, test = rows.index.year < year, rows.index.year == year
        model = make_model(**params).fit(rows.loc[train, features(rows)], rows.loc[train, "pm25"])
        predictions[test] = model.predict(rows.loc[test, features(rows)])
    return predictions


def score_by_year(observed, predicted):
    """R2, MAE and bias of daily predictions, by year and overall."""
    frame = pd.DataFrame({"observed": observed, "predicted": predicted}).dropna()

    def score(part):
        error = part["predicted"] - part["observed"]
        r2 = 1 - (error ** 2).sum() / ((part["observed"] - part["observed"].mean()) ** 2).sum()
        return pd.Series({"days": len(part), "r2": r2, "mae": error.abs().mean(), "bias": error.mean()})

    by_year = frame.groupby(frame.index.year).apply(score)
    by_year.loc["all"] = score(frame)
    return by_year


def normalise(model, table, n_samples=200, window_days=15, seed=0, chunk=400):
    """Weather-normalised value of each day: the mean prediction over weather of similar dates.

    For each day, n_samples days are drawn whose day of year lies within window_days of it
    (in any year); their weather replaces the day's weather, while the time features stay.
    """
    rng = np.random.default_rng(seed)
    weather_cols = weather_features(table)
    columns = features(table)
    doy = table.index.dayofyear.to_numpy()
    weather = table[weather_cols].to_numpy()
    base = table[columns].to_numpy()
    weather_idx = [columns.index(c) for c in weather_cols]
    distance = np.abs(doy[:, None] - doy[None, :])
    distance = np.minimum(distance, 366 - distance)
    out = np.empty(len(table))
    for start in range(0, len(table), chunk):
        days = np.arange(start, min(start + chunk, len(table)))
        rows = []
        for day in days:
            candidates = np.flatnonzero(distance[day] <= window_days)
            picked = rng.choice(candidates, n_samples, replace=True)
            block = np.repeat(base[day][None, :], n_samples, axis=0)
            block[:, weather_idx] = weather[picked]
            rows.append(block)
        predictions = model.predict(pd.DataFrame(np.vstack(rows), columns=columns))
        out[days] = predictions.reshape(len(days), n_samples).mean(axis=1)
    return pd.Series(out, index=table.index, name="pm25_normalised")


def normalised_ensemble(table, n_models=10, block_days=30, params=None, seed=0, **normalise_options):
    """Weather-normalised series from n_models models, each fit on a block bootstrap of the days.

    Resampling blocks of consecutive days keeps their dependence; the spread of the members
    measures the uncertainty that comes from the model.
    """
    params = params or {}
    rows = table.dropna(subset=["pm25"])
    rng = np.random.default_rng(seed)
    n = len(rows)
    members = []
    for member in range(n_models):
        starts = rng.integers(0, n - block_days + 1, int(np.ceil(n / block_days)))
        picked = (starts[:, None] + np.arange(block_days)).ravel()[:n]
        sample = rows.iloc[picked]
        model = make_model(seed=member, **params).fit(sample[features(sample)], sample["pm25"])
        members.append(normalise(model, table, seed=seed + member, **normalise_options))
    return pd.concat(members, axis=1, keys=range(n_models))
