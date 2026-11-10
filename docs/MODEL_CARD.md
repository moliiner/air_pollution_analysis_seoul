# Model card: Seoul PM2.5 forecasts

This card documents the two forecasts of the project: the **1-3 day forecast** of notebook 10 and the **2026-2028 outlook** of notebook 11. The earlier next-day forecast on the Kaggle data (notebook 05) is kept for reference only and is summarised at the end. Every figure below is checked against `reports/metrics/*_key_figures.json` by `tests/test_readme_numbers.py`.

## 1. Forecast of daily PM2.5 one to three days ahead (notebook 10)

### Model details
- **Output**: the city daily PM2.5 (mean of the daily means of the 25 urban stations of Seoul, ug/m3) for D+1, D+2 and D+3, issued at 17:00 KST of day D, the hour of the Korean forecast. Also a 10th, 50th and 90th percentile, and the probability of a Bad-or-worse day (rounded daily mean above 35 ug/m3, the Korean grade rule).
- **Model**: one ridge regression per horizon on log PM2.5 (penalty alpha 10, median imputation, standardised inputs). Quantiles: gradient boosting with the quantile loss, widened by conformal calibration on the validation years. Bad days: a gradient boosting classifier with a probability threshold chosen on the validation years (0.50 at D+1, 0.35 at D+2, 0.18 at D+3).
- **Code**: `src/seoul_air/multiday.py`, `nwp.py`, `regional.py`; tests in `tests/test_multiday.py`.

### Inputs (all known at 17:00 KST)
| Input | Source | Known at issue because |
|---|---|---|
| Hourly PM2.5, PM10, NO2, CO, O3 of the city | Seoul Open Data Plaza (OA-15526, OA-2221) | readings up to the hour 15:00-16:00 |
| Baengnyeong Island PM2.5 and PM10 | AirKorea final data | same hours (final data stand in for real-time readings) |
| Observed weather | ERA5 through Open-Meteo | same hours (stand-in for real-time observations) |
| Weather forecast of the target day | JMA GSM, Open-Meteo Previous Runs API | forecast made at least (k+1) x 24 hours before each target hour of D+k |
| Calendar of the target day | - | - |

A test changes every value after 15:00-16:00 of an issue day and checks that the inputs of that day do not change.

### Training and evaluation
- **Origins**: one per year; each year is forecast by models fit only on rows whose target day is before 1 January of that year. Models with JMA inputs are fit from 2019.
- **Validation (choices)**: 2020-2021. Inputs, model, penalty, quantile widening and alert thresholds come only from these years.
- **Test (scored once)**: 2022-2025.
- **References**: persistence (mean of the last 24 hours at issue time) and climatology (training mean within 15 days of the day of year).

### Test results, 2022-2025
| Horizon | MAE (ug/m3) | Persistence MAE | Skill vs persistence (95% interval) | Skill vs climatology | Grade accuracy |
|---|---|---|---|---|---|
| D+1 | 5.078 | 8.464 | 40.0% (36.6% to 43.0%) | 44.0% | 0.734 |
| D+2 | 6.004 | 10.553 | 43.1% (39.7% to 46.3%) | 33.8% | 0.666 |
| D+3 | 6.200 | 11.050 | 43.9% (40.6% to 47.1%) | 31.6% | 0.671 |

Intervals resample whole weeks. Without the JMA inputs the same model has a test MAE of 6.036, 7.580 and 7.860.

**Bad-or-worse days (122 in the test years), D+1**: the classifier has a POD of 0.516 and a FAR of 0.357 (CSI 0.401); persistence 0.352 and 0.650 (CSI 0.213); the 90th percentile rule 0.779 and 0.578. At D+2 and D+3 no alert reaches a CSI above 0.277.

**Uncertainty**: the 80% interval covers 0.850, 0.860 and 0.859 of the test days at D+1 to D+3 after calibration (0.664 to 0.684 before).

### Intended use and limits
- **Intended**: a research benchmark of what open data can do for a city-level PM2.5 forecast, and a baseline for comparison with operational forecasts.
- **Not intended**: public health warnings or decisions about individuals. It is not the official forecast, and it is not evaluated at district level.
- **Stand-ins**: ERA5 and the AirKorea final data replace the real-time observations; JMA forecasts are up to a day older than an operational forecaster's; no chemical transport model forecast is archived. CAMS (archived from August 2022 only) made the forecast worse and is not used.
- **Known weaknesses**: point forecasts are pulled toward the mean and miss many Bad days; alerts beyond D+1 are weak; the slight negative bias at D+2 and D+3 (-0.682 and -0.879 ug/m3).

## 2. Outlook for 2026-2028 (notebook 11)

- **Output**: monthly and annual city PM2.5 for 2026-2028 from an origin at the end of 2025, as simulated paths: median, 80% and 95% intervals, the chance that the annual mean rounds to 15 ug/m3 or less, and the expected Bad-or-worse days.
- **Candidates**: seasonal mean, ETS, damped trend, SARIMA, and a damped-trend model on the weather-normalised series of notebook 09 with the weather added back.
- **Evaluation**: 14 rolling origins every six months (2018-2024), up to 36 months ahead; MASE and interval coverage.
- **Selection rule, fixed in advance** (`longterm.SELECTION_RULE`): eligible if the 80% interval coverage is between 0.70 and 0.90; lowest mean MASE; a simpler model within 5% wins.
- **Chosen**: ETS (MASE 0.663, 80% coverage 0.835). Its annual mean was 1.78 ug/m3 too high on average three years ahead in the evaluation, while PM2.5 was falling.
- **Result**: annual median 17.43, 17.46 and 17.46 ug/m3; chance of meeting 15 ug/m3 of 0.09, 0.16 and 0.21; median Bad days 24, 23 and 24 a year.
- **Scenarios** (assumptions, not forecasts): if the weather-normalised decline of 2015-2025 continues, the median falls to 16.84 in 2028; if it stalls, it stays at 18.49.
- **Limits**: the outlook extends 2015-2025 and does **not anticipate shocks** (new policies, emission changes in Korea or China, pandemics, network changes, unusual weather years).

## 3. Earlier next-day forecast on the Kaggle data (notebook 05)

A district-level next-day forecast fit on 2017-2018 and evaluated on 2019 (7.97 vs 8.86 ug/m3 for persistence). 2019 had been inspected before its protocol was fixed, so it is an evaluation after inspection; notebook 10 supersedes it.

## Ethical considerations

Air quality forecasts influence behaviour. A missed Bad day exposes sensitive groups; a false alarm erodes trust. This card reports both POD and FAR so that a user can choose the alert that fits the cost of each error, and it states that the forecasts are not official warnings.
