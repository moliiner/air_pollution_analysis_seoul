# Data

The project has two datasets: the **Kaggle** files (2017-2019), used by notebooks 00-06, and the **extended** official Seoul files (2015-2025), built by notebook 07 and used by the next phase of the analysis.

Raw files are **not committed** (size and licence). Re-download them with `notebooks/00_data_acquisition.ipynb` (or `seoul_air.data.download_raw()`).

| Folder | Content | Edited? |
|---|---|---|
| `raw/` | Files exactly as downloaded | Never |
| `external/` | Reference data for later phases: weather (KMA), district boundaries (GeoJSON) | Never |
| `processed/` | Clean tables written by notebook 01 (Parquet) | Only by code |
| `reference/` | Small curated tables, committed to the repository | By hand, with a source |

## Kaggle source (notebooks 00-06)

Kaggle, *Air Pollution in Seoul* (`bappekim/air-pollution-in-seoul`): <https://www.kaggle.com/datasets/bappekim/air-pollution-in-seoul>. According to its description the data comes from the Seoul Metropolitan Government. The terms of use are on the Kaggle page and are not restated here.

## File inventory

| File | Content | Rows x columns |
|---|---|---|
| `Measurement_info.csv` | Hourly readings, long format, with instrument status (**used**) | 3,885,066 x 5 |
| `Measurement_item_info.csv` | Pollutant codes, units and grade thresholds | 6 x 7 |
| `Measurement_station_info.csv` | Station code, district, address, coordinates | 25 x 5 |
| `Measurement_summary.csv` | Wide version without status; keeps instrument errors (**not used**, see notebook 01) | 647,511 x 11 |

Period: 2017-01-01 00:00 to 2019-12-31 23:00, 25 stations, 6 pollutants.

**Timestamps.** Each timestamp is in Korean Standard Time (KST, UTC+9, no daylight saving) and marks the **start** of the hourly average: 07:00 is the average of 07:00-08:00, and a calendar day groups 00:00-24:00. Official Korean sources label the same average by the **end** of the hour (AirKorea writes 1-24 h; the Seoul Open API writes 00:00 instead of 24:00), so a Kaggle timestamp is one hour earlier than the official label. The Kaggle page does not state either point; notebook 01 (section 3.1) verifies both:

- Hourly values downloaded from the Seoul Open API equal the Kaggle values one hour before their official label (`reference/seoul_api_hourly_samples.csv`).
- The real-time service publishes each label in KST as soon as that hour has ended (`reference/realtime_label_check.csv`), so its labels mark the end of the hour.

What remains an assumption: that the archive of 2017-2019 used the same end-of-hour convention as the service in 2026. It is supported by the offset being the same one hour in every sampled hour of 2017-2019 that can be compared.

Instrument status codes: 0 normal, 1 needs calibration, 2 abnormal, 4 power cut off, 8 under repair, 9 abnormal data. Only status 0 is kept.

**Network-wide gaps.** In the Kaggle file, 18 days of 2019 have no valid daily mean at any station, for all six pollutants, so 1,077 of the 1,095 days have a city value: 2019-03-09 to 2019-03-17, 05-16, 05-18, 05-22, 07-03, 07-04, 09-07 to 09-09 and 12-01. On 10 of them the raw file has no PM2.5 rows; the other 8 have between 4 and 16 hours for the network. The list is written to `reports/metrics/01_network_gap_days.csv`. Notebook 07 shows that the official OA-15526 file has these days: they are missing from the Kaggle copy only.

## Processed tables

| File | Grain | Columns |
|---|---|---|
| `air_hourly.parquet` | station x hour (complete grid, NaN when missing) | `datetime`, `station_code`, `district`, 6 pollutants |
| `air_daily.parquet` | station x day (mean when at least 18 valid hours) | `date`, `station_code`, `district`, 6 pollutants, `pm25_grade`, `pm10_grade` |

## Station history

