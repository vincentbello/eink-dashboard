"""fetchers — Data-retrieval modules, each with a typed return value."""

from fetchers.weather import WeatherData, fetch_weather
from fetchers.calendar import CalendarEvent, fetch_calendar
from fetchers.subway import SubwayArrival, fetch_subway
from fetchers.citibike import CitiBikeStation, fetch_citibike

__all__ = [
    "WeatherData",
    "fetch_weather",
    "CalendarEvent",
    "fetch_calendar",
    "SubwayArrival",
    "fetch_subway",
    "CitiBikeStation",
    "fetch_citibike",
]
