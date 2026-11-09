import numpy as np

from seoul_air import config, report


def test_key_figures_round_trip_with_numpy_types(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "METRICS", tmp_path)
    figures = {"share": np.float64(23.4), "days": np.int64(1077), "flag": np.bool_(True),
               "by_year": {2017: np.float64(24.6)}, "pair": (np.int64(1), 2.5)}
    path = report.save_key_figures("99_test", figures)
    assert path == tmp_path / "99_test_key_figures.json"
    assert report.load_key_figures("99_test") == {
        "share": 23.4, "days": 1077, "flag": True, "by_year": {"2017": 24.6}, "pair": [1, 2.5]}