`reference/station_history.csv` transcribes table 19.1 (urban network, printed pages 97-98) of the [2018 Seoul Air Quality Assessment Report](https://news.seoul.go.kr/env/files/2021/01/60112177d83700.85894331.pdf), Seoul Metropolitan Government: year of installation, of the latest equipment replacement and of the latest relocation, and the previous site. The site names are translated from Korean.

- The table gives years only. It does not say which instrument was replaced, and it lists a single latest change per station.
- Relocations in the study period: Seongdong-gu, Seodaemun-gu, Mapo-gu and Songpa-gu, all in 2018. The same report dates Mapo-gu to August 2018 and Songpa-gu to November 2018.
- The dataset gives one location per station, the latest one, so its coordinates do not show these moves.

## Extended source, 2015-2025 (notebook 07)

Downloaded by `seoul_air.sources.download_extended()` into `data/raw/seoul/` (not committed). Notebook 07 compares the candidate sources:

| Source | Years | Format | Hour label | Instrument status | Final data | Licence | Use |
|---|---|---|---|---|---|---|---|
| [OA-15526](https://data.seoul.go.kr/dataList/OA-15526/S/1/datasetView.do) Seoul air pollution measurements | 1988-2022 | CSV per year, long, UTF-8 | Start of hour (00-23) | Yes | No (stated on the page) | KOGL Type 1: attribution | 2015-2022 |
| [OA-2221](https://data.seoul.go.kr/dataList/OA-2221/S/1/datasetView.do) Seoul hourly air quality by period | 2019-2025 | CSV per month to 2020-06 (CP949), ZIP per year after (UTF-8); wide | End of hour (00 = 24 of the day before) | No: flagged readings left blank | No: same values as OA-15526 | KOGL Type 1: attribution | 2023-2025 |
| [AirKorea final measurements](https://www.data.go.kr/data/15122830/fileData.do) (data.go.kr 15122830) | Versions 2018-2024 | XLSX per year, every Korean station, about 400 MB | End of hour (01-24) | No: quality-assured values only | Yes | KOGL Type 3: attribution, no derivatives | Check of 2024 only |

- **Why the Seoul files:** they are small, downloadable by script, licensed for modification, and OA-15526 keeps the instrument status. For PM10 and PM2.5 they equal the final data of 2024 wherever both have a value (`reference/final_vs_provisional_2024.csv`, made by `tools/compare_airkorea_final.py`).
- **Nothing has to be downloaded by hand.** Earlier AirKorea years (2015-2017) are only on airkorea.or.kr, which refused scripted access during this work; they are not needed.
- **Validation:** `reference/official_annual_means.csv` holds official annual means: three urban stations for every year (Seoul Open API, dataset OA-2216; the public sample key returns only the first five rows of each year) and the whole-Seoul figures announced by the city, with the article of each. A personal API key from the Seoul Open Data Plaza would give the 25 stations.

### Changes of methodology

| Topic | Kaggle (notebooks 00-06) | Extended (notebook 07) |
|---|---|---|
| Source | Kaggle copy of OA-15526, 2017-2019 | OA-15526 2015-2022, OA-2221 2023-2025 |
| Hour label | Start of hour | Start of hour; OA-2221 is moved back one hour |
| Faulty readings | Dropped by instrument status | Same up to 2022; from 2023 the provider leaves them blank. In 2022 OA-2221 still kept 1,129 flagged readings (no PM2.5), which moved the annual means by at most 0.0742 ug/m3 |
| Data status | Provisional | Provisional; checked against the final data of 2024 and the official annual means |
| Station codes | Seoul codes 101-125 | Same; OA-2221 uses AirKorea codes, mapped with `reference/stations.csv` |
| Year boundaries | - | The last hour of 2025 is in the 2026 file and is missing |

### Processed tables of the extended data

| File | Grain | Columns |
|---|---|---|
| `air_hourly_2015_2025.parquet` | station x hour, 2015-2025 | as `air_hourly.parquet` |
| `air_daily_2015_2025.parquet` | station x day (at least 18 valid hours) | as `air_daily.parquet` |

