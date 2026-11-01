"""Load and clean the raw air quality files.

Every cleaning step must report how many rows it drops (see CLAUDE.md, rule 3).
"""
import pandas as pd

from seoul_air.config import DATA_RAW


def load_raw(filename):
    """Read a raw CSV from data/raw without changing it."""
    return pd.read_csv(DATA_RAW / filename)


def drop_with_report(df, mask, reason):
    """Drop the rows where mask is True and print how many were removed."""
    n_drop = int(mask.sum())
    print(f"{reason}: dropped {n_drop:,} rows, {len(df) - n_drop:,} left")
    return df.loc[~mask].copy()
