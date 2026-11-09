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
    return {nb: load_key_figures(nb) for nb in ["01", "02", "03", "04", "05", "07", "08"]}


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
