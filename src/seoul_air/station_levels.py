"""Compare each station with the rest of the network and find level shifts.

All stations share the same weather and the same regional pollution, so a lasting
change in the gap between one station and the others points to something local:
a relocation, an instrument change or a new nearby source. The data alone cannot
tell these apart.
"""
import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371


def to_station_table(daily, pollutant):
    """One row per day, one column per district."""
    return daily.pivot(index="date", columns="district", values=pollutant)


def rest_of_city_mean(table):
    """Mean of the other stations of the same day, for each station."""
    total = table.sum(axis=1)
    count = table.notna().sum(axis=1)
    rest = {
        district: (total - table[district].fillna(0)) / (count - table[district].notna())
        for district in table.columns
    }
    return pd.DataFrame(rest)[table.columns].replace([np.inf, -np.inf], np.nan)


def offset_from_city(table):
    """Station minus the mean of the other stations, in the units of the pollutant."""
    return table - rest_of_city_mean(table)


def log_ratio(table, reference):
    """log(station / reference), so that a shift is comparable across seasons."""
    return np.log(table.where(table > 0)) - np.log(reference.where(reference > 0))


def nearest_stations(stations, k=5):
    """The k closest stations to each district, by great-circle distance."""
    lat = np.radians(stations["latitude"].to_numpy())
    lon = np.radians(stations["longitude"].to_numpy())
    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat)[:, None] * np.cos(lat)[None, :] * np.sin(dlon / 2) ** 2
    distance = 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))
    names = stations["district"].to_numpy()
    order = np.argsort(distance, axis=1)[:, 1:k + 1]
    return {name: names[row].tolist() for name, row in zip(names, order)}


def neighbour_median(table, neighbours):
    """Median of the nearest stations of the same day, for each station."""
    return pd.DataFrame({d: table[neighbours[d]].median(axis=1) for d in table.columns})


def best_arc(values, min_size):
    """Stretch of the series that differs most from the rest (circular binary segmentation).

    A stretch that reaches either end of the series is a single change of level;
    one in the middle is a change that later reverses, which a single split misses.
    Returns (start, end, jump inside minus outside, statistic), or None when the
    series is too short. The stretch is values[start:end].
    """
    n = len(values)
    if n < 2 * min_size:
        return None
    cumulative = np.r_[0.0, np.cumsum(values)]
    sums = cumulative[:, None] - cumulative[None, :]  # sums[j, i] = sum of values[i:j]
    sizes = np.arange(n + 1)[:, None] - np.arange(n + 1)[None, :]
    valid = (sizes >= min_size) & (n - sizes >= min_size)
    inside = np.divide(sums, sizes, out=np.zeros_like(sums), where=valid)
    outside = np.divide(cumulative[-1] - sums, n - sizes, out=np.zeros_like(sums), where=valid)
    jump = inside - outside
    statistic = np.zeros_like(sums)
    statistic[valid] = np.abs(jump[valid]) * np.sqrt(sizes[valid] * (n - sizes[valid]) / n)
    end, start = np.unravel_index(np.argmax(statistic), statistic.shape)
    return int(start), int(end), float(jump[end, start]), float(statistic[end, start])


def shuffle_blocks(n, block, rng):
    """Positions 0..n-1 with consecutive blocks in a random order."""
    blocks = [np.arange(start, min(start + block, n)) for start in range(0, n, block)]
    return np.concatenate([blocks[i] for i in rng.permutation(len(blocks))])


def shift_pvalue(values, statistic, min_size, block, n_perm, rng):
    """Share of block-shuffled series with a stretch at least as strong.

    Shuffling blocks keeps the short-term persistence of the series, which an
    ordinary test ignores, and destroys any lasting change of level.
    """
    exceed = 0
    for _ in range(n_perm):
        shuffled = values[shuffle_blocks(len(values), block, rng)]
        if best_arc(shuffled, min_size)[3] >= statistic:
            exceed += 1
    return (exceed + 1) / (n_perm + 1)


