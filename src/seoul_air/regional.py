"""Regional inputs for the forecast: AirKorea background stations and CAMS.

AirKorea background stations
    The AirKorea website publishes the final (최종확정) hourly data of every Korean station
    as one zip per year, with one workbook per quarter. `load_background` keeps the
    national background network (국가배경농도), whose station on Baengnyeong Island
    (백령도, code 831492) lies in the Yellow Sea, west of Seoul and upwind of it in the
    cold season. Each year is about 130 MB; only the background rows are kept, in
    data/external/airkorea_background/ (not committed). Labels mark the END of the hour
    (01-24) and are moved to the start of the hour, as for the Seoul files. Invalid
    readings are -999. The final data of a year is published the following year; the
    most recent year is marked provisional on the website ("대기환경월보 통계", may still
    change). In operation the real-time (provisional) values of these stations are
    available at issue time; the final values are their stand-in here.

CAMS
    The Copernicus Atmosphere Monitoring Service global forecasts, through the Open-Meteo
    air quality API, from August 2022 only. The archive is a continuous series stitched
    from successive runs; forecasts at longer lead times are not archived, so CAMS can only
    describe the air upwind of Seoul up to the issue time, not forecast the target days.
"""
import io
import zipfile

import numpy as np
import pandas as pd

from seoul_air import config

AIRKOREA_PAGE = "https://www.airkorea.or.kr/web/last_amb_hour_data?pMENU_NO=123"
AIRKOREA_FILE_URL = "https://www.airkorea.or.kr/jfile/readDownloadFile.do"
# (fileId, fileSeq) of each yearly zip on the page; the download checks the file name
AIRKOREA_FILES = {year: ("1657eebba9237", year - 2000) for year in range(2015, 2026)}
BACKGROUND_NETWORK = "국가배경농도"
BAENGNYEONG = "831492"
BACKGROUND_DIR = config.DATA_EXTERNAL / "airkorea_background"
COLUMNS = ["region", "network", "code", "name", "label", "so2", "co", "o3", "no2", "pm10", "pm25", "address"]

CAMS_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
CAMS_FIRST_DAY = "2022-08-01"
# Points upwind of Seoul (west and north-west) and Seoul itself, latitude and longitude
CAMS_POINTS = {
    "seoul": (37.57, 126.98),
    "baengnyeong": (37.97, 124.63),
    "shandong": (36.67, 117.00),
    "beijing_tianjin": (39.50, 116.80),
    "liaoning": (41.80, 123.40),
}
CAMS_RAW = config.DATA_RAW / "cams"


def read_quarter(content):
    """Rows of the background network in one quarterly workbook (bytes)."""
    from python_calamine import CalamineWorkbook

    workbook = CalamineWorkbook.from_filelike(io.BytesIO(content))
    frames = []
    for sheet in workbook.sheet_names:
        rows = workbook.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        columns = list(COLUMNS)
        if len(rows[0]) == len(columns) - 1:  # some workbooks have no network column
            columns.remove("network")
        frame = pd.DataFrame(rows[1:], columns=columns)
        if "network" in frame:
            frame = frame[frame["network"] == BACKGROUND_NETWORK]
        else:
            frame = frame[frame["code"].astype(str).str.startswith(BAENGNYEONG)]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def label_to_start(labels):
    """AirKorea labels (YYYYMMDDHH, hour 01-24 = end of the hour) to start-of-hour times."""
    text = pd.Series(labels).astype(str).str.replace(r"\.0$", "", regex=True)
    return pd.to_datetime(text.str[:8], format="%Y%m%d") + pd.to_timedelta(text.str[8:10].astype(int) - 1, unit="h")


def tidy(rows):
    out = pd.DataFrame({
        "datetime": label_to_start(rows["label"]).to_numpy(),
        "code": rows["code"].astype(str).str.replace(r"\.0$", "", regex=True).to_numpy(),
        "name": rows["name"].astype(str).to_numpy(),
    })
    for pollutant in ["so2", "co", "o3", "no2", "pm10", "pm25"]:
        values = pd.to_numeric(rows[pollutant], errors="coerce").to_numpy(dtype=float)
        out[pollutant] = np.where(values < 0, np.nan, values)  # -999 marks invalid readings
    return out


def download_background_year(year, force=False):
    """Download the AirKorea final zip of one year and keep the background stations."""
    import requests

    target = BACKGROUND_DIR / f"background_{year}.parquet"
    if target.exists() and not force:
        return target
    file_id, seq = AIRKOREA_FILES[year]
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    session.get(AIRKOREA_PAGE, timeout=60)
    response = session.get(AIRKOREA_FILE_URL, params={"fileId": file_id, "fileSeq": seq}, timeout=3600)
    response.raise_for_status()
    disposition = response.headers.get("Content-Disposition", "")
    if f"{year}.zip" not in disposition:
        raise RuntimeError(f"AirKorea served {disposition!r} for {year}")
    frames = []
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for info in archive.infolist():
            if info.file_size and info.filename.lower().endswith((".xlsx", ".xls")):
                frames.append(read_quarter(archive.read(info)))
    out = tidy(pd.concat(frames, ignore_index=True))
    out = out[out["datetime"].dt.year == year].sort_values(["code", "datetime"]).reset_index(drop=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(target, index=False)
    return target


def load_background(first_year=2015, last_year=2025, download=True):
    """Hourly readings of the background stations, start-of-hour KST."""
    frames = []
    for year in range(first_year, last_year + 1):
        path = BACKGROUND_DIR / f"background_{year}.parquet"
        if not path.exists():
            if not download:
                raise FileNotFoundError(path)
            download_background_year(year)
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def download_cams(first_day=CAMS_FIRST_DAY, last_day="2025-12-31", force=False):
    """Hourly CAMS PM2.5, PM10 and dust at CAMS_POINTS (Open-Meteo, times in KST)."""
    import requests

    path = CAMS_RAW / f"cams_{first_day}_{last_day}.csv"
    if path.exists() and not force:
        return path
    frames = []
    for name, (lat, lon) in CAMS_POINTS.items():
        response = requests.get(CAMS_URL, timeout=300, params={
            "latitude": lat, "longitude": lon, "hourly": "pm2_5,pm10,dust", "timezone": "Asia/Seoul",
            "start_date": first_day, "end_date": last_day})
        response.raise_for_status()
        hourly = response.json()["hourly"]
        frame = pd.DataFrame(hourly).rename(columns={"time": "datetime"})
        frame["point"] = name
        frames.append(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_csv(path, index=False)
    return path


def read_cams(path):
    """CAMS hourly values; Open-Meteo labels the instant, kept as the hour's time in KST."""
    frame = pd.read_csv(path, parse_dates=["datetime"])
    return frame.pivot(index="datetime", columns="point", values=["pm2_5", "pm10", "dust"])
