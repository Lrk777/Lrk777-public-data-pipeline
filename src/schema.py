"""Schema validation for raw and clean daily weather tables."""

from __future__ import annotations

import pandera.pandas as pa
from pandera.typing import Series


class RawDailyWeatherSchema(pa.DataFrameModel):
    """Minimal columns expected after flattening the Open-Meteo daily payload."""

    date: Series[str] = pa.Field(nullable=False)
    temperature_2m_max: Series[float] = pa.Field(nullable=True)
    temperature_2m_min: Series[float] = pa.Field(nullable=True)
    temperature_2m_mean: Series[float] = pa.Field(nullable=True)
    precipitation_sum: Series[float] = pa.Field(nullable=True, ge=0)
    rain_sum: Series[float] = pa.Field(nullable=True, ge=0)
    snowfall_sum: Series[float] = pa.Field(nullable=True, ge=0)
    windspeed_10m_max: Series[float] = pa.Field(nullable=True, ge=0)
    weathercode: Series[float] = pa.Field(nullable=True)

    class Config:
        coerce = True
        strict = False


class CleanDailyWeatherSchema(pa.DataFrameModel):
    """Analysis-ready daily weather for Toronto."""

    date: Series[pa.Date] = pa.Field(nullable=False)
    year: Series[int] = pa.Field(ge=1900, le=2100)
    month: Series[int] = pa.Field(ge=1, le=12)
    dow: Series[int] = pa.Field(ge=0, le=6)  # Monday=0
    temp_max_c: Series[float] = pa.Field(nullable=False, ge=-60, le=60)
    temp_min_c: Series[float] = pa.Field(nullable=False, ge=-60, le=60)
    temp_mean_c: Series[float] = pa.Field(nullable=False, ge=-60, le=60)
    precip_mm: Series[float] = pa.Field(nullable=False, ge=0)
    rain_mm: Series[float] = pa.Field(nullable=False, ge=0)
    snow_cm: Series[float] = pa.Field(nullable=False, ge=0)
    wind_max_kmh: Series[float] = pa.Field(nullable=False, ge=0)
    weather_code: Series[int] = pa.Field(nullable=False, ge=0, le=99)
    is_precip_day: Series[bool] = pa.Field(nullable=False)
    is_freezing: Series[bool] = pa.Field(nullable=False)
    temp_range_c: Series[float] = pa.Field(nullable=False, ge=0)
    location: Series[str] = pa.Field(nullable=False)
    source: Series[str] = pa.Field(nullable=False)

    class Config:
        coerce = True
        strict = True


def validate_raw(df):
    return RawDailyWeatherSchema.validate(df, lazy=True)


def validate_clean(df):
    return CleanDailyWeatherSchema.validate(df, lazy=True)
