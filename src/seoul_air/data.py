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


def load_raw(filename):
    """Read a raw CSV from data/raw without changing it."""
    return pd.read_csv(DATA_RAW / filename)


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


def load_measurements():
    """Hourly readings in long format: one row per station, hour and pollutant."""
    raw = load_raw(RAW_FILES["measurements"])
    out = raw.rename(columns={
        "Measurement date": "datetime",
        "Station code": "station_code",
        "Item code": "item_code",
        "Average value": "value",
        "Instrument status": "status",
    })
    out["datetime"] = pd.to_datetime(out["datetime"], format="%Y-%m-%d %H:%M")
    out["pollutant"] = out["item_code"].map(ITEM_CODES)
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
    wide = long_df.pivot_table(index=["datetime", "station_code"],
                               columns="pollutant", values="value", aggfunc="first")
    wide.columns.name = None
    return wide.reset_index()


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
