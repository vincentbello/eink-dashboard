"""
tests/test_fetchers.py — Unit tests for all four data fetchers.

Tests mock external HTTP calls and verify that:
  - Each fetcher returns a valid typed result on well-formed responses.
  - Malformed / empty API responses return safe fallback values (no raise).
  - Network errors return the cached stale value (or None on first call).

Run from the project root:
    cd dashboard && python -m pytest tests/test_fetchers.py -v
Or:
    python -m unittest tests.test_fetchers -v
"""

from __future__ import annotations

import importlib
import sys
import time
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure the project root is on sys.path.
import os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(json_data: Any = None, status_code: int = 200, content: bytes = b"") -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    if json_data is not None:
        resp.json.return_value = json_data
    if status_code >= 400:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(f"{status_code} Error")
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Weather fetcher tests
# ---------------------------------------------------------------------------


class TestWeatherFetcher(unittest.TestCase):
    """Tests for fetchers.weather.fetch_weather."""

    def setUp(self) -> None:
        # Reset module cache between tests.
        import fetchers.weather as mod
        mod._cache = None

    def test_successful_fetch_returns_dataclass(self) -> None:
        """A well-formed Open-Meteo response produces a WeatherData object."""
        payload = {
            "current": {
                "temperature_2m": 68.5,
                "weathercode": 2,
                "windspeed_10m": 12.3,
                "precipitation": 0.0,
            }
        }
        with patch("fetchers.weather.requests.get", return_value=_mock_response(payload)):
            from fetchers.weather import fetch_weather, WeatherData
            result = fetch_weather()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, WeatherData)
        self.assertAlmostEqual(result.temperature, 68.5)
        self.assertEqual(result.icon_key, "cloudy")  # WMO code 2

    def test_sunny_icon_key(self) -> None:
        """WMO code 0 maps to icon_key 'sunny'."""
        payload = {
            "current": {
                "temperature_2m": 75.0,
                "weathercode": 0,
                "windspeed_10m": 5.0,
                "precipitation": 0.0,
            }
        }
        with patch("fetchers.weather.requests.get", return_value=_mock_response(payload)):
            from fetchers.weather import fetch_weather
            result = fetch_weather()

        self.assertIsNotNone(result)
        self.assertEqual(result.icon_key, "sunny")

    def test_network_error_returns_none_on_first_call(self) -> None:
        """A network error on the first call returns None (no stale data)."""
        from requests import RequestException
        with patch("fetchers.weather.requests.get", side_effect=RequestException("timeout")):
            from fetchers.weather import fetch_weather
            result = fetch_weather()
        self.assertIsNone(result)

    def test_network_error_returns_stale_cache(self) -> None:
        """After a successful fetch, a network error returns cached data."""
        import fetchers.weather as mod
        from fetchers.weather import WeatherData

        stale = WeatherData(
            temperature=60.0,
            condition="Clear sky",
            wind_speed=5.0,
            icon_key="sunny",
            fetched_at=datetime.now(),
        )
        mod._cache = stale

        from requests import RequestException
        with patch("fetchers.weather.requests.get", side_effect=RequestException("down")):
            result = mod.fetch_weather()

        self.assertEqual(result, stale)

    def test_malformed_response_returns_none(self) -> None:
        """Missing keys in the API response return None (no crash)."""
        with patch("fetchers.weather.requests.get", return_value=_mock_response({})):
            from fetchers.weather import fetch_weather
            result = fetch_weather()
        self.assertIsNone(result)

    def test_http_error_returns_none(self) -> None:
        """An HTTP 500 response returns None without raising."""
        with patch("fetchers.weather.requests.get", return_value=_mock_response(status_code=500)):
            from fetchers.weather import fetch_weather
            result = fetch_weather()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Citi Bike fetcher tests
# ---------------------------------------------------------------------------


