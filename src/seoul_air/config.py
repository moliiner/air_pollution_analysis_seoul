"""Project paths and constants shared by notebooks, scripts and tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_EXTERNAL = ROOT / "data" / "external"
DATA_PROCESSED = ROOT / "data" / "processed"
STATION_HISTORY = ROOT / "data" / "reference" / "station_history.csv"
API_SAMPLES = ROOT / "data" / "reference" / "seoul_api_hourly_samples.csv"
REALTIME_LABEL_LOG = ROOT / "data" / "reference" / "realtime_label_check.csv"
FIGURES = ROOT / "reports" / "figures"
METRICS = ROOT / "reports" / "metrics"

TIMEZONE = "Asia/Seoul"
# Timestamps of the Kaggle files mark the START of each hourly average, in KST
# (verified in notebook 01). Official Seoul and AirKorea labels mark its END, so
# Kaggle 07:00 (07:00-08:00) is the official 08:00 reading.
OFFICIAL_LABEL_OFFSET_HOURS = 1

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
