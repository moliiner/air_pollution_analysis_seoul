"""Official resident population of the Seoul districts, and population-weighted exposure.

Source: Ministry of the Interior and Safety (MOIS), resident registration population
statistics (주민등록 인구통계), monthly, every district of Korea, downloaded as CSV from
https://jumin.mois.go.kr without a key. The population of December is used for each year.
"""
import io
import re

import numpy as np
import pandas as pd

from seoul_air import config
from seoul_air.sources import load_stations_reference

DOWNLOAD_URL = "https://jumin.mois.go.kr/downloadCsv.do?searchYearMonth=month&xlsStats=2"
PAGE_URL = "https://jumin.mois.go.kr/statMonth.do"
RAW_DIR = config.DATA_RAW / "population"


def raw_path(year, month=12):
    return RAW_DIR / f"mois_population_{year}{month:02d}.csv"


def download_population(years=range(2015, 2026), month=12, force=False):
    """One CSV per year with the population of every Korean district at the end of `month`."""
    import requests

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    paths = []
    for year in years:
        path = raw_path(year, month)
        if force or not path.exists():
            session.get(PAGE_URL, timeout=60)
            response = session.post(DOWNLOAD_URL, timeout=300, headers={"Referer": PAGE_URL}, data={
                "sltOrgType": 1, "sltOrgLvl1": "A", "sltOrgLvl2": "", "gender": "gender", "genderPer": "genderPer",
                "generation": "generation", "sltUndefType": "", "searchYearStart": year,
                "searchMonthStart": f"{month:02d}", "searchYearEnd": year, "searchMonthEnd": f"{month:02d}",
                "sltOrderType": 1, "sltOrderValue": "ASC", "category": "month", "state": 2,
            })
            response.raise_for_status()
            if f"{year}{month:02d}" not in response.headers.get("Content-Disposition", ""):
                raise RuntimeError(f"MOIS did not return the file of {year}-{month:02d}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        paths.append(path)
    return paths


def read_population(path):
    """Population of Seoul and its 25 districts from one MOIS CSV."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            table = pd.read_csv(io.BytesIO(raw), encoding=encoding, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    region = table.iloc[:, 0].str.strip()
    total = table.iloc[:, 1].str.replace(",", "", regex=False).str.strip().astype(int)
    code = region.str.extract(r"\((\d{10})\)")[0]
    name = region.str.replace(r"\s*\(\d{10}\)", "", regex=True).str.strip()
    seoul = code.str.startswith("11")
    out = pd.DataFrame({"name": name[seoul], "admin_code": code[seoul], "population": total[seoul]})
    match = re.search(r"(\d{4})년(\d{1,2})월", table.columns[1])
    out["year"] = int(match.group(1))
    return out.reset_index(drop=True)


def load_population(years=range(2015, 2026), month=12):
    """One row per year and district (English name), plus the Seoul total per year."""
    stations = load_stations_reference()
    names = {f"서울특별시 {ko}": district for ko, district in zip(stations["name_ko"], stations["district"])}
    frames = []
    for year in years:
        table = read_population(raw_path(year, month))
        districts = table[table["name"].isin(names)].assign(district=lambda t: t["name"].map(names))
        if len(districts) != 25:
            raise ValueError(f"{year}: {len(districts)} districts found, expected 25")
        city = table.loc[table["name"] == "서울특별시", "population"]
        if len(city) != 1 or city.iloc[0] != districts["population"].sum():
            raise ValueError(f"{year}: the districts do not add up to the Seoul total")
        frames.append(districts[["year", "district", "population"]])
    return pd.concat(frames, ignore_index=True)


def population_weighted_mean(values, populations):
    """Mean of district values weighted by population, ignoring districts without a value."""
    values = np.asarray(values, dtype=float)
    populations = np.asarray(populations, dtype=float)
    valid = ~np.isnan(values)
    if not valid.any():
        return float("nan")
    return float(np.sum(values[valid] * populations[valid]) / np.sum(populations[valid]))
