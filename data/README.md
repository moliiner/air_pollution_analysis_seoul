# Data

Raw files are **not committed** (size and licence). Re-download them with `notebooks/00_data_acquisition.ipynb` (or `seoul_air.data.download_raw()`).

| Folder | Content | Edited? |
|---|---|---|
| `raw/` | Files exactly as downloaded | Never |
| `external/` | Reference data for later phases: weather (KMA), district boundaries (GeoJSON) | Never |
| `processed/` | Clean tables written by notebook 01 (Parquet) | Only by code |

## Source

Kaggle, *Air Pollution in Seoul* (`bappekim/air-pollution-in-seoul`): <https://www.kaggle.com/datasets/bappekim/air-pollution-in-seoul>. According to its description the data comes from the Seoul Metropolitan Government. The terms of use are on the Kaggle page and are not restated here.

## File inventory

| File | Content | Rows x columns |
|---|---|---|
| `Measurement_info.csv` | Hourly readings, long format, with instrument status (**used**) | 3,885,066 x 5 |
| `Measurement_item_info.csv` | Pollutant codes, units and grade thresholds | 6 x 7 |
| `Measurement_station_info.csv` | Station code, district, address, coordinates | 25 x 5 |
| `Measurement_summary.csv` | Wide version without status; keeps instrument errors (**not used**, see notebook 01) | 647,511 x 11 |

Period: 2017-01-01 00:00 to 2019-12-31 23:00 (KST), 25 stations, 6 pollutants.

Instrument status codes: 0 normal, 1 needs calibration, 2 abnormal, 4 power cut off, 8 under repair, 9 abnormal data. Only status 0 is kept.

**Network-wide gaps.** 18 days of 2019 have no valid daily mean at any station, for all six pollutants, so 1,077 of the 1,095 days have a city value: 2019-03-09 to 2019-03-17, 05-16, 05-18, 05-22, 07-03, 07-04, 09-07 to 09-09 and 12-01. On 10 of them the raw file has no PM2.5 rows; the other 8 have between 4 and 16 hours for the network. The list is written to `reports/metrics/01_network_gap_days.csv`.

## Processed tables

| File | Grain | Columns |
|---|---|---|
| `air_hourly.parquet` | station x hour (complete grid, NaN when missing) | `datetime`, `station_code`, `district`, 6 pollutants |
| `air_daily.parquet` | station x day (mean when at least 18 valid hours) | `date`, `station_code`, `district`, 6 pollutants, `pm25_grade`, `pm10_grade` |
