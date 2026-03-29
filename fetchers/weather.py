"""
fetchers/weather.py — Current conditions from the Open-Meteo API.

Open-Meteo is free and requires no API key.
Docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WMO weather interpretation codes → (human label, icon key)
# Full table: https://open-meteo.com/en/docs#weathervariables
# ---------------------------------------------------------------------------
_WMO_CODE_MAP: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "sunny"),
    1: ("Mainly clear", "sunny"),
    2: ("Partly cloudy", "cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "foggy"),
    48: ("Rime fog", "foggy"),
    51: ("Light drizzle", "rainy"),
    53: ("Drizzle", "rainy"),
    55: ("Dense drizzle", "rainy"),
    56: ("Freezing drizzle", "rainy"),
    57: ("Heavy freezing drizzle", "rainy"),
    61: ("Slight rain", "rainy"),
    63: ("Rain", "rainy"),
    65: ("Heavy rain", "rainy"),
    66: ("Freezing rain", "rainy"),
    67: ("Heavy freezing rain", "rainy"),
    71: ("Slight snow", "snowy"),
    73: ("Snow", "snowy"),
    75: ("Heavy snow", "snowy"),
    77: ("Snow grains", "snowy"),
    80: ("Slight showers", "rainy"),
    81: ("Rain showers", "rainy"),
    82: ("Violent showers", "rainy"),
    85: ("Snow showers", "snowy"),
    86: ("Heavy snow showers", "snowy"),
    95: ("Thunderstorm", "stormy"),
    96: ("Thunderstorm w/ hail", "stormy"),
    99: ("Thunderstorm w/ heavy hail", "stormy"),
}

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_HTTP_TIMEOUT = 10  # seconds

# Module-level cache – last successful result is kept here.
_cache: Optional[WeatherData] = None  # type: ignore[name-defined]  # forward ref resolved below


@dataclass(frozen=True)
class WeatherData:
    """Current weather conditions."""

    temperature: float       # °F
    condition: str           # human-readable string
    wind_speed: float        # mph
    icon_key: str            # one of: sunny | cloudy | rainy | snowy | stormy | foggy
    fetched_at: datetime


def fetch_weather() -> Optional[WeatherData]:
    """Fetch current weather from Open-Meteo.

    Returns a :class:`WeatherData` on success, or the last cached result
    (or ``None``) if the request fails.
    """
    global _cache
    try:
        resp = requests.get(
            _OPEN_METEO_URL,
            params={
                "latitude": config.LATITUDE,
                "longitude": config.LONGITUDE,
                "current": "temperature_2m,weathercode,windspeed_10m,precipitation",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": config.TIMEZONE,
            },
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        current = data["current"]
        code: int = int(current["weathercode"])
        condition, icon_key = _WMO_CODE_MAP.get(code, ("Unknown", "cloudy"))

        result = WeatherData(
            temperature=float(current["temperature_2m"]),
            condition=condition,
            wind_speed=float(current["windspeed_10m"]),
            icon_key=icon_key,
            fetched_at=datetime.now(),
        )
        _cache = result
        logger.debug(
            "Weather fetched: %.1f°F, %s (code %d)", result.temperature, condition, code
        )
        return result

    except requests.RequestException as exc:
        logger.warning("Weather fetch failed (network): %s", exc)
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Weather fetch failed (parse): %s", exc)
    except Exception:
        logger.exception("Weather fetch failed (unexpected)")

    if _cache is not None:
        logger.info("Returning stale weather data from %s", _cache.fetched_at)
    return _cache
