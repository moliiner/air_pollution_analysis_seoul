# Analysis Plan

Roadmap for the project, in the order the work should be done. Each phase ends with a checklist; do not start the next phase until the current one is checked.

## Business question

> **When and where is Seoul's air most harmful, what drives it, and can tomorrow's PM2.5 level be predicted well enough to warn residents?**

Sub-questions, one per notebook:

| # | Question | Notebook | Deliverable |
|---|---|---|---|
| 1 | Is the data complete and trustworthy? | `01_data_cleaning` | Cleaning table with rows dropped per step |
| 2 | How did PM2.5 / PM10 change over the years, seasons, weekdays and hours? | `02_eda_temporal` | Trend + seasonality charts, share of Bad days per year |
| 3 | Which districts are most exposed, and is that stable? | `03_eda_spatial` | Choropleth map, district ranking |
| 4 | What role do weather and dust episodes play? | `04_weather_and_episodes` | Episode table, weather effect charts |
| 5 | Is winter PM2.5 lower since the seasonal management system (Dec 2019)? | `05_policy_impact` | Weather-adjusted before/after estimate |
| 6 | Can next-day PM2.5 be forecast better than "same as today"? | `06_forecasting` | Model leaderboard vs persistence baseline |
| 7 | What should a citizen or the city take away? | `07_insights_summary` | 5-7 findings, recommendations, limitations |

## Phase 0 - Setup (day 1)

- [ ] Create a virtual environment and `make install`
- [ ] Copy `.env.example` to `.env` and add API keys (data.go.kr, data.seoul.go.kr)
- [ ] `make test` passes

## Phase 1 - Data acquisition (`00`)

- [ ] Choose the main dataset: hourly measurements per district, **at least 5 years** (so a trend and the 2019 policy can be studied)
- [ ] Download weather data (KMA, Seoul station) for the same period
- [ ] Download the district boundaries GeoJSON
- [ ] Fill in the inventory table of `data/README.md` (source, dataset ID, period, size, date)
- [ ] Check and write down the terms of use of each source

## Phase 2 - Cleaning (`01`)

- [ ] One tidy table: `datetime` (KST), `district`, `pm10`, `pm25`, `o3`, `no2`, `co`, `so2`
- [ ] Missing values per station and per month (heat map); decide: keep, interpolate short gaps (max 3 h) or drop
- [ ] Impossible values (negative, sensor error codes): drop with `drop_with_report`
- [ ] Hour 24 / timezone handled explicitly
- [ ] Add `pm25_grade` / `pm10_grade` with `seoul_air.grades.pm_grade`
- [ ] Save to `data/processed/air_hourly.parquet` and a daily version
- [ ] Move every reusable function to `src/seoul_air/` with a test

## Phase 3 - EDA (`02`, `03`, `04`)

- [ ] Every chart has a title, units (ug/m3), a source note and an "Interpretation" cell below it
- [ ] Medians and percentiles (data is right-skewed)
- [ ] Compare against the WHO 2021 guideline and the Korean standard, citing both
- [ ] Save the 4-6 best charts to `reports/figures/` for the README
- [ ] Episode detection: define a "Bad episode" (for example 2+ consecutive days with PM2.5 Bad) and count them per year and season

## Phase 4 - Policy impact (`05`)

- [ ] Periods: winters (Dec-Mar) before vs after Dec 2019
- [ ] Model PM2.5 from weather only on the "before" winters; predict the "after" winters; the gap is the weather-adjusted difference
- [ ] Discuss confounders: COVID-19 (2020), Chinese emission changes, long-term trend
- [ ] Wording: "associated with", never "caused"

## Phase 5 - Forecasting (`06`)

- [ ] Target: next-day mean PM2.5 per district (regression) and its grade (classification)
- [ ] Features known at prediction time only: lags (1, 2, 7 days), rolling means, calendar, weather forecast proxies
- [ ] Split by time: train up to 2023, validation 2024, test from 2025 (see `config.py`); test used **once**
- [ ] Baselines: persistence (tomorrow = today) and seasonal mean
- [ ] Models: Ridge, HistGradientBoosting (optional: LightGBM)
- [ ] Metrics: MAE, grade accuracy, **recall on Bad / Very bad days** (the costly mistake is missing a bad day)
- [ ] Save metrics to `reports/metrics/*.json` and a leaderboard chart

## Phase 6 - Communication (`07`, README, optional app)

- [ ] `07_insights_summary`: 5-7 findings written for a non-technical reader
- [ ] Fill in the README: key results with real numbers, 3-4 figures, how to reproduce
- [ ] Korean summary (한국어 요약) in the README, reviewed by a native speaker if possible
- [ ] Optional: Streamlit dashboard in `app/` (district selector, trend, forecast)
- [ ] Final check: `make all` runs clean from an empty `data/processed`

## What makes it stand out to recruiters in Korea

- **A clear question with a local angle**: 미세먼지 (fine dust) is a daily topic in Korea; recruiters understand the problem immediately.
- **Korean standards, not only WHO**: using the official Ministry of Environment grades (좋음 / 보통 / 나쁨 / 매우나쁨) shows domain understanding.
- **Engineering, not only notebooks**: `src/` package, tests, CI, reproducible `Makefile`. Korean tech companies (Naver, Kakao, Coupang, Toss, LINE) value production habits.
- **Honest methodology**: temporal split, baselines, a limitations section. This matters more than a high score.
- **Bilingual README**: English for global teams, a short Korean summary for local HR.
- **A visible result in 30 seconds**: one headline chart and 3 bullet points at the top of the README.
