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

## Weather, 2015-2025 (notebook 08)

Downloaded by `seoul_air.weather.download_era5()` and `download_station_observations()` into `data/raw/weather/` (not committed). No key is needed.

| Source | Role | Time | Licence |
|---|---|---|---|
| [ERA5 reanalysis](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels) through the [Open-Meteo historical API](https://open-meteo.com/en/docs/historical-weather-api) | Weather of the analysis; nearest grid point to central Seoul (37.5 N, 127.0 E) | UTC instants; precipitation is the total of the hour before | ERA5: Copernicus licence, attribution ("Contains modified Copernicus Climate Change Service information"); Open-Meteo: CC BY 4.0 |
| KMA ASOS 108 Seoul (WMO 47108) through [Meteostat](https://meteostat.net/en/station/47108) | Check of ERA5 against measurements only | UTC instants; 3-hourly before 2018, hourly from 2021; precipitation from 2022 | CC BY-NC 4.0, not redistributed |

The official KMA station data (data.kma.go.kr, KMA API Hub, data.go.kr) needs a personal key and is not used.

| Column | Unit | Hour [h, h+1) KST gets |
|---|---|---|
| `temperature_c` | degC (2 m) | mean of the instants h and h+1 |
| `relative_humidity_pct` | % (2 m) | mean of the instants h and h+1 |
| `precipitation_mm` | mm | the total reported at h+1 |
| `wind_speed_ms` | m/s (10 m) | mean of the instants h and h+1 |
| `wind_direction_deg` | degrees the wind blows **from** | from the mean wind components |
| `wind_u_ms`, `wind_v_ms` | m/s, eastward and northward | mean of the instants h and h+1 |
| `boundary_layer_height_m` | m (mixing layer) | mean of the instants h and h+1 |
| `surface_pressure_hpa` | hPa | mean of the instants h and h+1 |

- **Time zone:** ERA5 is in UTC and is converted to KST (UTC+9), with the hour labelled by its start like the pollution tables.
- **Missing data:** none except the boundary layer height for 2024-01-01 to 2024-06-30 (UTC), absent from the Open-Meteo archive; left missing. Daily values need all 24 hours of their own variable.
- **Single point:** one ERA5 grid cell (about 25 km) stands for the whole city.
- **Observed weather is for analysis, not for forecasting:** the weather of a day is known only after it. A next-day forecast may use the weather of the issue day and earlier (`weather_known_at_issue`), or a weather forecast for the target day, never the observed weather of the target day.

| File | Grain |
|---|---|
| `weather_hourly_2015_2025.parquet` | KST hour |
| `weather_daily_2015_2025.parquet` | KST day |
| `air_weather_daily_2015_2025.parquet` | station-day of `air_daily_2015_2025` with the weather of the same day |

## Population, stations by network, CAI, regional background (notebooks 02-04, 09)

| Data | Source | Notes |
|---|---|---|
| District population, end of each year 2015-2025 | Ministry of the Interior and Safety, resident registration statistics ([jumin.mois.go.kr](https://jumin.mois.go.kr/statMonth.do)), downloaded by `seoul_air.population.download_population()` into `data/raw/population/` | Monthly CSV of every Korean district (CP949); December is used. The loader checks that the 25 districts add up to the Seoul total. Registered residents (거주자, 거주불명자, 재외국민), not foreigners. |
| `reference/seoul_stations_by_network_2024.csv` | AirKorea final data 2024, made by `tools/seoul_networks_2024.py` | Annual means of the 40 Seoul stations: 25 urban (도시대기, the project's stations) and 15 roadside (도로변대기). |
| `reference/baengnyeong_seoul_monthly_2018_2024.csv` | AirKorea final data 2018-2024, made by `tools/regional_background.py` | Monthly PM2.5 of the national background station of Baengnyeong Island (백령도, code 831492, 국가배경농도) and of the mean of the 25 Seoul urban stations; a month needs 75% of its hours. Only monthly means are stored: the final data is under KOGL Type 3 (no derivative works), so hourly values are not redistributed. Used in notebook 09. |
| AirKorea final data 2015-2025, background stations | [AirKorea, 최종확정자료 다운로드](https://www.airkorea.or.kr/web/last_amb_hour_data?pMENU_NO=123), one zip per year with quarterly workbooks, downloaded by `seoul_air.regional.load_background()` | Only the national background network (국가배경농도, including Baengnyeong 831492) is kept, in `external/airkorea_background/` (not committed). Labels are end-of-hour (01-24), moved to the start of the hour; -999 is invalid. The 2025 file is marked provisional on the website. Used in notebook 10. |
| JMA forecasts 2018-2025 | [Open-Meteo Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api), model `jma_seamless`, downloaded by `seoul_air.nwp.download()` into `raw/weather/` | Hourly forecasts at Seoul made 2, 3 and 4 days before each hour; the archive of other models starts in 2024 (GFS temperature in 2021); no boundary layer height. CC BY 4.0. |
| CAMS 2022-2025 | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), downloaded by `seoul_air.regional.download_cams()` into `raw/cams/` | PM2.5, PM10 and dust at five points (Seoul, Baengnyeong, Shandong, Beijing-Tianjin, Liaoning), from August 2022; forecasts at longer lead times are not archived. |
| CAI breakpoints and rules | [Seoul Metropolitan Government](https://cleanair.seoul.go.kr/information/info3), [AirKorea](https://www.airkorea.or.kr/eng/khaiInfo?pMENU_NO=166) | Implemented in `seoul_air.cai`; the O3 scale ends at 0.6 ppm (the Kaggle item file shows 0.5). |