class TestCitiBikeFetcher(unittest.TestCase):
    """Tests for fetchers.citibike.fetch_citibike."""

    def setUp(self) -> None:
        import fetchers.citibike as mod
        mod._cache = None

    def _info_payload(self, station_id: str = "3279", name: str = "Varick & Vandam") -> dict:
        return {
            "data": {
                "stations": [
                    {"station_id": station_id, "name": name, "capacity": 20}
                ]
            }
        }

    def _status_payload(
        self,
        station_id: str = "3279",
        bikes: int = 12,
        ebikes: int = 3,
        docks: int = 8,
        is_renting: bool = True,
    ) -> dict:
        return {
            "data": {
                "stations": [
                    {
                        "station_id": station_id,
                        "num_bikes_available": bikes,
                        "num_ebikes_available": ebikes,
                        "num_docks_available": docks,
                        "is_renting": int(is_renting),
                    }
                ]
            }
        }

    def test_successful_fetch(self) -> None:
        """Both feeds present → CitiBikeStation returned correctly."""
        import config
        with patch.object(config, "CITIBIKE_STATION_IDS", ["3279"]):
            responses = [
                _mock_response(self._info_payload()),
                _mock_response(self._status_payload()),
            ]
            with patch("fetchers.citibike.requests.get", side_effect=responses):
                from fetchers.citibike import fetch_citibike, CitiBikeStation
                result = fetch_citibike()

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        st = result[0]
        self.assertIsInstance(st, CitiBikeStation)
        self.assertEqual(st.station_id, "3279")
        self.assertEqual(st.bikes_available, 12)
        self.assertEqual(st.ebikes_available, 3)
        self.assertEqual(st.docks_available, 8)
        self.assertTrue(st.is_renting)

    def test_station_offline(self) -> None:
        """is_renting=False propagates to the dataclass."""
        import config
        with patch.object(config, "CITIBIKE_STATION_IDS", ["3279"]):
            responses = [
                _mock_response(self._info_payload()),
                _mock_response(self._status_payload(is_renting=False)),
            ]
            with patch("fetchers.citibike.requests.get", side_effect=responses):
                from fetchers.citibike import fetch_citibike
                result = fetch_citibike()

        self.assertFalse(result[0].is_renting)

    def test_network_error_returns_stale(self) -> None:
        """A network failure returns the in-module cached list."""
        import fetchers.citibike as mod
        from fetchers.citibike import CitiBikeStation

        stale = [
            CitiBikeStation(
                station_id="3279",
                name="Cached",
                bikes_available=5,
                ebikes_available=0,
                docks_available=10,
                is_renting=True,
            )
        ]
        mod._cache = stale

        from requests import RequestException
        with patch("fetchers.citibike.requests.get", side_effect=RequestException("no wifi")):
            result = mod.fetch_citibike()

        self.assertEqual(result, stale)

    def test_empty_stations_list(self) -> None:
        """Feed with no stations returns an empty list, not an exception."""
        import config
        empty = {"data": {"stations": []}}
        with patch.object(config, "CITIBIKE_STATION_IDS", ["9999"]):
            with patch("fetchers.citibike.requests.get", side_effect=[
                _mock_response(empty),
                _mock_response(empty),
            ]):
                from fetchers.citibike import fetch_citibike
                result = fetch_citibike()

        self.assertIsNotNone(result)
        self.assertEqual(result, [])

    def test_malformed_json_returns_none(self) -> None:
        """Completely missing 'data' key returns None without raising."""
        with patch("fetchers.citibike.requests.get", side_effect=[
            _mock_response({"wrong": "shape"}),
            _mock_response({"wrong": "shape"}),
        ]):
            from fetchers.citibike import fetch_citibike
            import fetchers.citibike as mod
            mod._cache = None
            result = fetch_citibike()

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Subway fetcher tests
# ---------------------------------------------------------------------------


