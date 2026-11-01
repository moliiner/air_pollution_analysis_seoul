# Seoul Air Quality Analysis

Portfolio project: analysis of air pollution (PM2.5, PM10, O3, NO2) in the 25 districts of Seoul. It is meant to be read by tech recruiters in South Korea, so it must look professional: a clear business question, reproducible code, tested helpers, and conclusions that match the data.

## Language
- Repository content (notebooks, code comments, markdown, plot titles, README): **English**. The README also has a short Korean summary.
- Chat replies to the user: **Spanish**, concise.

## Layout
- `notebooks/00`-`07`: the analysis, run in order. Each one reads `data/processed` written by an earlier one.
- `src/seoul_air/`: reusable code (loading, cleaning, grades, features, models). Notebooks import from here instead of copying code.
- `tests/`: pytest for everything in `src/`.
- `reports/figures`, `reports/metrics`: outputs written by the notebooks.
- `docs/ANALYSIS_PLAN.md`: the roadmap, phase by phase.

## Rules
1. **Numbers**: never write a number in markdown that does not appear in an executed output. No placeholders and no values read by eye from charts.
2. **Verification**: before saying a task is done, run `make test` and re-run the touched notebooks top to bottom in a fresh kernel.
3. **Removing rows**: only with a documented reason and the exact count (use `drop_with_report`).
4. **Statistics**: pollutant concentrations are right-skewed; report medians and percentiles, not only means.
5. **Time**: timestamps are KST (`Asia/Seoul`). Some sources publish hour 24 for midnight; convert it explicitly.
6. **Modeling**: strict temporal split (never random); no feature may use information from after the prediction time; always compare to a persistence baseline.
7. **Causality**: the policy notebook estimates an association adjusted for weather, not a proven causal effect. Say so.
8. **Order**: an "Interpretation" markdown goes after the code cell it interprets. Neutral analytical voice, no second person.
9. **Safety**: never edit `data/raw`. No personal paths (`C:\Users\...`) in notebooks. Do not commit or push unless explicitly asked. API keys only in `.env`.
