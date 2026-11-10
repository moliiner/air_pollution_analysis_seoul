# Seoul Air Quality Analysis

Portfolio project: analysis of air pollution (PM2.5, PM10, O3, NO2) in the 25 districts of Seoul. It is meant to be read by tech recruiters in South Korea, so it must look professional: a clear business question, reproducible code, tested helpers, and conclusions that match the data.

## Language
- Repository content (notebooks, code comments, markdown, plot titles, README): **English**. The README also has a short Korean summary.
- Chat replies to the user: **Spanish**, concise.

## Dataset facts
- Kaggle "Air Pollution in Seoul" (bappekim): hourly readings, 25 stations (one per district), 6 pollutants, 2017-01-01 to 2019-12-31. No weather variables. It is a copy of the Seoul file OA-15526, with 18 days of 2019 missing that the official file has.
- Extended data 2015-2025 (notebook 07, `seoul_air.sources`): OA-15526 for 2015-2022 (start-of-hour labels, instrument status) and OA-2221 for 2023-2025 (end-of-hour labels moved back one hour; no status, flagged readings already blank). Both are provisional; for PM they equal the AirKorea final data of 2024, and the annual means reproduce the official Seoul figures (`reference/official_annual_means.csv`). New analyses should use `air_hourly_2015_2025.parquet` / `air_daily_2015_2025.parquet`.
- `Measurement_info.csv` is the source used: it has the instrument status (only 0 = normal is valid). `Measurement_summary.csv` has no status and keeps instrument errors (PM2.5 above 500 ug/m3); do not use it for analysis.
- Units: PM10 and PM2.5 in ug/m3; SO2, NO2, CO and O3 in ppm.
- Weather (`seoul_air.weather`): ERA5 at one grid point, UTC converted to start-of-hour KST; precipitation of hour h is the ERA5 total reported at h+1. The boundary layer height is missing for 2024-01 to 2024-06. **Observed weather never enters a forecast for its own day**: use `weather_known_at_issue` (issue day and earlier) or a weather forecast.
- The 25 stations are all urban (도시대기). Seoul's 15 roadside stations (도로변대기) are only in the AirKorea final data; `reference/seoul_stations_by_network_2024.csv` has their 2024 means. Keep the two networks apart.
- CAI: official definition in `seoul_air.cai` (PM uses the 24-hour predicted moving average; +50 / +75 bonus). A daily CAI in this project is the highest hourly CAI of the day, not an official daily statistic.
- A district value is the value of one station, and stations change: four were relocated in 2018 and most had equipment replaced in 2018-2019 (`data/reference/station_history.csv`, years only). Do not present a ranking of districts; compare stations on the same days, with intervals (notebook 03).
- 18 days of 2019 have no valid value for any station, so 1,077 of the 1,095 days are valid: use 1,077 as the denominator of city-day shares, leave the gaps missing and do not draw lines across them (see `reports/metrics/01_network_gap_days.csv`).

