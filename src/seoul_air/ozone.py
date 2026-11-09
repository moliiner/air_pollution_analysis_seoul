"""Ozone statistics against the Korean standards.

Korean ambient standards for ozone: 0.06 ppm as an 8-hour mean and 0.1 ppm as a 1-hour
mean; an ozone warning (주의보) is issued from 0.12 ppm as a 1-hour mean.
"""

STANDARD_8H_PPM = 0.06
STANDARD_1H_PPM = 0.1
WARNING_1H_PPM = 0.12


def daily_max_8h(hourly, min_hours=6):
    """Highest 8-hour mean of each day, for one station's complete hourly series.

    Each 8-hour mean ends at an hour of the day and needs min_hours valid hours (75%).
    `hourly` is a Series with a DatetimeIndex, one value per hour.
    """
    rolling = hourly.rolling(8, min_periods=min_hours).mean()
    return rolling.groupby(rolling.index.normalize()).max()


def daily_max_1h(hourly, min_hours=18):
    """Highest hourly value of each day with at least min_hours readings."""
    grouped = hourly.groupby(hourly.index.normalize())
    return grouped.max().where(grouped.count() >= min_hours)
