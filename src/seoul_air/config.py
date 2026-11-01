"""Project paths and constants shared by notebooks, scripts and tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_EXTERNAL = ROOT / "data" / "external"
DATA_PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
METRICS = ROOT / "reports" / "metrics"

TIMEZONE = "Asia/Seoul"

# Kaggle "Air Pollution in Seoul" (bappekim), public download endpoint
KAGGLE_URL = "https://www.kaggle.com/api/v1/datasets/download/bappekim/air-pollution-in-seoul"
RAW_FILES = {
    "measurements": "Measurement_info.csv",
    "items": "Measurement_item_info.csv",
    "stations": "Measurement_station_info.csv",
    "summary": "Measurement_summary.csv",
}

# Pollutants and their units; keys are the column names used after cleaning
POLLUTANTS = {
    "so2": "ppm",
    "no2": "ppm",
    "co": "ppm",
    "o3": "ppm",
    "pm10": "ug/m3",
    "pm25": "ug/m3",
}
# Item codes of Measurement_item_info.csv
ITEM_CODES = {1: "so2", 3: "no2", 5: "co", 6: "o3", 8: "pm10", 9: "pm25"}

# Instrument status codes (dataset documentation); only 0 is a valid reading
STATUS_NORMAL = 0
STATUS_LABELS = {
    0: "Normal",
    1: "Needs calibration",
    2: "Abnormal",
    4: "Power cut off",
    8: "Under repair",
    9: "Abnormal data",
}

# A daily mean is valid only with at least 18 of 24 hourly readings (75%)
MIN_HOURS_PER_DAY = 18

# Temporal split for the forecast (never a random split): fit on 2017-2018, test on 2019
TRAIN_END = "2018-12-31"
TEST_START = "2019-01-01"
