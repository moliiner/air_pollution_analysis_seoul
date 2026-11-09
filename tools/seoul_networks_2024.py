"""Annual means of every Seoul station in the AirKorea final data of 2024, by network.

The Seoul files used by the project (OA-15526, OA-2221) hold only the 25 urban stations
(도시대기). AirKorea also runs roadside stations (도로변대기) next to major roads. This
script downloads the AirKorea final workbook of 2024 (about 400 MB, see
compare_airkorea_final.py), keeps every Seoul station and writes its annual means and
network to data/reference/seoul_stations_by_network_2024.csv.

    pip install python-calamine
    python tools/seoul_networks_2024.py
"""
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_airkorea_final import POLLUTANTS, download_workbook  # noqa: E402

NETWORKS = {"도시대기": "urban", "도로변대기": "roadside"}


def seoul_stations(path):
    from python_calamine import CalamineWorkbook

    frames = []
    workbook = CalamineWorkbook.from_path(str(path))
    for sheet in workbook.sheet_names:
        rows = workbook.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        frame = pd.DataFrame(rows[1:], columns=["region", "network", "code", "name", "label", *POLLUTANTS, "address"])
        frames.append(frame[frame["region"].astype(str).str.startswith("서울")])
    out = pd.concat(frames, ignore_index=True)
    out["code"] = out["code"].astype(str).str.replace(r"\.0$", "", regex=True)
    for pollutant in POLLUTANTS:
        out[pollutant] = pd.to_numeric(out[pollutant], errors="coerce")
    return out


def main(year=2024):
    with tempfile.TemporaryDirectory() as folder:
        path, name = download_workbook(year, Path(folder))
        rows = seoul_stations(path)
    grouped = rows.groupby(["code", "name", "network"])
    out = grouped[["pm25", "pm10", "no2", "o3"]].mean()
    out["pm25_hours"] = grouped["pm25"].count()
    out = out.reset_index()
    out["network_en"] = out["network"].map(NETWORKS).fillna("other")
    out["year"] = year
    out["source"] = name
    target = ROOT / "data" / "reference" / f"seoul_stations_by_network_{year}.csv"
    out.to_csv(target, index=False, encoding="utf-8")
    print(out.groupby("network_en")[["pm25", "pm10", "no2", "o3"]].mean().round(4).to_string())
    print("stations:", out["network_en"].value_counts().to_dict(), "| written to", target.relative_to(ROOT))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
