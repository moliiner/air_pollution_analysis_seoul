"""Monthly and annual PM2.5 of Seoul two to three years ahead, with simulated paths.

Every model works on log monthly PM2.5 (concentrations are right-skewed and their
changes roughly proportional) and returns simulated paths, from which the median, the
intervals, the annual means, the chance of meeting the annual standard and the expected
Bad days all follow in the same way.

Models
- seasonal mean: the mean of each calendar month over the last three years, plus
  resampled residuals; no trend.
- ETS: exponential smoothing with additive level and season, no trend.
- damped trend: exponential smoothing with an additive damped trend and season.
- SARIMA: seasonal ARIMA with one seasonal difference and a drift; the order is chosen by
  AIC on the training months among three fixed candidates.
- deweathered (ML): the gradient boosting weather normalisation of notebook 09, fit only
  on the training days; a damped-trend model forecasts the weather-normalised series, and
  the weather is added back as the anomalies (observed minus normalised) of a whole
  training year drawn at random, which keeps the weather of the months of a year together.

These are statistical extrapolations of 2015-2025. They do not anticipate shocks: a new
policy, an economic or emission change in Korea or China, a pandemic, a change of the
measuring network, or an unusual weather year beyond those of 2015-2025.
"""
import warnings

import numpy as np
import pandas as pd

MODELS = ["seasonal mean", "ETS", "damped trend", "SARIMA", "deweathered (ML)"]  # simplest first
HORIZON = 36
SEASON = 12
SARIMA_ORDERS = [((1, 0, 0), (0, 1, 1, 12)), ((1, 0, 1), (0, 1, 1, 12)), ((2, 0, 0), (0, 1, 1, 12))]

# Selection rule, fixed before any model was evaluated
COVERAGE_RANGE = (0.70, 0.90)  # pooled coverage of the 80% interval needed to be eligible
TIE_MARGIN = 0.05  # models within 5% of the lowest MASE count as tied; the simplest wins
SELECTION_RULE = (
    "1. Eligible: pooled coverage of the 80% interval over all origins and horizons between "
    "0.70 and 0.90. 2. Among eligible models, the lowest mean MASE over all origins and horizons "
    "1-36 months. 3. A model within 5% of that MASE that is simpler (order: seasonal mean, ETS, "
    "damped trend, SARIMA, deweathered (ML)) is preferred. 4. If no model is eligible, rule 2 "
    "and 3 apply to all models and the coverage problem is reported.")


def month_index(start, periods):
    return pd.period_range(start, periods=periods, freq="M")


def seasonal_naive_scale(train, season=SEASON):
    """MAE of the seasonal naive forecast (same month last year) on the training months."""
    values = np.asarray(train, dtype=float)
    return float(np.nanmean(np.abs(values[season:] - values[:-season])))


def mase(actual, forecast, scale):
    return np.abs(np.asarray(actual, dtype=float) - np.asarray(forecast, dtype=float)) / scale


def _seasonal_mean(train_log, h, n, rng, years=3):
    recent = train_log.iloc[-SEASON * years:]
    means = recent.groupby(recent.index.month).mean()
    residuals = (recent - means.reindex(recent.index.month).to_numpy()).to_numpy()
    future = month_index(train_log.index[-1] + 1, h)
    centre = means.reindex(future.month).to_numpy()
    return centre + rng.choice(residuals, size=(n, h), replace=True)


def _ets(train_log, h, n, seed, damped):
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    model = ETSModel(train_log.to_timestamp(), error="add", trend="add" if damped else None,
                     damped_trend=damped, seasonal="add", seasonal_periods=SEASON)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = model.fit(disp=False)
        paths = fit.simulate(h, repetitions=n, anchor="end", rng=np.random.default_rng(seed))
    return np.asarray(paths).T


def _sarima(train_log, h, n, seed):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    best = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for order, seasonal in SARIMA_ORDERS:
            fit = SARIMAX(train_log.to_timestamp(), order=order, seasonal_order=seasonal, trend="c").fit(disp=False)
            if best is None or fit.aic < best.aic:
                best = fit
        paths = best.simulate(h, repetitions=n, anchor="end", rng=np.random.default_rng(seed))
    return np.asarray(paths).reshape(h, n).T


def year_anomalies(anomaly):
    """Monthly weather anomalies of each complete training year: {year: array of 12}."""
    frame = pd.DataFrame({"value": anomaly.to_numpy(), "year": anomaly.index.year, "month": anomaly.index.month})
    out = {}
    for year, part in frame.groupby("year"):
        if part["value"].notna().sum() == SEASON:
            out[year] = part.sort_values("month")["value"].to_numpy()
    return out


