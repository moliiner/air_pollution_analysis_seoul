"""Hourly weather for Seoul, 2015-2025, aligned with the pollution tables.

Source: the ERA5 reanalysis (ECMWF / Copernicus Climate Change Service), read through the
Open-Meteo historical weather API, which needs no key. ERA5 is a model reconstruction of
past weather on a 0.25-degree grid (about 25 km); one grid point covers central Seoul.
It includes the boundary layer height, the depth of the air layer in which pollution
mixes, which surface stations do not measure.

Observations of the KMA surface station of Seoul (ASOS 108, WMO 47108), read from the
Meteostat bulk files, are used only to check how close ERA5 is to measured weather.

Time: ERA5 values are instantaneous at each UTC hour, except precipitation, which is the
total of the hour before. The pollution tables label an hour by its start in KST
(UTC+9). Hour [h, h+1) KST therefore gets the mean of the instants h and h+1, and the
precipitation reported at h+1.

**Observed weather is for analysis only.** The weather of a day is not known when a
forecast for that day is issued; a forecast may use the weather of the issue day and
earlier (`weather_known_at_issue`) or a weather forecast, never the observed weather of
the target day.
"""
import json

import numpy as np
import pandas as pd

from seoul_air import config

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
METEOSTAT_URL = "https://bulk.meteostat.net/v2/hourly/47108.csv.gz"
RAW_DIR = config.DATA_RAW / "weather"
# Central Seoul (City Hall); Open-Meteo returns the nearest ERA5 grid point
LATITUDE, LONGITUDE = 37.5665, 126.9780
KST = pd.Timedelta(hours=9)

# Open-Meteo variable -> (column of this project, unit)
VARIABLES = {
    "temperature_2m": ("temperature_c", "degC"),
    "relative_humidity_2m": ("relative_humidity_pct", "%"),
    "precipitation": ("precipitation_mm", "mm per hour"),
    "wind_speed_10m": ("wind_speed_ms", "m/s"),
    "wind_direction_10m": ("wind_direction_deg", "degrees, direction the wind blows from"),
    "boundary_layer_height": ("boundary_layer_height_m", "m"),
    "surface_pressure": ("surface_pressure_hpa", "hPa"),
}
INSTANT_COLUMNS = ["temperature_c", "relative_humidity_pct", "boundary_layer_height_m", "surface_pressure_hpa"]
# Columns of the weather tables: observed weather, never a forecast input for its own hour or day
WEATHER_COLUMNS = ["temperature_c", "relative_humidity_pct", "precipitation_mm", "wind_speed_ms",
                   "wind_direction_deg", "wind_u_ms", "wind_v_ms", "boundary_layer_height_m",
                   "surface_pressure_hpa"]


# ------------------------------------------------------------------ download and read

def era5_path(start, end):
    return RAW_DIR / f"era5_{start}_{end}.json"


def era5_periods(first_year=2015, last_year=2025):
    """UTC date ranges to download; the day before the first year is needed for KST."""
    periods = [(f"{first_year - 1}-12-31", f"{first_year - 1}-12-31")]
    periods += [(f"{year}-01-01", f"{year}-12-31") for year in range(first_year, last_year + 1)]
    return periods


def download_era5(first_year=2015, last_year=2025, force=False):
    import requests

    paths = []
    for start, end in era5_periods(first_year, last_year):
        path = era5_path(start, end)
        if force or not path.exists():
            response = requests.get(OPEN_METEO_URL, timeout=300, params={
                "latitude": LATITUDE, "longitude": LONGITUDE, "start_date": start, "end_date": end,
                "hourly": ",".join(VARIABLES), "timezone": "GMT", "models": "era5", "wind_speed_unit": "ms",
            })
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(response.text, encoding="utf-8")
        paths.append(path)
    return paths