class TestSubwayFetcher(unittest.TestCase):
    """Tests for fetchers.subway.fetch_subway."""

    def setUp(self) -> None:
        import fetchers.subway as mod
        mod._cache = None

    def _make_feed_bytes(self, stop_id: str, route_id: str, arrival_offset: int) -> bytes:
        """Build a minimal valid GTFS-RT binary feed with one arrival."""
        from google.transit import gtfs_realtime_pb2

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(time.time())

        entity = feed.entity.add()
        entity.id = "test_entity"

        trip = entity.trip_update.trip
        trip.route_id = route_id
        trip.trip_id = "test_trip"

        stu = entity.trip_update.stop_time_update.add()
        stu.stop_id = stop_id
        stu.arrival.time = int(time.time()) + arrival_offset

        return feed.SerializeToString()

    def test_arrival_parsing(self) -> None:
        """A valid GTFS-RT feed returns the correct SubwayArrival."""
        import config
        with patch.object(config, "SUBWAY_STOP_ID", "120S"):
            feed_bytes = self._make_feed_bytes("120S", "1", 300)  # 5 min away
            with patch(
                "fetchers.subway.requests.get",
                return_value=_mock_response(content=feed_bytes),
            ):
                from fetchers.subway import fetch_subway, SubwayArrival
                result = fetch_subway()

        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        arr = result[0]
        self.assertIsInstance(arr, SubwayArrival)
        self.assertEqual(arr.route_id, "1")
        self.assertEqual(arr.direction, "Downtown")  # "S" suffix
        self.assertGreaterEqual(arr.minutes_away, 4)
        self.assertLessEqual(arr.minutes_away, 6)

    def test_wrong_stop_filtered_out(self) -> None:
        """Arrivals for a different stop ID are excluded."""
        import config
        with patch.object(config, "SUBWAY_STOP_ID", "120S"):
            feed_bytes = self._make_feed_bytes("999N", "2", 120)
            with patch(
                "fetchers.subway.requests.get",
                return_value=_mock_response(content=feed_bytes),
            ):
                from fetchers.subway import fetch_subway
                result = fetch_subway()

        self.assertIsNotNone(result)
        self.assertEqual(result, [])

    def test_direction_northbound(self) -> None:
        """Stop IDs ending in 'N' produce direction 'Uptown'."""
        import config
        with patch.object(config, "SUBWAY_STOP_ID", "120N"):
            feed_bytes = self._make_feed_bytes("120N", "2", 120)
            with patch(
                "fetchers.subway.requests.get",
                return_value=_mock_response(content=feed_bytes),
            ):
                from fetchers.subway import fetch_subway
                result = fetch_subway()

        self.assertIsNotNone(result)
        for arr in result:
            self.assertEqual(arr.direction, "Uptown")

    def test_network_error_returns_stale(self) -> None:
        """A network error returns stale cached arrivals."""
        import fetchers.subway as mod
        from fetchers.subway import SubwayArrival

        stale = [
            SubwayArrival(
                route_id="1",
                minutes_away=8,
                direction="Downtown",
                headsign="South Ferry",
            )
        ]
        mod._cache = stale

        from requests import RequestException
        with patch("fetchers.subway.requests.get", side_effect=RequestException("timeout")):
            result = mod.fetch_subway()

        self.assertEqual(result, stale)

    def test_http_error_returns_none_on_first_call(self) -> None:
        """HTTP error on first call returns None (no cache)."""
        with patch(
            "fetchers.subway.requests.get",
            return_value=_mock_response(status_code=401),
        ):
            import fetchers.subway as mod
            mod._cache = None
            result = mod.fetch_subway()

        self.assertIsNone(result)

    def test_past_arrivals_excluded(self) -> None:
        """Arrivals whose time is in the past are not included."""
        import config
        with patch.object(config, "SUBWAY_STOP_ID", "120S"):
            feed_bytes = self._make_feed_bytes("120S", "3", -60)  # 60 s in the past
            with patch(
                "fetchers.subway.requests.get",
                return_value=_mock_response(content=feed_bytes),
            ):
                from fetchers.subway import fetch_subway
                result = fetch_subway()

        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Calendar fetcher tests
