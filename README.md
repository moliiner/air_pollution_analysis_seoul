# Seoul Air Quality: When and Where Is the Air Most Harmful?

> **Status: work in progress.** The sections marked _TBD_ are filled in as each phase of [docs/ANALYSIS_PLAN.md](docs/ANALYSIS_PLAN.md) is completed.

End-to-end data analysis of air pollution (PM2.5, PM10, O3, NO2) in the 25 districts of Seoul: data cleaning, temporal and spatial EDA, weather drivers, a weather-adjusted look at the PM seasonal management system, and a next-day PM2.5 forecast compared against a persistence baseline.

## Key results

_TBD: 3-5 bullet points with real numbers from the notebooks, and one headline figure._

<!-- ![Headline figure](reports/figures/xx_headline.png) -->

## Business question

When and where is Seoul's air most harmful, what drives it, and can tomorrow's PM2.5 level be predicted well enough to warn residents?

## Data

_TBD: sources, dataset IDs, period, size and terms of use. See [data/README.md](data/README.md)._

## Methodology

1. **Cleaning** ([01](notebooks/01_data_cleaning.ipynb)): tidy hourly table, documented row drops, Korean PM grades.
2. **Temporal EDA** ([02](notebooks/02_eda_temporal.ipynb)): trend, seasonality, weekly and daily cycles.
3. **Spatial EDA** ([03](notebooks/03_eda_spatial.ipynb)): district ranking and map.
4. **Weather and episodes** ([04](notebooks/04_weather_and_episodes.ipynb)): wind, rain and high-pollution episodes.
5. **Policy impact** ([05](notebooks/05_policy_impact.ipynb)): weather-adjusted comparison of winters before and after December 2019.
6. **Forecasting** ([06](notebooks/06_forecasting.ipynb)): strict temporal split, persistence baseline, linear and boosting models.
7. **Summary** ([07](notebooks/07_insights_summary.ipynb)): findings, recommendations and limitations.

## Project structure

```
├── data/                 # raw/ (never edited), external/, processed/  (not committed)
├── notebooks/            # 00-07, run in order
├── src/seoul_air/        # reusable code: config, loading, cleaning, PM grades
├── tests/                # pytest for src/
├── reports/              # figures/ and metrics/ written by the notebooks
├── docs/ANALYSIS_PLAN.md # roadmap and checklists
├── app/                  # optional Streamlit dashboard
├── Makefile              # install, test, lint, notebooks
└── requirements.txt
```

## How to reproduce

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
make install                    # or: pip install -r requirements.txt
cp .env.example .env            # add API keys
make test
make notebooks                  # runs 00-07 in order
```

## Limitations

_TBD._

## 한국어 요약

_TBD: 서울시 25개 자치구의 미세먼지(PM10)와 초미세먼지(PM2.5) 데이터를 분석하여, 언제 어디에서 대기질이 가장 나쁜지, 기상 요인의 영향, 미세먼지 계절관리제 전후 비교, 그리고 다음 날 PM2.5 예측 모델을 다룹니다. 주요 결과는 분석 완료 후 작성합니다._

## Tech stack

Python, pandas, NumPy, scikit-learn, statsmodels, Matplotlib, seaborn, pytest, GitHub Actions.
