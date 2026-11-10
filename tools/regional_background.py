"""Monthly PM2.5 at the regional background station of Baengnyeong Island, 2018-2024.

Baengnyeong Island (백령도, AirKorea code 831492, network 국가배경농도) lies in the Yellow
Sea, about 200 km west of Seoul and upwind of it in the cold season. Its PM2.5 reflects
the regional and transboundary air reaching Korea, with little influence of Seoul's own
emissions, which makes it a reference for the regional part of Seoul's changes.

The script downloads the AirKorea final workbook of each year from data.go.kr (about
400 MB each, see compare_airkorea_final.py), keeps Baengnyeong and the 25 Seoul urban
stations, and writes monthly means to data/reference/baengnyeong_seoul_monthly_2018_2024.csv.
Only monthly means are kept: the final data is licensed under KOGL Type 3 (no derivatives),
so the hourly readings are not redistributed.

    pip install python-calamine
    python tools/regional_background.py
"""
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))
from compare_airkorea_final import VERSIONS, download_workbook, seoul_rows  # noqa: E402
from seoul_air.sources import load_stations_reference  # noqa: E402

BAENGNYEONG = "831492"
MIN_HOURS_PER_MONTH = 0.75  # share of the hours of a month with a reading


def monthly(year):
    seoul = set(load_stations_reference()["airkorea_code"])
    with tempfile.TemporaryDirectory() as folder:
        path, name = download_workbook(year, Path(folder))
        rows = seoul_rows(path, seoul | {BAENGNYEONG})
    rows = rows[(rows["pollutant"] == "pm25") & (rows["datetime"].dt.year == year)]
    rows["site"] = rows["code"].map(lambda c: "baengnyeong" if c == BAENGNYEONG else "seoul_station")
    # Seoul: hourly mean of the 25 stations first, so that it is one series like Baengnyeong
    seoul_hourly = rows[rows["site"] == "seoul_station"].groupby("datetime")["final"].mean().rename("seoul")
    background = rows[rows["site"] == "baengnyeong"].set_index("datetime")["final"].rename("baengnyeong")
    hourly = pd.concat([seoul_hourly, background], axis=1)
    hours_in_month = hourly.index.to_period("M").value_counts().sort_index()
    grouped = hourly.groupby(hourly.index.to_period("M"))
    out = grouped.mean().where(grouped.count().div(hours_in_month, axis=0) >= MIN_HOURS_PER_MONTH)
    out = out.rename_axis("month").reset_index()
    out["month"] = out["month"].astype(str)
    out["source"] = name
    return out


def main():
    frames = []
    for year in sorted(VERSIONS):
        frame = monthly(year)
        print(year, frame[["seoul", "baengnyeong"]].notna().sum().to_dict(), flush=True)
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    target = ROOT / "data" / "reference" / "baengnyeong_seoul_monthly_2018_2024.csv"
    out.to_csv(target, index=False, encoding="utf-8")
    print("written to", target.relative_to(ROOT), out.shape)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
