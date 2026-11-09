# Seoul Air Quality Analysis

Portfolio project: analysis of air pollution (PM2.5, PM10, O3, NO2) in the 25 districts of Seoul. It is meant to be read by tech recruiters in South Korea, so it must look professional: a clear business question, reproducible code, tested helpers, and conclusions that match the data.

## Language
- Repository content (notebooks, code comments, markdown, plot titles, README): **English**. The README also has a short Korean summary.
- Chat replies to the user: **Spanish**, concise.

## Dataset facts
- Kaggle "Air Pollution in Seoul" (bappekim): hourly readings, 25 stations (one per district), 6 pollutants, 2017-01-01 to 2019-12-31. No weather variables.
- `Measurement_info.csv` is the source used: it has the instrument status (only 0 = normal is valid). `Measurement_summary.csv` has no status and keeps instrument errors (PM2.5 above 500 ug/m3); do not use it for analysis.
- Units: PM10 and PM2.5 in ug/m3; SO2, NO2, CO and O3 in ppm.
- A district value is the value of one station, and stations change: four were relocated in 2018 and most had equipment replaced in 2018-2019 (`data/reference/station_history.csv`, years only). Do not present a ranking of districts; compare stations on the same days, with intervals (notebook 03).
- 18 days of 2019 have no valid value for any station, so 1,077 of the 1,095 days are valid: use 1,077 as the denominator of city-day shares, leave the gaps missing and do not draw lines across them (see `reports/metrics/01_network_gap_days.csv`).

## Layout
- `notebooks/00`-`06`: the analysis, run in order. Notebook 01 writes `data/processed`, which the later notebooks read.
- `src/seoul_air/`: reusable code (loading, cleaning, grades, features, models). Notebooks import from here instead of copying code.
- `tests/`: pytest for everything in `src/`.
- `reports/figures`, `reports/metrics`: outputs written by the notebooks.
- `docs/ANALYSIS_PLAN.md`: the roadmap, phase by phase.

## Rules
1. **Numbers**: never write a number in markdown that does not appear in an executed output. No placeholders and no values read by eye from charts.
2. **Verification**: before saying a task is done, run `make test` and re-run the touched notebooks top to bottom in a fresh kernel.
3. **Removing rows**: only with a documented reason and the exact count (use `drop_with_report`).
4. **Statistics**: pollutant concentrations are right-skewed; report medians and percentiles, not only means.
5. **Time**: Kaggle timestamps are KST (`Asia/Seoul`) and mark the **start** of each hourly average (07:00 = 07:00-08:00), verified in notebook 01. Official Korean data label the **end** of the hour (1-24 h, or 00:00 of the next day), one hour later: convert with `to_official_label` before joining any official or weather data.
6. **Modeling**: strict temporal split (never random); no feature may use information from after the prediction time; always compare to a persistence baseline.
7. **Causality**: describe associations (seasons, pollutants, districts); do not claim causes the data cannot show.
8. **Order**: an "Interpretation" markdown goes after the code cell it interprets. Neutral analytical voice, no second person.
9. **Safety**: never edit `data/raw`. No personal paths (`C:\Users\...`) in notebooks. Do not commit or push unless explicitly asked. API keys only in `.env`.
