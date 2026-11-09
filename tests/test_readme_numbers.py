"""The figures quoted in the README must match the files the notebooks wrote.

If a notebook changes a result, this test fails until the README is updated.
"""
import pandas as pd
import pytest

from seoul_air import config
from seoul_air.report import load_key_figures

README = (config.ROOT / "README.md").read_text(encoding="utf-8")
NUMBER_WORDS = {4: "Four", 5: "Five", 9: "nine"}


@pytest.fixture(scope="module")
def k():
    return {nb: load_key_figures(nb) for nb in ["01", "02", "03", "04", "05", "07"]}


def quoted(text):
    assert text in README, f"README does not contain: {text!r}"


def test_data_quality(k):
    f = k["01"]
    quoted(f"{f['dropped_pct']:.2f}% of the readings carry a non-normal instrument status")
    quoted(f"all {f['summary_pm25_above_500']:,} PM2.5 readings above 500 ug/m3")
    quoted(f"changes the grade of {f['filter_check_grade_changes']} of {f['filter_check_station_days']:,} station-days")
    quoted(f"no daily value on {f['gap_days']} days of 2019, including {f['longest_gap_days']} in a row")
    quoted(f"the analysis uses {f['valid_city_days']:,} valid days")


def test_seasons_and_level(k):
    month, bad, year = (k["02"][key] for key in ["pm25_median_by_month", "bad_or_worse_pct_by_month", "pm25_mean_by_year"])
    quoted(f"peaks in March ({month['3']:.1f} ug/m3) and is lowest in September ({month['9']:.1f})")
    quoted(f"In March {bad['3']:.1f}% of station-days are graded Bad or Very bad, against {bad['8']:.1f}% in August")
    quoted(f"The mean station-day PM2.5 was {year['2017']:.1f}, {year['2018']:.1f} and {year['2019']:.1f} ug/m3")


def test_variance_and_districts(k):
    f = k["03"]
    share = f["variance_share_pct"]
    quoted(f"The calendar month accounts for {share['Calendar month (season)']:.1f}% of the station-day variance "
           f"of PM2.5 and the district for {share['District']:.1f}%")
    quoted(f"the date accounts for {share['Date (each single day)']:.1f}% of the station-day variance")
    quoted(f"correlates at {f['min_pairwise_correlation']:.2f} or more")
    low, high = f["spearman_between_years"]
    quoted(f"(Spearman {low:.2f}-{high:.2f})")
    quoted(f"(typically {f['median_quarterly_offset_range']:.1f} ug/m3)")
    quoted(f"the highest and lowest medians ({f['median_gap_between_district_medians']:.1f})")
    quoted(f"{NUMBER_WORDS[f['relocated_2017_2019']]} stations were relocated in 2018")
    groups = f["categories"]
    consistent = groups.get("Above the rest of the city", 0) + groups.get("Below the rest of the city", 0)
    quoted(f"{groups['Not comparable']} are not comparable across the period; only {consistent} of 25")
    korean = f"달력 월이 차지하는 비중은 {share['Calendar month (season)']:.1f}%, 자치구는 {share['District']:.1f}%"
    quoted(korean)


def test_episodes(k):
    quoted(f"{k['04']['episodes_2plus_days']} multi-day Bad episodes")


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
