"""Download, load and clean the raw air quality files.

Every cleaning step must report how many rows it drops (see CLAUDE.md, rule 3).
"""
import io
import zipfile

import pandas as pd

from seoul_air.config import (
    DATA_RAW,
    ITEM_CODES,
    KAGGLE_URL,
    MIN_HOURS_PER_DAY,
    RAW_FILES,
    STATION_HISTORY,
    STATUS_NORMAL,
)


def download_raw(force=False):
    """Download the Kaggle zip and extract its CSV files into data/raw.

    Files that already exist are kept unless force is True.
    """
    import requests

    targets = [DATA_RAW / name for name in RAW_FILES.values()]
    if not force and all(p.exists() for p in targets):
        print("Raw files already present, download skipped")
        return targets
    response = requests.get(KAGGLE_URL, timeout=300)
    response.raise_for_status()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        for member in zf.namelist():
            name = member.rsplit("/", 1)[-1]
            if name in RAW_FILES.values():
                (DATA_RAW / name).write_bytes(zf.read(member))
    return targets


def load_raw(filename, **read_csv_options):
    """Read a raw CSV from data/raw without changing it."""
    return pd.read_csv(DATA_RAW / filename, **read_csv_options)


def load_stations():
    """Station code, district name and coordinates."""
    stations = load_raw(RAW_FILES["stations"])
    return stations.rename(columns={
        "Station code": "station_code",
        "Station name(district)": "district",
        "Address": "address",
        "Latitude": "latitude",
        "Longitude": "longitude",
    })


def load_station_history():
    """Official year of the latest equipment replacement and relocation of each station."""
    return pd.read_csv(STATION_HISTORY, dtype={"last_relocation": "Int64"})


def load_measurements():
    """Hourly readings in long format: one row per station, hour and pollutant."""
    # Compact types: this table has almost 4 million rows
    out = load_raw(
        RAW_FILES["measurements"],
        dtype={"Station code": "int16", "Item code": "int8", "Instrument status": "int8"},
        parse_dates=["Measurement date"],
        date_format="%Y-%m-%d %H:%M",
    ).rename(columns={
        "Measurement date": "datetime",
        "Station code": "station_code",
        "Item code": "item_code",
        "Average value": "value",
        "Instrument status": "status",
    })
    out["pollutant"] = out["item_code"].map(ITEM_CODES).astype("category")
    return out


def drop_with_report(df, mask, reason):
    """Drop the rows where mask is True and print how many were removed."""
    n_drop = int(mask.sum())
    print(f"{reason}: dropped {n_drop:,} rows, {len(df) - n_drop:,} left")
    return df.loc[~mask].copy()


def keep_valid_readings(long_df):
    """Drop readings flagged by the instrument and negative values."""
    out = drop_with_report(long_df, long_df["status"] != STATUS_NORMAL,
                           "Instrument status not normal")
    return drop_with_report(out, out["value"] < 0, "Negative value")


def to_wide(long_df):
    """One row per station and hour, one column per pollutant (NaN when missing)."""
    keys = ["datetime", "station_code"]
    # One outer merge per pollutant: a pivot needs far more memory on this table
    wide = None
    for pollutant in sorted(long_df["pollutant"].unique()):
        column = (long_df.loc[long_df["pollutant"] == pollutant, [*keys, "value"]]
                         .drop_duplicates(keys)
                         .rename(columns={"value": pollutant}))
        wide = column if wide is None else wide.merge(column, on=keys, how="outer")
    return wide.sort_values(keys).reset_index(drop=True)


def complete_hourly_grid(wide, start, end, stations):
    """Add a NaN row for every station and hour that has no reading."""
    hours = pd.date_range(start, end, freq="h")
    grid = pd.MultiIndex.from_product([hours, stations], names=["datetime", "station_code"])
    return (wide.set_index(["datetime", "station_code"])
                .reindex(grid)
                .reset_index())


def daily_means(hourly, pollutants, min_hours=MIN_HOURS_PER_DAY):
    """Daily mean per station; a day is NaN when it has fewer than min_hours readings."""
    grouped = hourly.assign(date=hourly["datetime"].dt.normalize()).groupby(["station_code", "date"])
    means = grouped[pollutants].mean()
    counts = grouped[pollutants].count()
    return means.where(counts >= min_hours).reset_index()


def network_gap_days(daily, hourly, pollutant="pm25"):
    """Days with no valid daily mean at any station, and the hours they still have."""
    stations = daily.groupby("date")[pollutant].count()
    gaps = stations.index[stations == 0]
    date = hourly["datetime"].dt.normalize()
    on_gap = hourly.assign(date=date).loc[date.isin(gaps)].dropna(subset=[pollutant])
    by_hour = on_gap.groupby(["date", "datetime"])[pollutant].mean()
    out = pd.DataFrame({
        "hours_with_data": by_hour.groupby("date").size(),
        "partial_city_mean": by_hour.groupby("date").mean(),
    }).reindex(gaps)
    out["hours_with_data"] = out["hours_with_data"].fillna(0).astype(int)
    return out.rename_axis("date").reset_index()


def network_level(long_df):
    """Median of the normal readings of the same hour, for one pollutant."""
    normal = long_df[long_df["status"] == STATUS_NORMAL]
    return long_df["datetime"].map(normal.groupby("datetime")["value"].median())


def plausible_flagged(long_df):
    """Flagged readings within a factor of 2 of the network level, for one pollutant.

    A heuristic: these look like real air, unlike sensor faults far from the network.
    """
    level = network_level(long_df)
    flagged = long_df["status"] != STATUS_NORMAL
    return flagged & long_df["value"].between(level / 2, level * 2)


def flag_rate_by_network_level(long_df, bins, labels):
    """Share of flagged readings by how polluted the network was, for one pollutant.

    If the status filter removed real peaks, the share would rise with the level.
    Hours without any normal reading have no level and go to "No reference".
    """
    level = pd.cut(network_level(long_df), bins=bins, labels=labels)
    level = pd.Categorical(level.astype(object).fillna("No reference"),
                           categories=[*labels, "No reference"])
    table = (long_df.assign(
                 level=level,
                 flagged=long_df["status"] != STATUS_NORMAL,
                 plausible=plausible_flagged(long_df))
             .groupby("level", observed=False)
             .agg(readings=("flagged", "size"), flagged=("flagged", "sum"),
                  plausible_flagged=("plausible", "sum")))
    table["flagged_%"] = (100 * table["flagged"] / table["readings"]).round(2)
    return table.rename_axis("network_level").reset_index()
