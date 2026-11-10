"""Archived numerical weather forecasts (JMA GSM through the Open-Meteo Previous Runs API).

The Previous Runs API keeps, for each hour, the value that a model predicted a fixed
time before it: `<variable>_previous_dayN` was predicted N x 24 hours before the valid
hour. Its archive reaches back before 2024 only for JMA GSM/MSM (from 2018) and for the
GFS 2 m temperature (from 2021), so JMA is the only source of real historical forecasts
of all variables for most of 2015-2025. No archived forecast has the boundary layer
height. KMA models are not archived.

Which forecast was known at the 17:00 KST issue time
    For a target day D+k (k = 1, 2, 3 days after the issue day D) the latest hour is
    23:00 KST of D+k. `previous_day(k+1)` for that hour was predicted at the latest 24 x
    (k+1) hours earlier, 23:00 KST of D-1 (14 UTC), so it comes from the 12 UTC run of D-1
    or an earlier one, published hours before 17:00 KST of D. `previous_dayk` would come
    from runs as late as 23:00 KST of D, after the issue time, and is not used. The
    forecasts used are therefore up to a day older than an operational forecaster's.
"""
import numpy as np
import pandas as pd

from seoul_air import config

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODEL = "jma_seamless"
POINT = (37.57, 126.98)  # Seoul, the point of the ERA5 series
FIRST_DAY = "2018-01-01"
VARIABLES = ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m",
             "wind_direction_10m", "pressure_msl", "cloud_cover"]
HORIZONS = (1, 2, 3)
RAW_DIR = config.DATA_RAW / "weather"


def offset_for(horizon):
    """previous_dayN used for a target day `horizon` days after the issue day."""
    return horizon + 1


def download(first_day=FIRST_DAY, last_day="2025-12-31", force=False):
    """Hourly JMA forecasts for the offsets of HORIZONS, one request per year, times in KST."""
    import requests

    path = RAW_DIR / f"jma_previous_runs_{first_day}_{last_day}.csv"
    if path.exists() and not force:
        return path
    import time

    names = [f"{v}_previous_day{offset_for(h)}" for v in VARIABLES for h in HORIZONS]
    frames = []
    # Quarterly requests: long ones time out on the server
    for start in pd.date_range(first_day, last_day, freq="QS"):
        end = min(start + pd.offsets.QuarterEnd(0), pd.Timestamp(last_day))
        for attempt in range(5):
            response = requests.get(URL, timeout=600, params={
                "latitude": POINT[0], "longitude": POINT[1], "models": MODEL, "timezone": "Asia/Seoul",
                "hourly": ",".join(names), "start_date": str(start.date()), "end_date": str(end.date()),
                "wind_speed_unit": "ms"})
            if response.ok and response.text.startswith("{"):
                break
            time.sleep(30 * (attempt + 1))  # rate limit of the free API
        response.raise_for_status()
        frames.append(pd.DataFrame(response.json()["hourly"]).rename(columns={"time": "datetime"}))
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_csv(path, index=False)
    return path


def daily_forecasts(path, min_hours=24):
    """Daily forecast of each target date and horizon (one row per date, columns per horizon).

    Hourly values are labelled by their instant in KST; precipitation is the sum of the
    hour that ends at the label, so it is moved back one hour to the start-of-hour
    convention of the project before the daily sum. Wind is averaged as u and v components.
    A day needs all 24 hours of a variable.
    """
    hourly = pd.read_csv(path, parse_dates=["datetime"]).set_index("datetime")
    out = {}
    for horizon in HORIZONS:
        n = offset_for(horizon)
        col = {v: f"{v}_previous_day{n}" for v in VARIABLES}
        frame = pd.DataFrame(index=hourly.index)
        frame["temperature"] = hourly[col["temperature_2m"]]
        frame["humidity"] = hourly[col["relative_humidity_2m"]]
        frame["precipitation"] = hourly[col["precipitation"]].shift(-1)
        speed, direction = hourly[col["wind_speed_10m"]], np.deg2rad(hourly[col["wind_direction_10m"]])
        frame["wind_speed"] = speed
        frame["wind_u"] = -speed * np.sin(direction)
        frame["wind_v"] = -speed * np.cos(direction)
        frame["pressure"] = hourly[col["pressure_msl"]]
        frame["cloud_cover"] = hourly[col["cloud_cover"]]
        grouped = frame.groupby(frame.index.normalize())
        daily = grouped.agg({"temperature": ["mean", "min", "max"], "humidity": "mean", "precipitation": "sum",
                             "wind_speed": "mean", "wind_u": "mean", "wind_v": "mean", "pressure": "mean",
                             "cloud_cover": "mean"})
        daily.columns = [f"{a}_{b}" for a, b in daily.columns]
        complete = grouped.count().min(axis=1) >= min_hours
        daily = daily.where(complete)
        out[horizon] = daily.add_prefix("nwp_")
    return pd.concat(out, axis=1, names=["horizon", "variable"])