## Layout
- Notebooks are numbered by topic; `run.py` runs them in dependency order: 00-01 (Kaggle data, cleaning and timestamp checks) -> 07 (official data 2015-2025) -> 08 (weather) -> 02-04 (analyses of 2015-2025) -> 09 (weather normalisation, seasonal management system) -> 10 (1-3 day forecast on 2015-2025) -> 11 (monthly and annual outlook 2026-2028) -> 05 (earlier next-day forecast on the Kaggle data) -> 06 (plain-language summary).
- `notebooks/07`: builds and validates the extended 2015-2025 data from the official Seoul files.
- `notebooks/08`: hourly weather 2015-2025 (ERA5 via Open-Meteo, checked against the Seoul station) joined with the pollution data.
- `notebooks/09`: weather-normalised PM2.5 (gradient boosting) and comparisons of the seasons of the PM seasonal management system (since December 2019); associations only, there is no untreated comparison region.
- `notebooks/10`: 1-3 day city PM2.5 forecast issued at 17:00 KST (`multiday`, `nwp`, `regional`): validation years 2020-2021, test years 2022-2025 with yearly origins, against persistence and climatology.
- `notebooks/11`: outlook for 2026-2028 (`longterm`): five monthly models, rolling origins every 6 months from 2018-01 up to 36 months, model chosen by `longterm.SELECTION_RULE` (fixed in advance, do not change it after seeing results), labelled scenarios; no shocks anticipated.
- `tools/`: one-off checks outside the pipeline (`compare_airkorea_final.py` needs `python-calamine` and a 400 MB download).
- `src/seoul_air/`: reusable code. Notebooks import from here instead of copying code: `data` (loading, cleaning, timestamps), `grades`, `episodes`, `station_levels`, `features`, `forecast` (folds, models, alert calibration, evaluation: `run_forecast`), `metrics`, `report` (key figures), `sources` (official Seoul files), `weather`, `trend` (Theil-Sen slope with a block-bootstrap interval), `ozone` (8-hour means, standards), `cai` (official Korean index), `population` (MOIS district population, weighted means), `deweather` (weather normalisation), `policy` (season comparisons), `multiday` (issue-time features, origins, scores), `nwp` (archived JMA forecasts), `regional` (AirKorea background stations, CAMS), `longterm` (monthly models, selection rule, scenarios, Bad days).
- `tests/`: pytest for everything in `src/`, plus `test_readme_numbers.py`, which checks every figure of the README (executive summary, Key results, Korean summary) and of `docs/MODEL_CARD.md` against `reports/metrics/*_key_figures.json`, and `test_app.py` (the dashboard; skipped where Streamlit is not installed, run in CI).
- `reports/figures`, `reports/metrics`: outputs written by the notebooks. Each notebook 01-05 ends by saving its key figures with `save_key_figures`.
- `data/reference/`: small curated tables with a documented source (station history, Seoul Open API samples).
- `docs/ANALYSIS_PLAN.md`: the roadmap, phase by phase. `docs/MODEL_CARD.md`: the forecasts of notebooks 10 and 11.
- `app/streamlit_app.py`: dashboard that reads only `reports/` (`requirements-app.txt`, not part of `constraints.txt`).
- `notebooks/06`: plain-language summary of every notebook; it writes `reports/figures/06_key_figure.png`, the figure of the README.

## Commands
- Use `run.py` (works on Windows without make): `python run.py install | lint | test | notebooks [NN] | all`.
- `install` uses `constraints.txt`, the exact versions that ran the project (Python 3.10). After changing dependencies, regenerate it from the environment and keep platform markers for Windows-only packages.
- `run.py` sets one thread per numerical library: the machine has little free memory, and notebooks 01 and 05 failed without it.
- When a result changes, update the README, notebook 06 and the model card in the same change: `test_readme_numbers.py` fails otherwise.

## Rules
1. **Numbers**: never write a number in markdown that does not appear in an executed output. No placeholders and no values read by eye from charts.
2. **Verification**: before saying a task is done, run `python run.py lint` and `python run.py test`, and re-run the touched notebooks top to bottom in a fresh kernel (`python run.py notebooks NN`).
3. **Removing rows**: only with a documented reason and the exact count (use `drop_with_report`).
4. **Statistics**: pollutant concentrations are right-skewed; report medians and percentiles, not only means.
5. **Time**: Kaggle timestamps are KST (`Asia/Seoul`) and mark the **start** of each hourly average (07:00 = 07:00-08:00), verified in notebook 01. Official Korean data label the **end** of the hour (1-24 h, or 00:00 of the next day), one hour later: convert with `to_official_label` before joining any official or weather data.
6. **Modeling**: strict temporal split (never random); no feature may use information from after the prediction time; always compare to a persistence baseline. Notebook 10 (17:00 KST issue): inputs only up to the hour 15:00-16:00 of the issue day, JMA forecasts `previous_day(k+1)` for day D+k, CAMS up to 08:00; choices only from the validation years 2020-2021, test 2022-2025 scored once. Notebook 05 (Kaggle): settings, model choice and alert thresholds come only from the 2018 validation folds (four quarterly origins). 2019 has already been inspected: never use it to choose anything, and call it an evaluation after inspection, not an untouched test. A Bad-or-worse day is `is_bad` (rounded mean above 35), the same rule as the grade.
7. **Causality**: describe associations (seasons, pollutants, districts); do not claim causes the data cannot show.
8. **Order**: an "Interpretation" markdown goes after the code cell it interprets. Neutral analytical voice, no second person.
9. **Safety**: never edit `data/raw`. No personal paths (`C:\Users\...`) in notebooks. Do not commit or push unless explicitly asked. API keys only in `.env`.
