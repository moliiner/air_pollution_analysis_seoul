"""Features for the next-day PM2.5 forecast.

The forecast is issued at the end of day d for day d+1. Every feature uses
only data up to and including day d (no leakage from the target day).
"""
import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 6]  # days before the issue day (lag 0 is the issue day itself)
FEATURE_COLUMNS = (
    ["pm25_d0", "pm10_d0", "no2_d0", "co_d0", "o3_d0", "so2_d0"]
    + [f"pm25_lag{k}" for k in LAGS]
    + ["pm25_roll7", "pm25_city_d0", "pm25_city_change",
       "doy_sin", "doy_cos", "target_weekday", "station_code"]
)


def make_forecast_table(daily, pollutants=("pm25", "pm10", "no2", "co", "o3", "so2")):
    """One row per station and issue day d, with target = PM2.5 mean of day d+1.

    `daily` must have one row per station and calendar day (a complete grid),
    so that shift(k) means exactly k days.
    """
    df = daily.sort_values(["station_code", "date"]).copy()
    g = df.groupby("station_code")

    out = df[["station_code", "date"]].copy()
    for p in pollutants:
        out[f"{p}_d0"] = df[p]
    for k in LAGS:
        out[f"pm25_lag{k}"] = g["pm25"].shift(k)
    out["pm25_roll7"] = g["pm25"].transform(lambda s: s.rolling(7, min_periods=5).mean())

    # City-wide mean of the issue day: all stations report before the forecast is issued
    city = df.groupby("date")["pm25"].mean()
    out["pm25_city_d0"] = out["date"].map(city)
    out["pm25_city_change"] = out["pm25_city_d0"] - out["date"].map(city.shift(1))

    target_date = out["date"] + pd.Timedelta(days=1)
    doy = target_date.dt.dayofyear
    out["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    out["target_weekday"] = target_date.dt.weekday
    out["target_date"] = target_date
    out["target"] = g["pm25"].shift(-1)
    return out
