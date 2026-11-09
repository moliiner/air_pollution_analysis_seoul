import pandas as pd
import pytest

from seoul_air import population

CSV = ('"행정구역","2015년12월_총인구수","2015년12월_세대수"\n'
       '"서울특별시  (1100000000)","300","9"\n'
       '"서울특별시 종로구 (1111000000)","100","3"\n'
       '"서울특별시 중구 (1114000000)","200","6"\n'
       '"부산광역시  (2600000000)","999","9"\n')


def test_read_population_keeps_seoul(tmp_path):
    path = tmp_path / "p.csv"
    path.write_bytes(CSV.encode("cp949"))
    out = population.read_population(path)
    assert out["name"].tolist() == ["서울특별시", "서울특별시 종로구", "서울특별시 중구"]
    assert out["population"].tolist() == [300, 100, 200]
    assert (out["year"] == 2015).all()


def test_load_population_checks_the_districts(tmp_path, monkeypatch):
    path = tmp_path / "mois_population_201512.csv"
    path.write_bytes(CSV.encode("cp949"))
    monkeypatch.setattr(population, "RAW_DIR", tmp_path)
    with pytest.raises(ValueError, match="expected 25"):
        population.load_population([2015])


def test_population_weighted_mean():
    assert population.population_weighted_mean([10, 20], [3, 1]) == pytest.approx(12.5)
    assert population.population_weighted_mean([10, float("nan")], [3, 1]) == pytest.approx(10)
    assert pd.isna(population.population_weighted_mean([float("nan")], [1]))