def read_era5(paths):
    """Instantaneous UTC values, one row per hour, with the units of the response."""
    frames, units, grid = [], None, None
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        frame = pd.DataFrame(data["hourly"])
        frames.append(frame)
        units = units or data["hourly_units"]
        grid = grid or (data["latitude"], data["longitude"])
    out = pd.concat(frames, ignore_index=True)
    out["time_utc"] = pd.to_datetime(out.pop("time"))
    out = out.drop_duplicates("time_utc").sort_values("time_utc").reset_index(drop=True)
    out = out.rename(columns={k: v[0] for k, v in VARIABLES.items()})
    out.attrs["units"] = units
    out.attrs["grid_point"] = grid
    return out


def download_station_observations(force=False):
    import requests

    path = RAW_DIR / "meteostat_47108.csv.gz"
    if force or not path.exists():
        response = requests.get(METEOSTAT_URL, timeout=300, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    return path


def read_station_observations(path, first_year=2015):
    """Seoul ASOS 108 observations as instants in UTC; wind converted from km/h to m/s."""
    columns = ["date", "hour", "temperature_c", "dew_point_c", "relative_humidity_pct", "precipitation_mm",
               "snow_mm", "wind_direction_deg", "wind_speed_kmh", "gust_kmh", "pressure_hpa", "sunshine_min",
               "condition"]
    out = pd.read_csv(path, header=None, names=columns)
    out = out[out["date"] >= f"{first_year}"]
    out["time_utc"] = pd.to_datetime(out["date"]) + pd.to_timedelta(out["hour"], unit="h")
    out["wind_speed_ms"] = out["wind_speed_kmh"] / 3.6
    return out[["time_utc", "temperature_c", "relative_humidity_pct", "precipitation_mm",
                "wind_speed_ms", "wind_direction_deg"]].reset_index(drop=True)


# ------------------------------------------------------------------ alignment

def wind_components(speed, direction):
    """Eastward (u) and northward (v) components of a wind blowing FROM direction."""
    radians = np.deg2rad(direction)
    return -speed * np.sin(radians), -speed * np.cos(radians)


def wind_direction(u, v):
    """Direction the wind blows from, in degrees, from its components."""
    return (np.rad2deg(np.arctan2(-u, -v)) + 360) % 360


def to_kst_hours(instants):
    """One row per KST hour [h, h+1), labelled by its start like the pollution tables.

    Instantaneous variables: mean of the instants at h and h+1. Wind direction: from the
    mean wind components. Precipitation: the total reported at h+1 (the hour before it).
    """
    frame = instants.copy()
    frame["kst"] = frame["time_utc"] + KST
    frame["wind_u_ms"], frame["wind_v_ms"] = wind_components(frame["wind_speed_ms"], frame["wind_direction_deg"])
    frame = frame.set_index("kst").asfreq("h")
    start, end = frame.iloc[:-1], frame.iloc[1:]
    hourly = pd.DataFrame(index=start.index)
    for column in INSTANT_COLUMNS + ["wind_speed_ms", "wind_u_ms", "wind_v_ms"]:
        hourly[column] = (start[column].to_numpy() + end[column].to_numpy()) / 2
    hourly["precipitation_mm"] = end["precipitation_mm"].to_numpy()
    hourly["wind_direction_deg"] = wind_direction(hourly["wind_u_ms"], hourly["wind_v_ms"])
    return hourly.rename_axis("datetime").reset_index()[["datetime", *WEATHER_COLUMNS]]


def daily_weather(hourly, min_hours=24):
    """Daily weather of KST days; each value needs min_hours valid hours of its variable."""
    frame = hourly.assign(date=hourly["datetime"].dt.normalize())
    grouped = frame.groupby("date")
    # Hourly variable behind each daily column, to check that its day is complete
    sources = {"temperature": "temperature_c", "relative_humidity": "relative_humidity_pct",
               "precipitation": "precipitation_mm", "wind": "wind_speed_ms",
               "boundary_layer": "boundary_layer_height_m", "surface_pressure": "surface_pressure_hpa"}
    out = pd.DataFrame({
        "temperature_mean_c": grouped["temperature_c"].mean(),
        "temperature_min_c": grouped["temperature_c"].min(),
        "temperature_max_c": grouped["temperature_c"].max(),
        "relative_humidity_mean_pct": grouped["relative_humidity_pct"].mean(),
        "precipitation_mm": grouped["precipitation_mm"].sum(min_count=1),
        "wind_speed_mean_ms": grouped["wind_speed_ms"].mean(),
        "wind_u_mean_ms": grouped["wind_u_ms"].mean(),
        "wind_v_mean_ms": grouped["wind_v_ms"].mean(),
        "boundary_layer_height_mean_m": grouped["boundary_layer_height_m"].mean(),
        "boundary_layer_height_max_m": grouped["boundary_layer_height_m"].max(),
        "surface_pressure_mean_hpa": grouped["surface_pressure_hpa"].mean(),
    })
    out["wind_direction_mean_deg"] = wind_direction(out["wind_u_mean_ms"], out["wind_v_mean_ms"])
    counts = grouped[list(sources.values())].count()
    for column in out.columns:
        prefix = next(p for p in sources if column.startswith(p))
        out[column] = out[column].where(counts[sources[prefix]] >= min_hours)
    return out.reset_index()


# ------------------------------------------------------------------ joins

def join_hourly(air_hourly, weather_hourly):
    """Pollution rows with the city weather of the same KST hour."""
    return air_hourly.merge(weather_hourly, on="datetime", how="left", validate="many_to_one")


def join_daily(air_daily, weather_daily):
    """Pollution station-days with the city weather of the same day (for analysis)."""
    return air_daily.merge(weather_daily, on="date", how="left", validate="many_to_one")


def weather_known_at_issue(table, weather_daily, issue_column="date", lags=(0,)):
    """Weather that is known when a forecast is issued at the end of `issue_column`.

    Adds the weather of the issue day (lag 0) and earlier days, with a suffix per lag.
    The weather of the target day is never added: it is only known afterwards.
    """
    out = table.copy()
    columns = [c for c in weather_daily.columns if c != "date"]
    for lag in lags:
        if lag < 0:
            raise ValueError("a negative lag would use weather from after the issue day")
        shifted = weather_daily.assign(date=weather_daily["date"] + pd.Timedelta(days=lag))
        shifted = shifted.rename(columns={c: f"{c}_lag{lag}" for c in columns})
        out = out.merge(shifted.rename(columns={"date": issue_column}), on=issue_column, how="left")
    return out


WEATHER_SOURCES = pd.DataFrame([
    {"source": "ERA5 reanalysis via Open-Meteo", "role": "weather of the analysis (all variables)",
     "what": "model reconstruction of past weather, 0.25-degree grid; nearest grid point to central Seoul",
     "time": "UTC instants; precipitation = total of the hour before", "key_needed": "no",
     "licence": "ERA5: Copernicus licence (attribution); Open-Meteo data: CC BY 4.0",
     "url": "https://open-meteo.com/en/docs/historical-weather-api"},
    {"source": "KMA ASOS 108 Seoul via Meteostat", "role": "check of ERA5 against measurements",
     "what": "observations of the official Seoul surface station (WMO 47108)",
     "time": "UTC instants; 3-hourly before 2018, hourly from 2021", "key_needed": "no",
     "licence": "Meteostat: CC BY-NC 4.0 (not redistributed here)",
     "url": "https://meteostat.net/en/station/47108"},
    {"source": "KMA ASOS 108 Seoul, official", "role": "not used",
     "what": "the same station from the KMA data portals", "time": "KST",
     "key_needed": "yes (KMA API Hub or data.go.kr)", "licence": "KOGL",
     "url": "https://data.kma.go.kr"},
])
