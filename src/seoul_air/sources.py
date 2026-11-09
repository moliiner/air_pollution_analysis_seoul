"""Download and read the official Seoul hourly files for 2015-2025.

Two Seoul Open Data Plaza datasets hold the same provisional hourly readings:

- OA-15526 "서울시 대기오염 측정정보": one CSV per year up to 2022, long format, with the
  instrument status of every reading, labelled by the START of the hour.
- OA-2221 "서울시 기간별 시간평균 대기환경 정보": one file per year from 2021 (monthly
  before), wide format, readings flagged by the instruments already removed,
  labelled by the END of the hour.

`load_extended_measurements` uses OA-15526 for 2015-2022 and OA-2221 for 2023-2025 and
returns the schema of `data.load_measurements`: start-of-hour timestamps in KST.
"""
import io
import zipfile

import pandas as pd

from seoul_air import config
from seoul_air.config import ITEM_CODES, STATUS_NORMAL

DOWNLOAD_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
PAGE_URL = "https://data.seoul.go.kr/dataList/{dataset}/S/1/datasetView.do"
RAW_DIR = config.DATA_RAW / "seoul"

# File ids ("seq") of the portal. They can change when the portal is updated, so every
# download checks the file name the server returns.
OA15526 = {2015: 114, 2016: 115, 2017: 116, 2018: 117, 2019: 118, 2020: 119, 2021: 120, 2022: 122}
OA2221 = {2021: 32, 2022: 33, 2023: 34, 2024: 35, 2025: 36}
SOURCE_YEARS = {"OA-15526": range(2015, 2023), "OA-2221": range(2023, 2026)}

OA2221_COLUMNS = ["label", "area_code", "area", "airkorea_code", "name_ko", "pm10", "pm10_24h",
                  "pm25", "o3", "no2", "co", "so2"]
POLLUTANT_CODES = {name: code for code, name in ITEM_CODES.items()}


def expected_name(dataset, year):
    if dataset == "OA-15526":
        return f"AIR_HOUR_{year}.csv"
    return f"서울시_기간별_시간평균_대기환경_정보_{year}.zip"


def raw_path(dataset, year):
    return RAW_DIR / (f"AIR_HOUR_{year}.csv" if dataset == "OA-15526" else f"OA-2221_{year}.zip")


def download_file(dataset, year, force=False):
    """Download one yearly file into data/raw/seoul and check its name."""
    import requests

    path = raw_path(dataset, year)
    if path.exists() and not force:
        return path
    seq = (OA15526 if dataset == "OA-15526" else OA2221)[year]
    response = requests.post(
        DOWNLOAD_URL,
        data={"infId": dataset, "seqNo": "", "seq": seq, "infSeq": 3},
        headers={"User-Agent": "Mozilla/5.0", "Referer": PAGE_URL.format(dataset=dataset)},
        timeout=900,
    )
    response.raise_for_status()
    disposition = response.headers.get("Content-Disposition", "")
    served = disposition.encode("latin-1").decode("utf-8", errors="replace")
    if expected_name(dataset, year) not in served:
        raise RuntimeError(f"{dataset} seq {seq} served {served!r}, expected {expected_name(dataset, year)}; "
                           f"the portal ids may have changed, see {PAGE_URL.format(dataset=dataset)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def download_extended(force=False):
    """Every file used for 2015-2025, plus OA-2221 2021-2022 to check the overlap."""
    paths = [download_file("OA-15526", year, force) for year in OA15526]
    paths += [download_file("OA-2221", year, force) for year in OA2221]
    return paths


def load_stations_reference():
    """District, Korean name, Seoul and AirKorea station codes, and coordinates."""
    return pd.read_csv(config.ROOT / "data" / "reference" / "stations.csv",
                       dtype={"airkorea_code": str})


def read_oa15526(path):
    """Long table: start-of-hour timestamp, station, pollutant, value, status."""
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype={0: str},
                      usecols=[0, 1, 2, 3, 4])
    raw.columns = ["label", "station_code", "item_code", "value", "status"]
    out = pd.DataFrame({
        "datetime": pd.to_datetime(raw["label"], format="%Y%m%d%H"),
        "station_code": raw["station_code"].astype("int16"),
        "item_code": raw["item_code"].astype("int8"),
        "value": raw["value"].astype(float),
        "status": raw["status"].astype("int8"),
    })
    out["pollutant"] = out["item_code"].map(ITEM_CODES).astype("category")
    return out


