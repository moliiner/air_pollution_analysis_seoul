"""Project paths and constants shared by notebooks, scripts and tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_EXTERNAL = ROOT / "data" / "external"
DATA_PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
METRICS = ROOT / "reports" / "metrics"

TIMEZONE = "Asia/Seoul"

# Pollutants and their units as published by AirKorea / Seoul Open Data Plaza
POLLUTANTS = {
    "pm10": "ug/m3",
    "pm25": "ug/m3",
    "o3": "ppm",
    "no2": "ppm",
    "co": "ppm",
    "so2": "ppm",
}

# The 25 autonomous districts (gu) of Seoul
DISTRICTS = [
    "Dobong-gu", "Dongdaemun-gu", "Dongjak-gu", "Eunpyeong-gu", "Gangbuk-gu",
    "Gangdong-gu", "Gangnam-gu", "Gangseo-gu", "Geumcheon-gu", "Guro-gu",
    "Gwanak-gu", "Gwangjin-gu", "Jongno-gu", "Jung-gu", "Jungnang-gu",
    "Mapo-gu", "Nowon-gu", "Seocho-gu", "Seodaemun-gu", "Seongbuk-gu",
    "Seongdong-gu", "Songpa-gu", "Yangcheon-gu", "Yeongdeungpo-gu", "Yongsan-gu",
]

# Temporal split for any predictive model (never a random split)
TRAIN_END = "2023-12-31"
VALID_END = "2024-12-31"  # the test period starts the day after
