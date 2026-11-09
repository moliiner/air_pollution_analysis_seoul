"""Compare the Seoul provisional readings of one year with the AirKorea final data.

AirKorea (National Institute of Environmental Research) publishes the final, quality-
assured hourly readings of every Korean station once a year, as one workbook of about
400 MB on data.go.kr (dataset 15122830). This script downloads the workbook of a year,
keeps the 25 Seoul urban stations, and compares them with the Seoul OA-2221 file of the
same year. It writes a summary to data/reference/final_vs_provisional_<year>.csv.

It is not part of the pipeline: it needs `pip install python-calamine` (fast reader for
the workbook) and about 1 GB of free disk space while it runs.

    python tools/compare_airkorea_final.py 2024
"""
import sys
import tempfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from seoul_air import sources  # noqa: E402

PAGE = "https://www.data.go.kr/data/15122830/fileData.do"
# One data.go.kr record per published year (detail key of the page, history number)
VERSIONS = {2024: ("uddi:ce62937c-cd4f-46e6-92f3-e438ceb7d781", 2)}
POLLUTANTS = ["so2", "co", "o3", "no2", "pm10", "pm25"]


def download_workbook(year, folder):
    detail, _ = VERSIONS[year]
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    session.get(PAGE, timeout=60)
    info = session.post("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do", timeout=60,
                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": PAGE},
                        data={"publicDataDetailPk": detail, "publicDataPk": "15122830", "atchFileId": "",
                              "fileDetailSn": "1", "publicDataTyCode": "PR0051"}).json()
    name = info["dataSetFileDetailInfo"]["dataNm"]
    if not name.endswith(f"{year}1231"):
        raise RuntimeError(f"data.go.kr served {name!r} for {year}")
    path = folder / f"airkorea_final_{year}.xlsx"
    with session.get("https://www.data.go.kr/cmm/cmm/fileDownload.do", stream=True, timeout=1800,
                     params={"atchFileId": info["atchFileId"], "fileDetailSn": info["fileDetailSn"]}) as response:
        response.raise_for_status()
        with open(path, "wb") as out:
            for chunk in response.iter_content(1 << 20):
                out.write(chunk)
    return path, name


def seoul_rows(path, codes):
    from python_calamine import CalamineWorkbook

    frames = []
    workbook = CalamineWorkbook.from_path(str(path))
    for sheet in workbook.sheet_names:
        rows = workbook.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        frame = pd.DataFrame(rows[1:], columns=["region", "network", "code", "name", "label", *POLLUTANTS, "address"])
        frame["code"] = frame["code"].astype(str).str.replace(r"\.0$", "", regex=True)
        frames.append(frame[frame["code"].isin(codes)])
    out = pd.concat(frames, ignore_index=True)
    label = out["label"].astype(str).str.replace(r"\.0$", "", regex=True)
    # Final data label the end of the hour from 01 to 24: move to the start of the hour
    out["datetime"] = (pd.to_datetime(label.str[:8], format="%Y%m%d")
                       + pd.to_timedelta(label.str[8:10].astype(int) - 1, unit="h"))
    long = out.melt(id_vars=["datetime", "code"], value_vars=POLLUTANTS, var_name="pollutant", value_name="final")
    long["final"] = pd.to_numeric(long["final"], errors="coerce")  # blank cells become NaN
    return long


def compare(year):
    stations = sources.load_stations_reference()
    codes = dict(zip(stations["airkorea_code"], stations["seoul_code"]))
    with tempfile.TemporaryDirectory() as folder:
        path, name = download_workbook(year, Path(folder))
        final = seoul_rows(path, set(codes))
    final["station_code"] = final["code"].map(codes)
    provisional = sources.read_oa2221(sources.raw_path("OA-2221", year))
    provisional = provisional[provisional["datetime"].dt.year == year]
    provisional = provisional.rename(columns={"value": "provisional"})[["datetime", "station_code", "pollutant", "provisional"]]
    provisional["pollutant"] = provisional["pollutant"].astype(str)
    final = final[final["datetime"].dt.year == year]
    both = final.merge(provisional, on=["datetime", "station_code", "pollutant"], how="outer")

    rows = []
    for pollutant, group in both.groupby("pollutant"):
        present = group["final"].notna() & group["provisional"].notna()
        station_means = group.groupby("station_code")[["final", "provisional"]].mean()
        rows.append({
            "year": year, "pollutant": pollutant, "hours": len(group),
            "final_present_pct": 100 * group["final"].notna().mean(),
            "provisional_present_pct": 100 * group["provisional"].notna().mean(),
            "identical_where_both_pct": 100 * (abs(group["final"] - group["provisional"]) < 1e-6)[present].mean(),
            "only_provisional_pct": 100 * (group["provisional"].notna() & group["final"].isna()).mean(),
            "only_final_pct": 100 * (group["final"].notna() & group["provisional"].isna()).mean(),
            "city_annual_mean_final": station_means["final"].mean(),
            "city_annual_mean_provisional": station_means["provisional"].mean(),
            "max_station_annual_mean_diff": (station_means["final"] - station_means["provisional"]).abs().max(),
            "final_source": name,
        })
    out = pd.DataFrame(rows)
    target = ROOT / "data" / "reference" / f"final_vs_provisional_{year}.csv"
    out.to_csv(target, index=False, encoding="utf-8")
    print(out.round(4).to_string(index=False))
    print("written to", target.relative_to(ROOT))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # station names are Korean
    compare(int(sys.argv[1]) if len(sys.argv) > 1 else 2024)
