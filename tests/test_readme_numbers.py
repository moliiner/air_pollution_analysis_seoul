"""The figures quoted in the README must match the files the notebooks wrote.

If a notebook changes a result, this test fails until the README is updated.
"""
import pandas as pd
import pytest

from seoul_air import config
from seoul_air.report import load_key_figures

README = (config.ROOT / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def k():
    return {nb: load_key_figures(nb) for nb in ["01", "02", "03", "04", "05", "07", "08", "09", "10", "11"]}


def quoted(text):
    assert text in README, f"README does not contain: {text!r}"


def test_data_quality(k):
    f = k["01"]
    quoted(f"{f['dropped_pct']:.2f}% of the readings carry a non-normal instrument status")
    quoted(f"all {f['summary_pm25_above_500']:,} PM2.5 readings above 500 ug/m3")
    quoted(f"changes the grade of {f['filter_check_grade_changes']} of {f['filter_check_station_days']:,} station-days")
    quoted(f"no daily value on {f['gap_days']} days of 2019, including {f['longest_gap_days']} in a row")
    quoted(f"the analysis uses {f['valid_city_days']:,} valid days")


def test_level_and_trend(k):
    f = k["02"]
    year = f["pm25_mean_by_year"]
    quoted(f"from {year['2016']:.1f} ug/m3 in 2016 to {year['2024']:.1f} in 2024 ({year['2025']:.1f} in 2025)")
    pm25 = f["trend"]["pm25"]
    quoted(f"trend is {pm25['pct_per_year']:.2f}% per year (95% interval {pm25['pct_low_95']:.2f}% "
           f"to {pm25['pct_high_95']:.2f}%")
    quoted(f"and all {f['stations_with_significant_pm25_decline']} stations decline")
    assert f["stations_with_significant_pm25_decline"] == 25
    quoted(f"NO2 ({f['trend']['no2']['pct_per_year']:.2f}% a year) and SO2 ({f['trend']['so2']['pct_per_year']:.2f}%)")
    o3 = f["trend"]["o3"]
    quoted(f"O3 rises by {o3['pct_per_year']:.2f}% a year (interval {o3['pct_low_95']:.2f}% to {o3['pct_high_95']:.2f}%)")
    above = f["o3_above_8h_pct_by_year"]
    quoted(f"from {above['2015']:.1f}% in 2015 to {above['2024']:.1f}% in 2024")
    main = k["04"]["cai_main_pollutant_pct_by_year"]
    quoted(f"in {main['2025']['o3']:.1f}% of the station-hours of 2025, against {main['2015']['o3']:.1f}% in 2015")
    quoted(f"연 {abs(pm25['pct_per_year']):.2f}%씩 감소")
    quoted(f"오존은 연 {o3['pct_per_year']:.2f}%씩 증가")


def test_seasons(k):
    month, bad = k["02"]["pm25_median_by_month"], k["02"]["bad_or_worse_pct_by_month"]
    quoted(f"peaks in March ({month['3']:.1f} ug/m3) and is lowest in September ({month['9']:.1f})")
    quoted(f"in March {bad['3']:.1f}% of station-days are graded Bad or Very bad, against {bad['8']:.1f}% in August")
    episodes = k["04"]["episodes_by_year"]
    quoted(f"episodes fell from {episodes['2016']} in 2016 to {episodes['2024']} in 2024")


def test_districts_exposure_and_roadside(k):
    f = k["03"]
    share = f["variance_share_pct"]
    quoted(f"The day accounts for {share['Date (each single day)']:.1f}% of the variance of station-day PM2.5, "
           f"the calendar month for {share['Calendar month (season)']:.1f}% and the district for {share['District']:.1f}%")
    quoted(f"within {f['median_gap_between_district_medians']:.1f} ug/m3 of each other")
    quoted(f"(Spearman between years: median {f['spearman_between_years'][1]:.2f})")
    groups = f["categories"]
    consistent = groups.get("Above the rest of the city", 0) + groups.get("Below the rest of the city", 0)
    quoted(f"{groups['Not comparable']} of the 25 stations were relocated or show a level shift, and only {consistent} keep")
    quoted(f"by at most {f['exposure_pm25_max_abs_difference']:.3f} ug/m3")
    quoted(f"the {f['roadside_stations']} roadside stations of Seoul recorded {f['roadside_vs_urban_pct_2024']['no2']:.1f}% more NO2")
    quoted(f"날짜가 차지하는 비중은 {share['Date (each single day)']:.1f}%, 자치구는 {share['District']:.1f}%")


def test_forecast(k):
    f = k["05"]
    model = f["selected_model"]
    assert model == "ridge"  # the README names the model
    quoted(f"MAE {f['skill_vs_persistence_pct']:.1f}% lower than")
    quoted(f"({f['mae'][model]:.2f} vs {f['mae']['persistence']:.2f} ug/m3")
    low, high = f["skill_interval_pct"]
    quoted(f"95% interval of the gain {low:.1f}% to {high:.1f}%")
    quoted(f"(recall {f['recall_grade_rule'][model]:.2f} vs {f['recall_grade_rule']['persistence']:.2f})")
    quoted(f"calibrated on 2018 ({f['threshold'][model]:g} ug/m3) its recall rises to {f['recall_calibrated'][model]:.2f}")
    quoted(f"(MAE)를 {f['skill_vs_persistence_pct']:.1f}% 줄였습니다")


def test_key_figures_agree_with_the_other_metric_files(k):
    leaderboard = pd.read_csv(config.METRICS / "05_leaderboard.csv", index_col="model")
    assert k["05"]["mae"]["ridge"] == pytest.approx(leaderboard.loc["ridge", "mae"])
    gaps = pd.read_csv(config.METRICS / "01_network_gap_days.csv")
    assert len(gaps) == k["01"]["gap_days"]
    comparison = pd.read_csv(config.METRICS / "03_station_comparison.csv")
    assert comparison["category"].value_counts().to_dict() == k["03"]["categories"]


def test_extended_data(k):
    f = k["07"]
    quoted(f"matches {f['station_identical_pct']:.1f}% of {f['station_years_compared']} official station-year means "
           f"exactly after rounding and {f['station_within_1_pct']:.1f}% within 1 ug/m3")
    quoted(f"its whole-Seoul PM2.5 mean for 2024 is {f['city_pm25_by_year']['2024']:.2f} ug/m3 "
           f"against the official {f['city_official']['2024_pm25']:g}")
    quoted(f"서울시 공식 연평균과 대조해 검증했고(2024년 PM2.5: {f['city_pm25_by_year']['2024']:.2f} 대 공식 "
           f"{f['city_official']['2024_pm25']:g}")


def test_weather(k):
    f = k["08"]
    check = f["hourly_check"]
    quoted(f"follows the Seoul station closely for temperature (correlation {check['temperature_c']['correlation']:.3f}) "
           f"and less for wind speed ({check['wind_speed_ms']['correlation']:.3f})")
    rho = f["spearman_all_days"]
    quoted(f"strongest for the boundary layer height (Spearman {rho['boundary_layer_height_mean_m']:.2f}) "
           f"and wind speed ({rho['wind_speed_mean_ms']:.2f})")


def test_weather_normalisation_and_policy(k):
    f = k["09"]
    loyo = f["validation"][f"{f['chosen_settings']} | leave one year out"]
    base = f["validation"]["date only | leave one year out"]
    quoted(f"explains daily PM2.5 with R2 {loyo['r2']:.3f} ({base['r2']:.3f} with the date alone)")
    norm = f["trend"]["weather-normalised"]
    quoted(f"the trend is {norm['pct_per_year']:.2f}% per year (95% interval {norm['pct_low_95']:.2f}% "
           f"to {norm['pct_high_95']:.2f}%)")
    main = f["comparisons"]["normalised | all seasons"]
    quoted(f"is {abs(main['A before-after (ug/m3)']):.2f} ug/m3 lower than in the four before")
    quoted(f"and {abs(main['B gap from trend (ug/m3)']):.2f} ug/m3 below the earlier trend "
           f"(interval {main['B low 95']:.2f} to {main['B high 95']:.2f})")
    assert main["B high 95"] < 0
    quoted(f"(difference in differences {main['C diff-in-diff (ug/m3)']:.2f} ug/m3, p = {main['C p-value']:.3f})")
    covid = f["comparisons"]["normalised | without 2019-2020"]
    assert covid["B low 95"] < 0 < covid["B high 95"]  # "loses its significance without the COVID-19 seasons"
    regional = f["regional_trends"]
    quoted(f"({regional['seoul']['pct_per_year']:.2f}% against {regional['baengnyeong']['pct_per_year']:.2f}% a year)")
    quoted(f"이전보다 {abs(main['A before-after (ug/m3)']):.2f}㎍/㎥ 낮았지만")


def test_multiday_forecast(k):
    f = k["10"]
    assert {row["model"] for row in f["chosen"]} == {"ridge, alpha 10"}  # the README names the model
    chosen = "chosen: ridge, alpha 10, + Baengnyeong + JMA forecast"
    mae = [f["test_scores"][f"D+{h} | {chosen}"]["mae"] for h in (1, 2, 3)]
    quoted(f"of {mae[0]:.3f}, {mae[1]:.3f} and {mae[2]:.3f} ug/m3 at D+1, D+2 and D+3")
    skill = f["skill"]["D+1 | persistence"]
    quoted(f"{skill['skill_pct']:.1f}% lower than persistence at D+1 (95% interval {skill['low_95_pct']:.1f}% "
           f"to {skill['high_95_pct']:.1f}%)")
    quoted(f"and {f['skill']['D+1 | climatology']['skill_pct']:.1f}% lower than climatology")
    quoted(f"Without the weather forecast the D+1 MAE is {f['test_scores']['D+1 | same model, + Baengnyeong']['mae']:.3f}")
    assert all(row["skill_pct"] < 0 for row in f["cams"].values())  # "CAMS makes it worse"
    alert = f["alerts"][f"D+1 | classifier (p >= {f['classifier_thresholds']['1']:.2f})"]
    persistence = f["alerts"]["D+1 | persistence (grade rule)"]
    quoted(f"a classifier has a POD of {alert['pod']:.3f} and a FAR of {alert['far']:.3f}, against "
           f"{persistence['pod']:.3f} and {persistence['far']:.3f} for persistence")
    quoted(f"a calibrated 80% interval covers {f['quantiles']['D+1 | test']['calibrated_coverage']:.3f} of the test days")
    quoted(f"내일(D+1) 예보의 MAE를 지속성 기준보다 {skill['skill_pct']:.1f}% 줄였습니다")


def test_long_term_outlook(k):
    f = k["11"]
    assert f["chosen_model"] == "ETS" and f["chosen_among_eligible"]
    ets = f["backtest"]["ETS"]
    quoted(f"chose ETS (MASE {ets['mase']:.3f}, 80% interval coverage {ets['coverage_80']:.3f})")
    quoted(f"did not do better ({f['backtest']['deweathered (ML)']['mase']:.3f})")
    y2026, y2028 = f["outlook"]["forecast: ETS | 2026"], f["outlook"]["forecast: ETS | 2028"]
    quoted(f"(median {y2028['annual_median']:.2f} in 2028, 80% interval {y2028['annual_low_80']:.1f}-{y2028['annual_high_80']:.2f})")
    quoted(f"is {y2026['p_meets_15']:.2f} in 2026 and {y2028['p_meets_15']:.2f} in 2028")
    continues = max(f["outlook"][f"scenario A: decline continues | {y}"]["p_meets_15"] for y in (2026, 2027, 2028))
    quoted(f"it stays at most {continues:.2f}")
    quoted(f"2026년 {y2026['p_meets_15']:.2f}, 2028년 {y2028['p_meets_15']:.2f}")


def test_executive_summary(k):
    year, pm25 = k["02"]["pm25_mean_by_year"], k["02"]["trend"]["pm25"]
    normalised = k["09"]["trend"]["weather-normalised"]
    outlook = k["11"]["outlook"]
    quoted(f"from {year['2016']:.1f} ug/m3 in 2016 to {year['2024']:.1f} in 2024, a trend of "
           f"{pm25['pct_per_year']:.2f}% per year that holds once the weather is removed "
           f"({normalised['pct_per_year']:.2f}% per year)")
    quoted(f"the forecast annual mean is {outlook['forecast: ETS | 2026']['annual_median']:.2f} ug/m3 in 2026, "
           f"with a chance of meeting the standard of {outlook['forecast: ETS | 2026']['p_meets_15']:.2f} in 2026 "
           f"and {outlook['forecast: ETS | 2028']['p_meets_15']:.2f} in 2028")
    quoted(f"sets the air quality index in {k['04']['cai_main_pollutant_pct_by_year']['2025']['o3']:.1f}% "
           f"of the station-hours of 2025")
    quoted(f"cuts the next-day error by {k['10']['skill']['D+1 | persistence']['skill_pct']:.1f}% against persistence")


MODEL_CARD = (config.ROOT / "docs" / "MODEL_CARD.md").read_text(encoding="utf-8")


def in_card(text):
    assert text in MODEL_CARD, f"MODEL_CARD.md does not contain: {text!r}"


def test_model_card(k):
    f = k["10"]
    chosen = "chosen: ridge, alpha 10, + Baengnyeong + JMA forecast"
    thresholds = f["classifier_thresholds"]
    in_card(f"({thresholds['1']:.2f} at D+1, {thresholds['2']:.2f} at D+2, {thresholds['3']:.2f} at D+3)")
    for h in (1, 2, 3):
        s = f["test_scores"][f"D+{h} | {chosen}"]
        p = f["test_scores"][f"D+{h} | persistence"]
        sk, sc = f["skill"][f"D+{h} | persistence"], f["skill"][f"D+{h} | climatology"]
        in_card(f"| D+{h} | {s['mae']:.3f} | {p['mae']:.3f} | {sk['skill_pct']:.1f}% ({sk['low_95_pct']:.1f}% to "
                f"{sk['high_95_pct']:.1f}%) | {sc['skill_pct']:.1f}% | {s['grade_accuracy']:.3f} |")
    without = [f["test_scores"][f"D+{h} | same model, + Baengnyeong"]["mae"] for h in (1, 2, 3)]
    in_card(f"test MAE of {without[0]:.3f}, {without[1]:.3f} and {without[2]:.3f}")
    c, p, q = (f["alerts"][f"D+1 | {name}"] for name in
               (f"classifier (p >= {thresholds['1']:.2f})", "persistence (grade rule)", "90th percentile above 35"))
    in_card(f"POD of {c['pod']:.3f} and a FAR of {c['far']:.3f} (CSI {c['csi']:.3f}); persistence {p['pod']:.3f} "
            f"and {p['far']:.3f} (CSI {p['csi']:.3f}); the 90th percentile rule {q['pod']:.3f} and {q['far']:.3f}")
    beyond = max(v["csi"] for key, v in f["alerts"].items() if not key.startswith("D+1"))
    in_card(f"no alert reaches a CSI above {beyond:.3f}")
    cov = [f["quantiles"][f"D+{h} | test"]["calibrated_coverage"] for h in (1, 2, 3)]
    in_card(f"covers {cov[0]:.3f}, {cov[1]:.3f} and {cov[2]:.3f} of the test days")
    in_card(f"(-{abs(f['test_scores'][f'D+2 | {chosen}']['bias']):.3f} and -{abs(f['test_scores'][f'D+3 | {chosen}']['bias']):.3f} ug/m3)")
    g = k["11"]
    ets = g["backtest"]["ETS"]
    in_card(f"ETS (MASE {ets['mase']:.3f}, 80% coverage {ets['coverage_80']:.3f})")
    in_card(f"{g['annual_backtest']['ETS | 3']['bias']:.2f} ug/m3 too high on average three years ahead")
    years = [g["outlook"][f"forecast: ETS | {y}"] for y in (2026, 2027, 2028)]
    in_card("annual median " + ", ".join(f"{y['annual_median']:.2f}" for y in years[:2]) + f" and {years[2]['annual_median']:.2f} ug/m3")
    in_card("chance of meeting 15 ug/m3 of " + ", ".join(f"{y['p_meets_15']:.2f}" for y in years[:2]) + f" and {years[2]['p_meets_15']:.2f}")
    in_card("median Bad days " + ", ".join(f"{y['bad_days_median']:.0f}" for y in years[:2]) + f" and {years[2]['bad_days_median']:.0f} a year")
    in_card(f"falls to {g['outlook']['scenario A: decline continues | 2028']['annual_median']:.2f} in 2028")
    in_card(f"stays at {g['outlook']['scenario B: decline stalls | 2028']['annual_median']:.2f}")
    in_card(f"({k['05']['mae']['ridge']:.2f} vs {k['05']['mae']['persistence']:.2f} ug/m3 for persistence)")
