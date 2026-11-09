import io
import zipfile

import pandas as pd
import pytest

from seoul_air import sources

HEADER_2221 = ("측정일시,권역코드,권역명,측정소코드,측정소명,미세먼지 1시간(㎍/㎥),미세먼지 24시간(㎍/㎥),"
               "초미세먼지(㎍/㎥),오존(ppm),이산화질소농도(ppm),일산화탄소농도(ppm),아황산가스농도(ppm)\n")


def _write_2221(path, rows, encoding="utf-8-sig", zipped=True):
    text = HEADER_2221 + "".join(rows)
    data = text.encode(encoding)
    if zipped:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("file.csv", data)
        data = buffer.getvalue()
    path.write_bytes(data)


def _row(label, code="111123", name="종로구", pm25="12", pm10="30"):
    return f"{label},100,도심권,{code},{name},{pm10},31,{pm25},0.02,0.03,0.4,0.003\n"


def test_read_oa15526(tmp_path):
    path = tmp_path / "AIR_HOUR_2022.csv"
    path.write_text("측정일시,측정소 코드,측정항목,평균값,측정기 상태,국가 기준초과 구분,지자체 기준초과 구분\n"
                    "2022010100,101,9,12.0,0,0,0\n2022010101,101,9,985.0,9,0,0\n", encoding="utf-8-sig")
    out = sources.read_oa15526(path)
    assert out["datetime"].tolist() == [pd.Timestamp("2022-01-01 00:00"), pd.Timestamp("2022-01-01 01:00")]
    assert out["pollutant"].tolist() == ["pm25", "pm25"]
    assert out["status"].tolist() == [0, 9]


@pytest.mark.parametrize("encoding,zipped", [("utf-8-sig", True), ("cp949", False)])
def test_read_oa2221_moves_labels_to_the_start_of_the_hour(tmp_path, encoding, zipped):
    path = tmp_path / "OA-2221_2023.zip"
    _write_2221(path, [_row("202301010100"), _row("202301010200", pm25="")], encoding, zipped)
    out = sources.read_oa2221(path)
    pm25 = out[out["pollutant"] == "pm25"]
    assert pm25["datetime"].tolist() == [pd.Timestamp("2023-01-01 00:00")]  # the blank reading is dropped
    assert set(out["station_code"]) == {101}
    assert set(out["pollutant"]) == {"pm10", "pm25", "o3", "no2", "co", "so2"}  # the 24-hour PM10 is not kept
    assert (out["status"] == 0).all()


def test_read_oa2221_rejects_unknown_stations(tmp_path):
    path = tmp_path / "OA-2221_2023.zip"
    _write_2221(path, [_row("202301010100", code="999999")])
    with pytest.raises(ValueError, match="unknown AirKorea codes"):
        sources.read_oa2221(path)


def test_extended_load_keeps_year_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "RAW_DIR", tmp_path)
    monkeypatch.setattr(sources, "SOURCE_YEARS", {"OA-15526": range(2022, 2023), "OA-2221": range(2023, 2024)})
    (tmp_path / "AIR_HOUR_2022.csv").write_text(
        "a,b,c,d,e,f,g\n2022123123,101,9,10.0,0,0,0\n", encoding="utf-8-sig")
    # OA-2221 2023 starts with the last hour of 2022; its own last hour is in the 2024 file
    _write_2221(tmp_path / "OA-2221_2023.zip", [_row("202301010000", pm25="99"), _row("202301010100", pm25="20")])
    _write_2221(tmp_path / "OA-2221_2024.zip", [_row("202401010000", pm25="30")])
    out = sources.load_extended_measurements(2022, 2023)
    pm25 = out[out["pollutant"] == "pm25"].set_index("datetime")
    assert pm25.loc[pd.Timestamp("2022-12-31 23:00"), "value"] == 10.0  # OA-15526 wins the overlap hour
    assert pm25.loc[pd.Timestamp("2022-12-31 23:00"), "source"] == "OA-15526"
    assert pm25.loc[pd.Timestamp("2023-12-31 23:00"), "value"] == 30.0  # taken from the next file
    assert not pm25.index.duplicated().any()


def test_stations_reference_has_both_code_systems():
    stations = sources.load_stations_reference()
    assert len(stations) == 25
    assert stations["seoul_code"].between(101, 125).all()
    assert stations["airkorea_code"].str.match(r"^111\d{3}$").all()
    assert stations["district"].is_unique and stations["airkorea_code"].is_unique


class _Response:
    def __init__(self, name):
        self.headers = {"Content-Disposition": f'attachment; filename="{name}"'.encode("utf-8").decode("latin-1")}
        self.content = b"data"

    def raise_for_status(self):
        pass


def test_download_checks_the_served_file_name(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(sources, "RAW_DIR", tmp_path)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Response("서울시_기간별_시간평균_대기환경_정보_2024.zip"))
    with pytest.raises(RuntimeError, match="ids may have changed"):
        sources.download_file("OA-2221", 2025)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Response("서울시_기간별_시간평균_대기환경_정보_2025.zip"))
    assert sources.download_file("OA-2221", 2025).read_bytes() == b"data"


def test_official_reference_table():
    official = pd.read_csv(sources.config.ROOT / "data/reference/official_annual_means.csv")
    assert set(official["scope"]) == {"station", "city"}
    assert official["year"].between(2015, 2025).all()
    assert official["url"].str.startswith("http").all()


def test_agreement_finds_the_offset():
    hours = pd.date_range("2022-01-01", periods=5, freq="h")
    a = pd.DataFrame({"datetime": hours, "station_code": 101, "pollutant": "pm25", "value": [1.0, 2, 3, 4, 5]})
    b = a.assign(datetime=a["datetime"] + pd.Timedelta(hours=1))  # b labels the end of the hour
    table = sources.agreement(a, b).set_index("lag_hours")
    assert table.loc[-1, "identical_pct"] == 100
    assert table.loc[0, "identical"] == 0 and table.loc[0, "compared"] == 4


def test_source_catalog_covers_every_source():
    catalog = sources.SOURCE_CATALOG
    assert len(catalog) == 4 and catalog["url"].str.startswith("https://").all()
    assert {"final", "licence", "hour_label", "instrument_status"} <= set(catalog.columns)