def read_oa2221(path):
    """Long table in the schema of read_oa15526.

    The official label marks the END of the hour, so one hour is subtracted. The
    file has no instrument status: readings flagged by the instruments are already
    blank, so the remaining ones get status 0.
    """
    raw = path.read_bytes()
    if raw[:2] == b"PK":
        archive = zipfile.ZipFile(io.BytesIO(raw))
        raw = archive.read(next(n for n in archive.namelist() if n.lower().endswith(".csv")))
    for encoding in ("utf-8-sig", "cp949"):
        try:
            wide = pd.read_csv(io.BytesIO(raw), encoding=encoding, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    wide.columns = OA2221_COLUMNS
    codes = load_stations_reference().set_index("airkorea_code")["seoul_code"]
    wide["station_code"] = wide["airkorea_code"].map(codes)
    if wide["station_code"].isna().any():
        raise ValueError(f"unknown AirKorea codes: {sorted(wide.loc[wide.station_code.isna(), 'airkorea_code'].unique())}")
    wide["datetime"] = pd.to_datetime(wide["label"], format="%Y%m%d%H%M") - pd.Timedelta(hours=1)
    pollutants = list(POLLUTANT_CODES)
    long = wide.melt(id_vars=["datetime", "station_code"], value_vars=pollutants,
                     var_name="pollutant", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    return pd.DataFrame({
        "datetime": long["datetime"].to_numpy(),
        "station_code": long["station_code"].astype("int16").to_numpy(),
        "item_code": long["pollutant"].map(POLLUTANT_CODES).astype("int8").to_numpy(),
        "value": long["value"].to_numpy(),
        "status": pd.Series(STATUS_NORMAL, index=long.index, dtype="int8").to_numpy(),
        "pollutant": pd.Categorical(long["pollutant"].to_numpy(), categories=sorted(ITEM_CODES.values())),
    })


def load_extended_measurements(first_year=2015, last_year=2025):
    """Hourly readings of 2015-2025 from both datasets, with a `source` column.

    OA-15526 covers 2015-2022 and OA-2221 2023-2025. Because OA-2221 labels the end of
    the hour, its 2023 file starts with the last hour of 2022, which is dropped in
    favour of OA-15526; the last hour of 2025 is in the 2026 file and is missing.
    """
    years = range(first_year, last_year + 1)
    frames = []
    for year in years:
        if year in SOURCE_YEARS["OA-15526"]:
            frame = read_oa15526(raw_path("OA-15526", year))
            frames.append(frame[frame["datetime"].dt.year == year].assign(source="OA-15526"))
    # OA-2221 files are read together: the last hour of each year sits in the next file
    later = [y for y in years if y in SOURCE_YEARS["OA-2221"]]
    if later:
        files = [raw_path("OA-2221", y) for y in range(later[0], later[-1] + 2) if raw_path("OA-2221", y).exists()]
        frame = pd.concat([read_oa2221(f) for f in files], ignore_index=True)
        frames.append(frame[frame["datetime"].dt.year.isin(later)].assign(source="OA-2221"))
    out = pd.concat(frames, ignore_index=True)
    out["pollutant"] = out["pollutant"].astype("category")
    out["source"] = out["source"].astype("category")
    return out


SOURCE_CATALOG = pd.DataFrame([
    {"source": "Kaggle bappekim/air-pollution-in-seoul", "publisher": "Kaggle user, from OA-15526",
     "years_available": "2017-2019", "used_for": "notebooks 00-06",
     "format": "CSV, long, one file", "hour_label": "start of hour (00-23)",
     "instrument_status": "yes", "final": "no (copy of provisional data)", "licence": "CC BY-SA 4.0",
     "url": "https://www.kaggle.com/datasets/bappekim/air-pollution-in-seoul"},
    {"source": "OA-15526 Seoul air pollution measurements", "publisher": "Seoul Research Institute of Public Health and Environment",
     "years_available": "1988-2022", "used_for": "2015-2022",
     "format": "CSV per year, long, UTF-8", "hour_label": "start of hour (00-23)",
     "instrument_status": "yes", "final": "no (stated on the page)", "licence": "KOGL Type 1 (attribution)",
     "url": "https://data.seoul.go.kr/dataList/OA-15526/S/1/datasetView.do"},
    {"source": "OA-2221 Seoul hourly air quality by period", "publisher": "Seoul Air Quality Policy Division",
     "years_available": "2019-2025", "used_for": "2023-2025",
     "format": "CSV per month (CP949) to 2020-06, ZIP per year (UTF-8) after; wide", "hour_label": "end of hour (00 = 24 of the day before)",
     "instrument_status": "no (flagged readings left blank)", "final": "no (same values as OA-15526)", "licence": "KOGL Type 1 (attribution)",
     "url": "https://data.seoul.go.kr/dataList/OA-2221/S/1/datasetView.do"},
    {"source": "AirKorea final measurements (data.go.kr 15122830)", "publisher": "Korea Environment Corporation / NIER",
     "years_available": "versions 2018-2024 on data.go.kr", "used_for": "check of 2024 (tools/compare_airkorea_final.py)",
     "format": "XLSX per year, all Korean stations, about 400 MB", "hour_label": "end of hour (01-24)",
     "instrument_status": "no (quality-assured values only)", "final": "yes", "licence": "KOGL Type 3 (attribution, no derivatives)",
     "url": "https://www.data.go.kr/data/15122830/fileData.do"},
])


def agreement(a, b, lags=(-1, 0, 1), tolerance=1e-6):
    """Share of identical values when the timestamps of b are moved by each lag (hours).

    a and b are long tables with datetime, station_code, pollutant and value. Only the
    hours present in both are compared.
    """
    keys = ["datetime", "station_code", "pollutant"]
    left = a[keys + ["value"]].astype({"pollutant": str})
    rows = []
    for lag in lags:
        right = b[keys + ["value"]].astype({"pollutant": str})
        right = right.assign(datetime=right["datetime"] + pd.Timedelta(hours=lag))
        both = left.merge(right, on=keys, suffixes=("_a", "_b"))
        identical = (both["value_a"] - both["value_b"]).abs() < tolerance
        rows.append({"lag_hours": lag, "compared": len(both), "identical": int(identical.sum()),
                     "identical_pct": 100 * identical.mean() if len(both) else float("nan")})
    return pd.DataFrame(rows)
