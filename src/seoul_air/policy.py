"""Comparisons of the PM seasonal management system (미세먼지 계절관리제) seasons.

The system runs every year from December to March; the first season was December 2019 to
March 2020. A season is labelled by the year of its December (2019 = 2019-12 to 2020-03).

These are observational comparisons. The system started in every region of Korea at the
same time as other changes (COVID-19, regional and Chinese emission controls, the
long-term decline), so the estimates describe associations unless a design removes those
changes, and each design below removes only some of them.
"""
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

from .trend import block_bootstrap_slopes

FIRST_SEASON = 2019
SEASON_MONTHS = (12, 1, 2, 3)
OTHER_MONTHS = tuple(range(4, 12))


def season_of(dates):
    """Season label (year of its December) of each date, NaN outside December-March."""
    dates = pd.DatetimeIndex(dates)
    label = np.where(dates.month == 12, dates.year, dates.year - 1).astype(float)
    return pd.Series(np.where(dates.month.isin(SEASON_MONTHS), label, np.nan), index=dates)


def season_means(monthly):
    """Mean of each complete December-March season of a monthly Series (PeriodIndex or dates)."""
    index = monthly.index.to_timestamp() if isinstance(monthly.index, pd.PeriodIndex) else monthly.index
    series = pd.Series(monthly.to_numpy(), index=index).dropna()
    seasons = season_of(series.index)
    in_season = seasons.notna().to_numpy()
    grouped = series[in_season].groupby(seasons[in_season].astype(int).to_numpy())
    complete = grouped.count() == len(SEASON_MONTHS)
    return grouped.mean()[complete]


def other_months_means(monthly, min_months=6):
    """Mean of April-November of each year (the months outside the seasons)."""
    index = monthly.index.to_timestamp() if isinstance(monthly.index, pd.PeriodIndex) else monthly.index
    series = pd.Series(monthly.to_numpy(), index=index).dropna()
    series = series[series.index.month.isin(OTHER_MONTHS)]
    grouped = series.groupby(series.index.year)
    return grouped.mean()[grouped.count() >= min_months]


def before_after(values, first_post=FIRST_SEASON, exclude=()):
    """Mean of the post seasons minus mean of the pre seasons, and an exact permutation p-value.

    The p-value is the share of all ways of splitting the seasons into groups of the same
    sizes that give a difference at least as large in absolute value.
    """
    values = values.drop([e for e in exclude if e in values.index])
    post = values.index >= first_post
    difference = values[post].mean() - values[~post].mean()
    arr = values.to_numpy()
    n_post = int(post.sum())
    diffs = []
    for chosen in combinations(range(len(arr)), n_post):
        mask = np.zeros(len(arr), dtype=bool)
        mask[list(chosen)] = True
        diffs.append(arr[mask].mean() - arr[~mask].mean())
    p_value = float(np.mean(np.abs(diffs) >= abs(difference) - 1e-12))
    return {"pre_seasons": int((~post).sum()), "post_seasons": n_post, "difference": float(difference),
            "p_value": p_value}


def season_minus_other(season, other, log=False):
    """Each season minus the April-November that follows it (season 2019 - Apr-Nov 2020).

    The months outside the seasons share the long-term decline, COVID-19 and year-round
    regional changes; they do not share changes specific to winter and early spring. The
    before-after difference of this series is a difference in differences. With log=True
    it compares relative changes, which matters because winter levels are higher, so the
    same relative decline is a larger absolute one.
    """
    following = other.rename(lambda year: year - 1)
    both = pd.concat([season, following], axis=1, keys=["season", "other"]).dropna()
    if log:
        both = np.log(both)
    return (both["season"] - both["other"]).rename("season_minus_other")


def trend_gap(monthly_anomaly, season, first_post=FIRST_SEASON, n_boot=2000, seed=0):
    """Post seasons minus the level expected if the trend before the system had continued.

    A Theil-Sen line is fit to the deseasonalised monthly anomalies before December of
    first_post. The expected post level is the pre-season mean moved along that line from
    the middle of the pre seasons to the middle of the post seasons (the end of January of
    each season). The 95% interval comes from a 12-month block bootstrap of the pre-period
    slope (trend.block_bootstrap_slopes), the largest source of uncertainty here.
    """
    index = monthly_anomaly.index.to_timestamp() if isinstance(monthly_anomaly.index, pd.PeriodIndex)         else monthly_anomaly.index
    anomaly = pd.Series(monthly_anomaly.to_numpy(), index=index).dropna()
    pre = anomaly[anomaly.index < pd.Timestamp(f"{first_post}-12-01")]
    t0 = pre.index[0]

    def years(dates):
        return np.asarray((pd.DatetimeIndex(dates) - t0).days, dtype=float) / 365.25

    t = years(pre.index)
    slope = theilslopes(pre.to_numpy(), t)[0]
    slopes = block_bootstrap_slopes(t, pre.to_numpy(), n_boot=n_boot, seed=seed)
    middle = lambda labels: [f"{y + 1}-01-31" for y in labels]  # noqa: E731
    pre_seasons, post_seasons = season[season.index < first_post], season[season.index >= first_post]
    elapsed = years(middle(post_seasons.index)).mean() - years(middle(pre_seasons.index)).mean()
    raw_change = post_seasons.mean() - pre_seasons.mean()
    gaps = raw_change - slopes * elapsed
    low, high = np.percentile(gaps, [2.5, 97.5])
    return {"pre_months": len(pre), "pre_slope_per_year": float(slope), "years_between": float(elapsed),
            "before_after": float(raw_change), "expected_change": float(slope * elapsed),
            "gap": float(raw_change - slope * elapsed), "gap_low_95": float(low), "gap_high_95": float(high)}
