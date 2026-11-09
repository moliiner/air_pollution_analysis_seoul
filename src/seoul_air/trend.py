"""Long-term trend of a monthly series, with an uncertainty that respects autocorrelation.

Monthly means are deseasonalised by subtracting the mean of each calendar month. The
slope is the Theil-Sen estimate (the median of all pairwise slopes, robust to outlying
months). Its 95% interval comes from a moving-block bootstrap of the residuals: blocks
of 12 consecutive months keep the dependence between nearby months, which an ordinary
interval would ignore and so make too narrow.
"""
import numpy as np
import pandas as pd
from scipy.stats import theilslopes


def monthly_means(daily, min_days=20):
    """Monthly mean of a daily series; months with fewer than min_days values are NaN."""
    daily = pd.Series(daily).astype(float)
    grouped = daily.groupby(daily.index.to_period("M"))
    return grouped.mean().where(grouped.count() >= min_days)


def deseasonalise(monthly):
    """Anomaly of each month from the mean of its calendar month."""
    climatology = monthly.groupby(monthly.index.month).transform("mean")
    return monthly - climatology


def years_since_start(index):
    """Time of each month in years since the first month (period index)."""
    first = index[0]
    return np.array([(p - first).n for p in index], dtype=float) / 12


def theil_sen(t, y):
    slope, intercept, _, _ = theilslopes(y, t)
    return slope, intercept


def block_bootstrap_slopes(t, y, block=12, n_boot=2000, seed=0):
    """Theil-Sen slopes of series rebuilt from the fitted line plus resampled residual blocks."""
    slope, intercept = theil_sen(t, y)
    fitted = intercept + slope * t
    residuals = y - fitted
    n = len(y)
    rng = np.random.default_rng(seed)
    starts_available = n - block + 1
    n_blocks = int(np.ceil(n / block))
    slopes = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, starts_available, n_blocks)
        rows = (starts[:, None] + np.arange(block)).ravel()[:n]
        slopes[b] = theil_sen(t, fitted + residuals[rows])[0]
    return slopes


def trend(monthly, n_boot=2000, seed=0):
    """Slope per year of a monthly series, its 95% interval and the slope relative to the mean."""
    anomalies = deseasonalise(monthly).dropna()
    t = years_since_start(anomalies.index)
    y = anomalies.to_numpy()
    slope, _ = theil_sen(t, y)
    slopes = block_bootstrap_slopes(t, y, n_boot=n_boot, seed=seed)
    low, high = np.percentile(slopes, [2.5, 97.5])
    level = monthly.mean()
    return {
        "months": len(y),
        "slope_per_year": slope, "low_95": low, "high_95": high,
        "pct_per_year": 100 * slope / level, "pct_low_95": 100 * low / level, "pct_high_95": 100 * high / level,
        "excludes_zero": bool(low > 0 or high < 0),
    }
