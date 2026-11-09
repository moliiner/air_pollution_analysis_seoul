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
- A district value is the value of one station, and stations change: four were relocated in 2018 and most had equipment replaced in 2018-2019 (`data/reference/station_history.csv`, years only). Do not present a ranking of districts; compare stations on the same days, with intervals (notebook 03).
- 18 days of 2019 have no valid value for any station, so 1,077 of the 1,095 days are valid: use 1,077 as the denominator of city-day shares, leave the gaps missing and do not draw lines across them (see `reports/metrics/01_network_gap_days.csv`).

## Layout
- `notebooks/00`-`06`: the analysis of the Kaggle data, run in order. Notebook 01 writes `data/processed`, which the later notebooks read. Notebook 06 is the plain-language summary.
- `notebooks/07`: builds and validates the extended 2015-2025 data from the official Seoul files.
- `tools/`: one-off checks outside the pipeline (`compare_airkorea_final.py` needs `python-calamine` and a 400 MB download).
- `src/seoul_air/`: reusable code. Notebooks import from here instead of copying code: `data` (loading, cleaning, timestamps), `grades`, `episodes`, `station_levels`, `features`, `forecast` (folds, models, alert calibration, evaluation: `run_forecast`), `metrics`, `report` (key figures).
- `tests/`: pytest for everything in `src/`, plus `test_readme_numbers.py`, which checks every figure of the README's Key results against `reports/metrics/*_key_figures.json`.
- `reports/figures`, `reports/metrics`: outputs written by the notebooks. Each notebook 01-05 ends by saving its key figures with `save_key_figures`.
- `data/reference/`: small curated tables with a documented source (station history, Seoul Open API samples).
- `docs/ANALYSIS_PLAN.md`: the roadmap, phase by phase.

## Commands
- Use `run.py` (works on Windows without make): `python run.py install | lint | test | notebooks [NN] | all`.
- `install` uses `constraints.txt`, the exact versions that ran the project (Python 3.10). After changing dependencies, regenerate it from the environment and keep platform markers for Windows-only packages.
- `run.py` sets one thread per numerical library: the machine has little free memory, and notebooks 01 and 05 failed without it.
- When a result changes, update the README in the same change: `test_readme_numbers.py` fails otherwise.

## Rules
1. **Numbers**: never write a number in markdown that does not appear in an executed output. No placeholders and no values read by eye from charts.
2. **Verification**: before saying a task is done, run `python run.py lint` and `python run.py test`, and re-run the touched notebooks top to bottom in a fresh kernel (`python run.py notebooks NN`).
3. **Removing rows**: only with a documented reason and the exact count (use `drop_with_report`).
4. **Statistics**: pollutant concentrations are right-skewed; report medians and percentiles, not only means.
5. **Time**: Kaggle timestamps are KST (`Asia/Seoul`) and mark the **start** of each hourly average (07:00 = 07:00-08:00), verified in notebook 01. Official Korean data label the **end** of the hour (1-24 h, or 00:00 of the next day), one hour later: convert with `to_official_label` before joining any official or weather data.
6. **Modeling**: strict temporal split (never random); no feature may use information from after the prediction time; always compare to a persistence baseline. Settings, model choice and alert thresholds come only from the 2018 validation folds (four quarterly origins). 2019 has already been inspected: never use it to choose anything, and call it an evaluation after inspection, not an untouched test. A Bad-or-worse day is `is_bad` (rounded mean above 35), the same rule as the grade.
7. **Causality**: describe associations (seasons, pollutants, districts); do not claim causes the data cannot show.
8. **Order**: an "Interpretation" markdown goes after the code cell it interprets. Neutral analytical voice, no second person.
9. **Safety**: never edit `data/raw`. No personal paths (`C:\Users\...`) in notebooks. Do not commit or push unless explicitly asked. API keys only in `.env`.
