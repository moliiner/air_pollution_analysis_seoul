"""Seoul air quality dashboard.

Reads only the files the notebooks wrote to reports/ (key figures and figures), so it runs
without downloading any data:

    pip install -r requirements-app.txt
    streamlit run app/streamlit_app.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "reports" / "metrics"
FIGURES = ROOT / "reports" / "figures"
YEARS = (2026, 2027, 2028)


@st.cache_data
def key_figures(notebook):
    return json.loads((METRICS / f"{notebook}_key_figures.json").read_text(encoding="utf-8"))


def by_year(mapping):
    return pd.Series({int(k): v for k, v in mapping.items()}).sort_index()


def overview(k02, k04, k10, k11):
    trend = k02["trend"]["pm25"]
    skill = k10["skill"]["D+1 | persistence"]
    outlook = k11["outlook"]
    cols = st.columns(4)
    cols[0].metric("PM2.5 trend, 2015-2025", f"{trend['pct_per_year']:.2f}% / year",
                   help=f"95% interval {trend['pct_low_95']:.2f}% to {trend['pct_high_95']:.2f}%")
    cols[1].metric("Hours in which ozone sets the CAI, 2025",
                   f"{k04['cai_main_pollutant_pct_by_year']['2025']['o3']:.1f}%",
                   f"{k04['cai_main_pollutant_pct_by_year']['2025']['o3'] - k04['cai_main_pollutant_pct_by_year']['2015']['o3']:+.1f} points since 2015",
                   delta_color="inverse")
    cols[2].metric("D+1 forecast error vs persistence", f"-{skill['skill_pct']:.1f}%",
                   help=f"95% interval {skill['low_95_pct']:.1f}% to {skill['high_95_pct']:.1f}% (test 2022-2025)")
    cols[3].metric("Chance of meeting 15 ug/m3 in 2028", f"{outlook['forecast: ETS | 2028']['p_meets_15']:.2f}")
    figure = FIGURES / "06_key_figure.png"
    if figure.exists():
        st.image(str(figure), width="stretch")


def trends(k02, k04):
    st.subheader("Annual PM2.5 and ozone")
    frame = pd.DataFrame({
        "PM2.5, mean station-day (ug/m3)": by_year(k02["pm25_mean_by_year"]),
        "Station-days above the 8-hour ozone standard (%)": by_year(k02["o3_above_8h_pct_by_year"]),
        "Hours in which ozone sets the CAI (%)": pd.Series({int(y): v["o3"] for y, v in k04["cai_main_pollutant_pct_by_year"].items()}),
    })
    choice = st.multiselect("Series", list(frame.columns), default=list(frame.columns)[:1])
    if choice:
        st.line_chart(frame[choice])
    rows = [{"pollutant": p.upper(), "change per year (%)": v["pct_per_year"], "low 95%": v["pct_low_95"],
             "high 95%": v["pct_high_95"]} for p, v in k02["trend"].items()]
    st.dataframe(pd.DataFrame(rows).set_index("pollutant").round(2))
    st.caption("Theil-Sen slope of deseasonalised monthly means; 95% interval from a 12-month block bootstrap (notebook 02).")


def policy(k09):
    st.subheader("PM seasonal management system (미세먼지 계절관리제)")
    seasons = pd.DataFrame(k09["seasons"]).T
    seasons.index = seasons.index.astype(int)
    st.bar_chart(seasons, stack=False)
    rows = []
    for case, values in k09["comparisons"].items():
        rows.append({"series | seasons": case, **{k: v for k, v in values.items() if "months" not in k}})
    st.dataframe(pd.DataFrame(rows).set_index("series | seasons").round(3))
    st.caption("Seasons are December-March, named by the year of their December; the system started in December 2019. "
               "A: before-after; B: gap from the earlier trend; C: difference in differences against April-November. "
               "Associations only (notebook 09).")


def forecast(k10):
    st.subheader("Daily PM2.5 one to three days ahead, issued at 17:00 KST (test 2022-2025)")
    rows = []
    for key, values in k10["test_scores"].items():
        horizon, name = key.split(" | ")
        rows.append({"horizon": horizon, "forecast": name, "MAE": values["mae"], "RMSE": values["rmse"],
                     "bias": values["bias"], "grade accuracy": values["grade_accuracy"]})
    table = pd.DataFrame(rows)
    horizon = st.radio("Horizon", sorted(table["horizon"].unique()), horizontal=True)
    st.dataframe(table[table["horizon"] == horizon].drop(columns="horizon").set_index("forecast").round(3))
    alerts = pd.DataFrame([{"alert": key.split(" | ")[1], **values} for key, values in k10["alerts"].items()
                           if key.startswith(horizon)]).set_index("alert")
    st.markdown("**Bad-or-worse days**: POD = share of Bad days with an alert, FAR = share of alerts that were wrong.")
    st.dataframe(alerts[["bad_days", "alerts", "pod", "far", "csi"]].round(3))
    figure = FIGURES / "10_forecast_by_horizon.png"
    if figure.exists():
        st.image(str(figure), width="stretch")


def outlook(k11):
    st.subheader("Monthly and annual PM2.5, 2026-2028")
    st.warning("These numbers extend 2015-2025. They do not anticipate shocks: new policies, emission changes in "
               "Korea or China, pandemics or unusual weather years.")
    series = sorted({key.split(" | ")[0] for key in k11["outlook"]})
    chosen = st.selectbox("Forecast or scenario", series, index=series.index(f"forecast: {k11['chosen_model']}"))
    rows = [{"year": y, **k11["outlook"][f"{chosen} | {y}"]} for y in YEARS]
    table = pd.DataFrame(rows).set_index("year")
    table.columns = ["annual median", "annual low 80%", "annual high 80%", "P(meets 15 ug/m3)",
                     "Bad days, median", "Bad days, low 80%", "Bad days, high 80%"]
    st.dataframe(table.round(2))
    if chosen.startswith("scenario"):
        st.info("A scenario states an assumption about the trend; it is not a forecast of which trend will happen.")
    backtest = pd.DataFrame(k11["backtest"]).T[["mase", "coverage_80", "coverage_95"]]
    st.markdown(f"**Model choice** (rule fixed in advance): {k11['selection_rule']}")
    st.dataframe(backtest.round(3))
    figure = FIGURES / "11_outlook.png"
    if figure.exists():
        st.image(str(figure), width="stretch")


def main():
    st.set_page_config(page_title="Seoul air quality", layout="wide")
    st.title("Seoul air quality, 2015-2025")
    st.caption("Official hourly readings of the 25 urban stations of Seoul. Source code and notebooks: "
               "github.com/moliiner/air_pollution_analysis_seoul")
    k02, k04, k09, k10, k11 = (key_figures(nb) for nb in ["02", "04", "09", "10", "11"])
    tabs = st.tabs(["Overview", "Trends and ozone", "Seasonal management system", "Forecast 1-3 days", "Outlook 2026-2028"])
    with tabs[0]:
        overview(k02, k04, k10, k11)
    with tabs[1]:
        trends(k02, k04)
    with tabs[2]:
        policy(k09)
    with tabs[3]:
        forecast(k10)
    with tabs[4]:
        outlook(k11)


main()
