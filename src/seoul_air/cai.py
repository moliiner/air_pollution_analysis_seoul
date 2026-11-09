"""Korean Comprehensive Air-quality Index (CAI, 통합대기환경지수).

Definition of AirKorea and the Seoul Metropolitan Government
(https://cleanair.seoul.go.kr/information/info3, https://www.airkorea.or.kr/eng/khaiInfo?pMENU_NO=166):

- A sub-index of 0-500 for each of six pollutants, by linear interpolation inside the
  concentration band of the reading: Ip = (IHI - ILO) / (BPHI - BPLO) * (Cp - BPLO) + ILO.
- Gases use 1-hour concentrations; PM10 and PM2.5 use the 24-hour predicted moving
  average (C24E), which weights the last 4 hours as much as the last 12.
- The CAI is the highest sub-index. When two pollutants are graded Unhealthy or worse
  (sub-index above 100), 50 points are added; three or more add 75 points.
- Grades: Good 0-50, Moderate 51-100, Unhealthy 101-250, Very unhealthy above 250.
"""
import numpy as np
import pandas as pd

# Upper bound of each band (Good, Moderate, Unhealthy, Very unhealthy), and the
# resolution to which a concentration is rounded before it is placed in a band
BREAKPOINTS = {
    "so2": ([0.02, 0.05, 0.15, 1.0], 0.001),
    "co": ([2.0, 9.0, 15.0, 50.0], 0.01),
    "o3": ([0.03, 0.09, 0.15, 0.6], 0.001),
    "no2": ([0.03, 0.06, 0.2, 2.0], 0.001),
    "pm10": ([30, 80, 150, 600], 1),
    "pm25": ([15, 35, 75, 500], 1),
}
INDEX_LOW = [0, 51, 101, 251]
INDEX_HIGH = [50, 100, 250, 500]
GRADES = ["Good", "Moderate", "Unhealthy", "Very unhealthy"]
# Threshold M of the predicted moving average, ug/m3
PM_THRESHOLD = {"pm10": 70, "pm25": 30}


def sub_index(pollutant, concentration):
    """Sub-index of each concentration; NaN stays NaN, values above the scale give 500."""
    uppers, resolution = BREAKPOINTS[pollutant]
    c = np.round(np.asarray(concentration, dtype=float) / resolution) * resolution
    out = np.full(c.shape, np.nan)
    lower = 0.0
    for band, upper in enumerate(uppers):
        bp_low = 0.0 if band == 0 else lower + resolution
        inside = (c >= (0 if band == 0 else lower + resolution / 2)) & (c <= upper + 1e-12)
        slope = (INDEX_HIGH[band] - INDEX_LOW[band]) / (upper - bp_low)
        out = np.where(inside, INDEX_LOW[band] + slope * (np.maximum(c, bp_low) - bp_low), out)
        lower = upper
    return np.where(c > uppers[-1], INDEX_HIGH[-1], out)


def grade(index):
    """CAI grade of each index value, as an ordered categorical."""
    bins = [-np.inf, 50, 100, 250, np.inf]
    return pd.cut(pd.Series(index, dtype=float), bins=bins, labels=GRADES)


def predicted_24h_average(hourly, threshold, min_hours_12=9, min_hours_4=3):
    """24-hour predicted moving average (C24E) of one station's hourly series.

    C12 is the mean of the last 12 hours and C4 the mean of the last 4 adjusted hours;
    an hour at or above the threshold whose ratio to C12 lies in [0.9, 1.7] counts as
    0.75 of its value. C24E = (12 * C12 + 12 * C4) / 24. The series must be complete
    (one row per hour); hours without enough readings give NaN.
    """
    hourly = pd.Series(hourly, dtype=float)
    c12 = hourly.rolling(12, min_periods=min_hours_12).mean()
    ratio = hourly / c12
    adjusted = hourly.where(~((hourly >= threshold) & (ratio >= 0.9) & (ratio <= 1.7)), 0.75 * hourly)
    c4 = adjusted.rolling(4, min_periods=min_hours_4).mean()
    return (12 * c12 + 12 * c4) / 24


def station_cai(hourly):
    """Hourly CAI of one station.

    `hourly` has one row per hour, in order, with columns so2, co, o3, no2, pm10, pm25.
    Returns the sub-indices, the CAI with its bonus, its grade and the pollutant with
    the highest sub-index.
    """
    subs = pd.DataFrame(index=hourly.index)
    for pollutant in ["so2", "co", "o3", "no2"]:
        subs[pollutant] = sub_index(pollutant, hourly[pollutant])
    for pollutant in ["pm10", "pm25"]:
        c24e = predicted_24h_average(hourly[pollutant].to_numpy(), PM_THRESHOLD[pollutant])
        subs[pollutant] = sub_index(pollutant, c24e)
    unhealthy = (subs > 100).sum(axis=1)
    bonus = np.select([unhealthy >= 3, unhealthy == 2], [75, 50], 0)
    out = pd.DataFrame({
        "cai": subs.max(axis=1, skipna=True) + bonus,
        # An hour without any sub-index has no main pollutant
        "main_pollutant": subs.fillna(-1).idxmax(axis=1).where(subs.notna().any(axis=1)),
        "unhealthy_pollutants": unhealthy,
    }, index=hourly.index)
    out["grade"] = grade(out["cai"].to_numpy()).to_numpy()
    return pd.concat([out, subs.add_prefix("index_")], axis=1)
