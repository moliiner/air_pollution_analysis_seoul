import pandas as pd

from seoul_air.data import load_station_history


def test_history_has_one_row_per_district():
    history = load_station_history()
    assert len(history) == 25
    assert history["district"].is_unique
    assert history["district"].str.endswith("-gu").all()


def test_years_are_consistent():
    history = load_station_history()
    assert history["installed"].between(1973, 1997).all()
    assert history["equipment_replaced"].between(2015, 2019).all()
    relocated = history.dropna(subset=["last_relocation"])
    assert (relocated["last_relocation"] >= relocated["installed"]).all()
    assert relocated["relocated_from"].notna().all()


def test_relocations_during_the_study_period():
    history = load_station_history()
    moved = history.loc[history["last_relocation"].between(2017, 2019), "district"]
    assert set(moved) == {"Seongdong-gu", "Seodaemun-gu", "Mapo-gu", "Songpa-gu"}


def test_yeongdeungpo_row():
    history = load_station_history().set_index("district")
    assert history.loc["Yeongdeungpo-gu", "last_relocation"] == 2003
    assert history.loc["Yeongdeungpo-gu", "equipment_replaced"] == 2019
    assert not pd.isna(history.loc["Yeongdeungpo-gu", "relocated_from"])