# ---------------------------------------------------------------------------


class TestCalendarFetcher(unittest.TestCase):
    """Tests for fetchers.calendar.fetch_calendar.

    The Google API client is fully mocked here; no real OAuth is performed.
    """

    def setUp(self) -> None:
        import fetchers.calendar as mod
        mod._cache = None

    def _mock_credentials(self) -> MagicMock:
        creds = MagicMock()
        creds.valid = True
        creds.expired = False
        creds.refresh_token = None
        return creds

    def _make_event(
        self,
        summary: str,
        start: str,
        end: str,
        is_all_day: bool = False,
    ) -> dict:
        if is_all_day:
            return {
                "summary": summary,
                "start": {"date": start},
                "end": {"date": end},
            }
        return {
            "summary": summary,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }

    def test_successful_fetch_returns_events(self) -> None:
        """Well-formed Google API response returns CalendarEvent list."""
        events_payload = {
            "items": [
                self._make_event(
                    "Standup",
                    "2026-03-29T09:00:00-04:00",
                    "2026-03-29T09:30:00-04:00",
                ),
                self._make_event(
                    "Dentist",
                    "2026-03-29T11:30:00-04:00",
                    "2026-03-29T12:30:00-04:00",
                ),
            ]
        }

        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = events_payload

        with patch("fetchers.calendar._load_credentials", return_value=self._mock_credentials()):
            with patch("fetchers.calendar.build", return_value=mock_service):
                from fetchers.calendar import fetch_calendar, CalendarEvent
                result = fetch_calendar()

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], CalendarEvent)
        self.assertEqual(result[0].title, "Standup")
        self.assertFalse(result[0].is_all_day)

    def test_all_day_event_parsed(self) -> None:
        """All-day events (date format) set is_all_day=True."""
        events_payload = {
            "items": [
                self._make_event("Holiday", "2026-03-29", "2026-03-30", is_all_day=True)
            ]
        }

        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = events_payload

        with patch("fetchers.calendar._load_credentials", return_value=self._mock_credentials()):
            with patch("fetchers.calendar.build", return_value=mock_service):
                from fetchers.calendar import fetch_calendar
                result = fetch_calendar()

        self.assertIsNotNone(result)
        self.assertTrue(result[0].is_all_day)

    def test_empty_calendar_returns_empty_list(self) -> None:
        """No events in the API response returns an empty list, not None."""
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {"items": []}

        with patch("fetchers.calendar._load_credentials", return_value=self._mock_credentials()):
            with patch("fetchers.calendar.build", return_value=mock_service):
                from fetchers.calendar import fetch_calendar
                result = fetch_calendar()

        self.assertIsNotNone(result)
        self.assertEqual(result, [])

    def test_api_exception_returns_stale_cache(self) -> None:
        """An API exception returns the previously cached data."""
        import fetchers.calendar as mod
        from fetchers.calendar import CalendarEvent
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/New_York")
        stale = [
            CalendarEvent(
                title="Old event",
                start_time=datetime(2026, 3, 29, 9, 0, tzinfo=tz),
                end_time=datetime(2026, 3, 29, 10, 0, tzinfo=tz),
                is_all_day=False,
                location=None,
            )
        ]
        mod._cache = stale

        with patch(
            "fetchers.calendar._load_credentials",
            side_effect=Exception("API down"),
        ):
            result = mod.fetch_calendar()

        self.assertEqual(result, stale)

    def test_credentials_missing_returns_none(self) -> None:
        """Missing credentials.json returns None without crashing."""
        import fetchers.calendar as mod
        mod._cache = None

        with patch(
            "fetchers.calendar._load_credentials",
            side_effect=FileNotFoundError("credentials.json"),
        ):
            result = mod.fetch_calendar()

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
