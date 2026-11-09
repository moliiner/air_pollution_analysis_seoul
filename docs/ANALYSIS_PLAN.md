# Analysis Plan

Roadmap for the project, in the order the work should be done. Each phase ends with a checklist.

## Business question

> **When and where is Seoul's air most harmful, and can tomorrow's PM2.5 level be predicted well enough to warn residents?**

Dataset: Kaggle *Air Pollution in Seoul*, hourly, 25 district stations, 2017-2019 (notebooks 00-06), and the official Seoul files for 2015-2025 (notebook 07). See `data/README.md`.

| # | Question | Notebook | Status |
|---|---|---|---|
| 1 | Is the data complete and trustworthy? | `01_data_cleaning` | Done |
| 2 | How do PM2.5 / PM10 vary by year, season, weekday and hour? | `02_eda_temporal` | Done |
| 3 | Can districts be ranked, or do differences depend on the stations? | `03_eda_spatial` | Done |
| 4 | How do pollutants relate, and when do episodes happen? | `04_pollutants_and_episodes` | Done |
| 5 | Can next-day PM2.5 be forecast better than "same as today"? | `05_forecasting` | Done (first version) |
| 6 | What should a citizen or the city take away? | `06_insights_summary` | Done |

Out of scope with this dataset: the effect of the PM seasonal management system (it started in December 2019, when the data ends) and weather drivers (no weather variables).

## Phase 0 - Setup

- [x] Virtual environment and `pip install -r requirements.txt`
- [x] `pytest` passes

## Phase 1 - Data acquisition (`00`)

- [x] Download the Kaggle dataset into `data/raw`
- [x] Inventory in `data/README.md`
- [ ] Read and note the terms of use on the Kaggle page

## Phase 2 - Cleaning (`01`)

- [x] Keep only normal instrument status; count every dropped reading
- [x] Complete hourly grid; missing hours left as missing
- [x] Daily means with the 18-of-24-hours rule; Korean PM grades
- [x] Check that the status filter does not remove real peaks
- [x] Verify the timestamps against the Seoul Open API: KST, start of the hour
- [x] Document the 18 network-wide gap days and exclude them from denominators
- [x] Save `air_hourly.parquet` and `air_daily.parquet`

## Phase 3 - EDA (`02`, `03`, `04`)

- [x] Annual level against Korean and WHO references
- [x] Seasonality, weekday and hourly cycles
- [x] Variance decomposition, station offsets over time, official station history, level shifts
- [x] Replace the district ranking with a comparison of stations with intervals
- [ ] Ask the Seoul Research Institute of Public Health and Environment for month-level maintenance records
- [x] Pollutant correlations, episodes, coarse-dust days
- [ ] Optional: choropleth map with district boundaries (GeoJSON in `data/external`, `geopandas`)

## Phase 4 - Forecasting (`05`)

- [x] Leakage-safe features and strict temporal split (fit 2017-2018, test 2019)
- [x] Baselines (persistence, climatology), Ridge, gradient boosting; choice on validation folds
- [x] Validate on four quarterly origins of 2018, including the first quarter
- [x] Same rounding for grades and alerts; alert threshold calibrated on validation
- [x] Weekly block bootstrap intervals for MAE and recall against persistence
- [ ] A clean test on data from 2020 onward (2019 has been inspected)
- [ ] Optional: a classifier for "Bad or worse"
- [ ] Add KMA weather observations (wind speed and direction, rain, humidity) as features
- [ ] Optional: hourly forecast for the next 24 hours

## Phase 5 - Communication (`06`, README, optional app)

- [x] `06_insights_summary`: findings, recommendations and limitations for a non-technical reader
- [x] Forecast code in `src/seoul_air/forecast.py`, with tests
- [x] `run.py` for Windows without make, `constraints.txt`, MIT license
- [x] Test that the README figures match `reports/metrics`
- [ ] Korean summary reviewed by a native speaker if possible
- [ ] Optional: Streamlit dashboard (seasonal profile, next-day forecast)
- [ ] Final check: delete `data/processed`, run `python run.py all`, everything runs clean

## Phase 6 - Extended data, 2015-2025 (`07`)

- [x] Compare OA-2221, OA-15526 and the AirKorea final data: coverage, format, licence, final or provisional
- [x] Reproducible download with a check of the served file names; one schema for both Seoul files
- [x] Check the sources against each other (Kaggle = OA-15526; OA-2221 = OA-15526 one hour later) and against the AirKorea final data of 2024
- [x] Validate the annual means against official Seoul figures
- [ ] A personal Seoul Open API key to validate all 25 stations (the sample key returns five rows a year)
- [ ] Move notebooks 01-06 to the extended data (next phase)

## What makes it stand out to recruiters in Korea

- **A clear question with a local angle**: 미세먼지 (fine dust) is a daily topic in Korea; recruiters understand the problem immediately.
- **Korean standards, not only WHO**: the official Ministry of Environment grades (좋음 / 보통 / 나쁨 / 매우나쁨) show domain understanding.
- **Engineering, not only notebooks**: `src/` package, tests, CI, reproducible pipeline. Korean tech companies (Naver, Kakao, Coupang, Toss, LINE) value production habits.
- **Honest methodology**: status-based cleaning, temporal split, baselines, a test year used once, and stated limitations.
- **Bilingual README**: English for global teams, a short Korean summary for local HR.
- **A visible result in 30 seconds**: one headline chart and a few bullet points at the top of the README.
