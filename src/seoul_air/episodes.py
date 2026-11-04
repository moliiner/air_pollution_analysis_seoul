"""Runs of consecutive days: network gaps and multi-day pollution episodes."""
import pandas as pd

from seoul_air.metrics import BAD_THRESHOLD_PM25


def find_runs(flags):
    """Runs of consecutive True values in a boolean Series with a daily index."""
    flags = flags.astype(bool)
    run_id = (flags != flags.shift()).cumsum()
    days = flags.index.to_series()[flags.to_numpy()]
    runs = days.groupby(run_id[flags]).agg(start="min", end="max", days="size")
    return runs.reset_index(drop=True)


def find_episodes(city_pm25):
    """Runs of days with a Bad-or-worse city PM2.5 mean (rounded, as the grades are).

    Missing days never count as Bad, so a gap ends a run. gap_before and gap_after
    mark the runs next to a missing day, whose true length is unknown.
    """
    is_bad = city_pm25.round() > BAD_THRESHOLD_PM25
    runs = find_runs(is_bad)
    one_day = pd.Timedelta(days=1)
    gaps = city_pm25.index[city_pm25.isna()]
    values = [city_pm25.loc[r.start:r.end] for r in runs.itertuples()]
    runs["peak_pm25"] = [v.max() for v in values]
    runs["mean_pm25"] = [v.mean() for v in values]
    runs["gap_before"] = (runs["start"] - one_day).isin(gaps)
    runs["gap_after"] = (runs["end"] + one_day).isin(gaps)
    return runs
