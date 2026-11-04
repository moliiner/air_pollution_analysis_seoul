# Analysis Plan

Roadmap for the project, in the order the work should be done. Each phase ends with a checklist.

## Business question

> **When and where is Seoul's air most harmful, what drives it, and can tomorrow's PM2.5 level be predicted well enough to warn residents?**

Dataset: Kaggle *Air Pollution in Seoul*, hourly, 25 district stations, 2017-2019 (see `data/README.md`).

| # | Question | Notebook | Status |
|---|---|---|---|
| 1 | Is the data complete and trustworthy? | `01_data_cleaning` | Done |
| 2 | How do PM2.5 / PM10 vary by year, season, weekday and hour? | `02_eda_temporal` | Done |
| 3 | Which districts are most exposed, and is that stable? | `03_eda_spatial` | Done |
| 4 | How do pollutants relate, and when do episodes happen? | `04_pollutants_and_episodes` | Done |
| 5 | Can next-day PM2.5 be forecast better than "same as today"? | `05_forecasting` | Done (first version) |
| 6 | What should a citizen or the city take away? | `06_insights_summary` | To do |

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
- [x] Document the 18 network-wide gap days and exclude them from denominators
- [x] Save `air_hourly.parquet` and `air_daily.parquet`

## Phase 3 - EDA (`02`, `03`, `04`)

- [x] Annual level against Korean and WHO references
- [x] Seasonality, weekday and hourly cycles
- [x] District ranking, stability across years, variance decomposition
- [x] Pollutant correlations, episodes, coarse-dust days
- [ ] Optional: choropleth map with district boundaries (GeoJSON in `data/external`, `geopandas`)

## Phase 4 - Forecasting (`05`)

- [x] Leakage-safe features and strict temporal split (fit 2017-2018, test 2019)
- [x] Baselines (persistence, climatology), Ridge, gradient boosting; choice on validation folds
- [ ] Improve the Bad-day recall: lower decision threshold chosen on the validation folds, or a classifier for "Bad or worse"
- [ ] Add KMA weather observations (wind speed and direction, rain, humidity) as features
- [ ] Optional: hourly forecast for the next 24 hours

## Phase 5 - Communication (`06`, README, optional app)

- [ ] `06_insights_summary`: 5-7 findings written for a non-technical reader
- [ ] README key results reviewed after any change to the notebooks
- [ ] Korean summary reviewed by a native speaker if possible
- [ ] Optional: Streamlit dashboard in `app/` (district selector, seasonal profile, next-day forecast)
- [ ] Final check: delete `data/processed`, run `make notebooks`, everything runs clean

## What makes it stand out to recruiters in Korea

- **A clear question with a local angle**: 미세먼지 (fine dust) is a daily topic in Korea; recruiters understand the problem immediately.
- **Korean standards, not only WHO**: the official Ministry of Environment grades (좋음 / 보통 / 나쁨 / 매우나쁨) show domain understanding.
- **Engineering, not only notebooks**: `src/` package, tests, CI, reproducible pipeline. Korean tech companies (Naver, Kakao, Coupang, Toss, LINE) value production habits.
- **Honest methodology**: status-based cleaning, temporal split, baselines, a test year used once, and stated limitations.
- **Bilingual README**: English for global teams, a short Korean summary for local HR.
- **A visible result in 30 seconds**: one headline chart and a few bullet points at the top of the README.