def detect_level_shifts(weekly, min_size=20, block=8, n_perm=499, alpha=0.01, min_jump=0.10,
                        seed=0):
    """Lasting level shifts of a weekly series, by circular binary segmentation.

    A stretch must pass the block-shuffled test (alpha) and differ from the rest by
    at least min_jump (0.10 is about 10% on a log ratio). Each of its boundaries is
    reported as a shift, and the pieces are then searched again.
    """
    series = weekly.dropna()
    rng = np.random.default_rng(seed)
    found = []
    pending = [series]
    while pending:
        segment = pending.pop()
        values = segment.to_numpy()
        arc = best_arc(values, min_size)
        if arc is None:
            continue
        start, end, jump, statistic = arc
        if abs(jump) < min_jump:
            continue
        p_value = shift_pvalue(values - values.mean(), statistic, min_size, block, n_perm, rng)
        if p_value > alpha:
            continue
        if start > 0:
            found.append({"date": segment.index[start], "jump": jump, "p_value": p_value})
        if end < len(segment):
            found.append({"date": segment.index[end], "jump": -jump, "p_value": p_value})
        pending += [segment.iloc[:start], segment.iloc[start:end], segment.iloc[end:]]
    columns = ["date", "jump", "p_value"]
    return pd.DataFrame(found, columns=columns).sort_values("date").reset_index(drop=True)


def agreed_shifts(by_city, by_neighbours, tolerance_weeks=8):
    """Shifts found against both references, with the same sign and close in time."""
    rows = []
    # An empty result of detect_level_shifts has no datetime type to compare with
    dates = pd.to_datetime(by_neighbours["date"])
    for shift in by_city.itertuples():
        close = by_neighbours[(dates - shift.date).abs() <= pd.Timedelta(weeks=tolerance_weeks)]
        close = close[np.sign(close["jump"]) == np.sign(shift.jump)]
        if not close.empty:
            rows.append({"date": shift.date, "date_near": close["date"].iloc[0],
                         "jump": shift.jump, "p_value": shift.p_value})
    agreed = pd.DataFrame(rows, columns=["date", "date_near", "jump", "p_value"])
    # Two nearby detections of the same shift match one neighbour shift: keep the larger
    largest = agreed["jump"].abs().groupby(agreed["date_near"]).idxmax() if len(agreed) else []
    return agreed.loc[sorted(largest)].reset_index(drop=True)


def station_outages(hourly, pollutant, min_hours=72, network_share=0.9):
    """Runs of at least min_hours without a reading at one station.

    Hours when most of the network is missing are left out: those are network gaps,
    not events of one station.
    """
    missing = hourly.pivot(index="datetime", columns="district", values=pollutant).isna()
    network_gap = missing.mean(axis=1) >= network_share
    rows = []
    for district in missing.columns:
        flags = missing[district] & ~network_gap
        run_id = (flags != flags.shift()).cumsum()[flags]
        for _, hours in flags[flags].index.to_series().groupby(run_id):
            if len(hours) >= min_hours:
                rows.append({"district": district, "start": hours.iloc[0], "end": hours.iloc[-1],
                             "days": round(len(hours) / 24, 1)})
    return (pd.DataFrame(rows, columns=["district", "start", "end", "days"])
            .sort_values(["district", "start"]).reset_index(drop=True))


def change_around(weekly, date, weeks=13):
    """Mean level of the weeks after a date minus that of the weeks before it."""
    date = pd.Timestamp(date)
    window = pd.Timedelta(weeks=weeks)
    before = weekly[(weekly.index >= date - window) & (weekly.index < date)]
    after = weekly[(weekly.index >= date) & (weekly.index < date + window)]
    return after.mean() - before.mean()


def offset_intervals(weekly, n_boot=2000, block=4, seed=0):
    """Mean offset and rank of each station, with 95% intervals.

    Resamples whole blocks of weeks and keeps every station of a week together,
    because the stations of the same week are not independent.
    """
    complete = weekly.dropna(how="all")
    n = len(complete)
    n_blocks = int(np.ceil(n / block))
    rng = np.random.default_rng(seed)
    values = complete.to_numpy()
    draws = np.empty((n_boot, values.shape[1]))
    for b in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        rows = (starts[:, None] + np.arange(block)).ravel()[:n]
        draws[b] = np.nanmean(values[rows], axis=0)
    ranks = pd.DataFrame(-draws).rank(axis=1).to_numpy()
    return pd.DataFrame({
        "offset": np.nanmean(values, axis=0),
        "offset_low": np.percentile(draws, 2.5, axis=0),
        "offset_high": np.percentile(draws, 97.5, axis=0),
        "rank_low": np.percentile(ranks, 2.5, axis=0),
        "rank_high": np.percentile(ranks, 97.5, axis=0),
    }, index=complete.columns).rename_axis("district")
