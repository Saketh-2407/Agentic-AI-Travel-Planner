"""Daily weather via Open-Meteo. Free, no API key.

The live forecast endpoint only covers roughly the next 16 days. Most trips are
planned further out than that, so for any date outside the live window we fall
back to the Historical Weather API for the *same calendar dates one year ago*
at that location — real recorded data, just flagged `typical: true` so callers
(and the planner LLM) know it's a typical-conditions estimate, not a live
forecast for the actual trip date.
"""

import datetime
import logging

import httpx

from app.tools import cache

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEOUT_SECONDS = 10.0
CACHE_TTL_SECONDS = 60 * 60 * 6  # forecasts shift; refresh a few times a day
DAILY_FIELDS = "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"


def _normalize(raw: dict, *, typical: bool, override_dates: list[str] | None = None) -> list[dict]:
    daily = raw.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    precipitation = daily.get("precipitation_sum", [])
    codes = daily.get("weathercode", [])
    return [
        {
            "date": override_dates[i] if override_dates else dates[i],
            "temp_max_c": highs[i] if i < len(highs) else None,
            "temp_min_c": lows[i] if i < len(lows) else None,
            "precipitation_mm": precipitation[i] if i < len(precipitation) else None,
            "weathercode": codes[i] if i < len(codes) else None,
            "typical": typical,
        }
        for i in range(len(dates))
    ]


def _shift_years(date_str: str, years: int) -> str:
    d = datetime.date.fromisoformat(date_str)
    try:
        return d.replace(year=d.year + years).isoformat()
    except ValueError:
        return d.replace(year=d.year + years, day=28).isoformat()  # Feb 29 -> Feb 28


def _date_range(start: str, end: str) -> list[str]:
    s, e = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    return [(s + datetime.timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]


def forecast(lat: float, lon: float, start: str, end: str) -> list[dict]:
    """lat/lon: decimal degrees. start/end: 'YYYY-MM-DD'.
    Returns [] only if both the live forecast and the historical fallback fail."""
    params = {"lat": lat, "lon": lon, "start": start, "end": end}

    def compute() -> list[dict]:
        try:
            response = httpx.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": DAILY_FIELDS,
                    "timezone": "auto",
                    "start_date": start,
                    "end_date": end,
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return _normalize(response.json(), typical=False)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.info(
                "weather.forecast: %s-%s out of live forecast range, falling back to last year's actuals: %s",
                start,
                end,
                exc,
            )

        try:
            hist_start, hist_end = _shift_years(start, -1), _shift_years(end, -1)
            response = httpx.get(
                ARCHIVE_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": DAILY_FIELDS,
                    "timezone": "auto",
                    "start_date": hist_start,
                    "end_date": hist_end,
                },
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return _normalize(response.json(), typical=True, override_dates=_date_range(start, end))
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("weather.forecast: historical fallback also failed for (%s,%s) %s-%s: %s", lat, lon, start, end, exc)
            return []

    return cache.get_or_set("weather", params, CACHE_TTL_SECONDS, compute)