def _deweathered(train_log, normalised_log, h, n, seed, rng):
    level = _ets(normalised_log, h, n, seed, damped=True)
    years = year_anomalies(train_log - normalised_log)
    keys = list(years)
    future = month_index(train_log.index[-1] + 1, h)
    picked = rng.choice(len(keys), size=n)
    weather = np.stack([years[keys[k]][future.month.to_numpy() - 1] for k in picked])
    return level + weather


def simulate(model, train_log, h=HORIZON, n=1000, seed=0, normalised_log=None):
    """n simulated paths (n x h) of log monthly PM2.5 after the last training month."""
    rng = np.random.default_rng(seed)
    if model == "seasonal mean":
        return _seasonal_mean(train_log, h, n, rng)
    if model == "ETS":
        return _ets(train_log, h, n, seed, damped=False)
    if model == "damped trend":
        return _ets(train_log, h, n, seed, damped=True)
    if model == "SARIMA":
        return _sarima(train_log, h, n, seed)
    if model == "deweathered (ML)":
        if normalised_log is None:
            raise ValueError("the deweathered model needs the weather-normalised series")
        return _deweathered(train_log, normalised_log, h, n, seed, rng)
    raise ValueError(model)


def summarise_paths(paths, index):
    """Median and 80% / 95% intervals of paths given in log units, back in ug/m3."""
    values = np.exp(paths)
    q = np.percentile(values, [2.5, 10, 50, 90, 97.5], axis=0)
    return pd.DataFrame({"low_95": q[0], "low_80": q[1], "median": q[2], "high_80": q[3], "high_95": q[4]}, index=index)


def choose(summary):
    """Apply SELECTION_RULE to a table with columns model, mase, coverage_80."""
    table = summary.set_index("model")
    eligible = table[table["coverage_80"].between(*COVERAGE_RANGE)]
    pool = eligible if len(eligible) else table
    best = pool["mase"].min()
    tied = pool[pool["mase"] <= best * (1 + TIE_MARGIN)]
    chosen = min(tied.index, key=MODELS.index)
    return chosen, bool(len(eligible))


def daily_profiles(daily):
    """Daily values divided by their monthly mean, for each calendar month: {month: [arrays]}."""
    daily = daily.dropna()
    months = daily.index.to_period("M")
    out = {m: [] for m in range(1, 13)}
    for period, values in daily.groupby(months):
        if len(values) >= 20:
            out[period.month].append((values / values.mean()).to_numpy())
    return out


def bad_days(monthly_values, months, profiles, rng):
    """Bad-or-worse days of simulated months: each month takes the daily shape of a random
    historical month of the same calendar month, scaled to the simulated mean.

    monthly_values: n x h array in ug/m3; months: calendar month of each column.
    """
    n, h = monthly_values.shape
    out = np.zeros((n, h))
    for j, month in enumerate(months):
        shapes = profiles[month]
        picked = rng.integers(0, len(shapes), n)
        for i in range(n):
            out[i, j] = np.sum(np.round(monthly_values[i, j] * shapes[picked[i]]) > 35)
    return out


def annual_from_monthly(monthly_values, index):
    """Day-weighted annual means and the years with all 12 months, from n x h monthly values."""
    days = index.days_in_month.to_numpy()
    years = index.year.to_numpy()
    out = {}
    for year in np.unique(years):
        cols = years == year
        if cols.sum() == SEASON:
            out[int(year)] = (monthly_values[:, cols] * days[cols]).sum(axis=1) / days[cols].sum()
    return out


def meets_standard(annual_values, standard=15):
    """Share of simulated annual means at or below the standard after rounding to an integer."""
    return float(np.mean(np.round(annual_values) <= standard))


def scenario_paths(normalised_log, anomaly, slopes_per_year, h=HORIZON, n=1000, seed=0):
    """Paths of a what-if scenario on the weather-normalised series (log units).

    The level of each calendar month is its value over the last 12 months; it then changes
    by a slope per year drawn from `slopes_per_year` (all zeros for a stalled decline), and
    the weather of a whole training year drawn at random is added back. A scenario states
    an assumption about the trend; it is not a forecast of which trend will happen.
    """
    rng = np.random.default_rng(seed)
    last = normalised_log.iloc[-SEASON:]
    base = pd.Series(last.to_numpy(), index=last.index.month)
    future = month_index(normalised_log.index[-1] + 1, h)
    years_ahead = (np.arange(h) + 1) / SEASON
    slopes = rng.choice(np.asarray(slopes_per_year, dtype=float), size=n)
    level = base.reindex(future.month).to_numpy()[None, :] + slopes[:, None] * years_ahead[None, :]
    years = year_anomalies(anomaly)
    keys = list(years)
    picked = rng.choice(len(keys), size=n)
    weather = np.stack([years[keys[k]][future.month.to_numpy() - 1] for k in picked])
    return level + weather
