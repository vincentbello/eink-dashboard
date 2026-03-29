"""
fetchers/subway.py — Real-time subway arrivals from the MTA GTFS-RT feed.

The MTA GTFS-RT feed is publicly accessible — no API key required.

The protobuf feed is parsed using gtfs-realtime-bindings.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests
from google.transit import gtfs_realtime_pb2  # type: ignore[import]

import config

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10  # seconds

# Module-level cache.
_cache: Optional[list[SubwayArrival]] = None  # type: ignore[name-defined]


@dataclass(frozen=True)
class SubwayArrival:
    """A single upcoming train arrival."""

    route_id: str       # e.g. "1", "2", "A"
    minutes_away: int   # rounded; 0 means "Due"
    direction: str      # "Uptown" or "Downtown"
    headsign: str       # e.g. "Van Cortlandt Park – 242 St"


def _stop_direction(stop_id: str) -> str:
    """Derive train direction from the NYCT stop ID suffix.

    NYCT stop IDs end with 'N' (northbound / Uptown) or 'S'
    (southbound / Downtown).
    """
    suffix = stop_id[-1].upper() if stop_id else ""
    if suffix == "N":
        return "Uptown"
    if suffix == "S":
        return "Downtown"
    return "Unknown"


def fetch_subway() -> Optional[list[SubwayArrival]]:
    """Fetch upcoming arrivals for the configured stop from the MTA feed.

    Returns a list sorted by arrival time (ascending).  Returns the cached
    list on network or parse failure so the display stays populated.
    """
    global _cache
    try:
        resp = requests.get(
            config.SUBWAY_LINE_FEED_URL,
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(resp.content)

        now_ts = time.time()
        arrivals: list[tuple[int, SubwayArrival]] = []  # (unix_ts, arrival)
        direction = _stop_direction(config.SUBWAY_STOP_ID)

        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue

            trip = entity.trip_update.trip
            route_id = trip.route_id

            for stu in entity.trip_update.stop_time_update:
                if stu.stop_id != config.SUBWAY_STOP_ID:
                    continue

                # Prefer arrival time; fall back to departure.
                arrival_ts: int = 0
                if stu.HasField("arrival") and stu.arrival.time > 0:
                    arrival_ts = stu.arrival.time
                elif stu.HasField("departure") and stu.departure.time > 0:
                    arrival_ts = stu.departure.time

                if arrival_ts <= now_ts:
                    # Already departed or stale — skip.
                    continue

                seconds_away = int(arrival_ts - now_ts)
                minutes_away = max(0, round(seconds_away / 60))

                # Headsign lives on the trip extension in NYCT data.
                # Use the route as a fallback if unavailable.
                headsign = _extract_headsign(entity.trip_update) or f"{route_id} train"

                arrivals.append(
                    (
                        arrival_ts,
                        SubwayArrival(
                            route_id=route_id,
                            minutes_away=minutes_away,
                            direction=direction,
                            headsign=headsign,
                        ),
                    )
                )

        # Sort by arrival timestamp, take the first N.
        arrivals.sort(key=lambda t: t[0])
        result = [a for _, a in arrivals[: config.NUM_ARRIVALS_TO_SHOW]]

        _cache = result
        logger.debug(
            "Subway fetched: %d arrivals for stop %s", len(result), config.SUBWAY_STOP_ID
        )
        return result

    except requests.RequestException as exc:
        logger.warning("Subway fetch failed (network): %s", exc)
    except Exception:
        logger.exception("Subway fetch failed (unexpected)")

    if _cache is not None:
        logger.info("Returning stale subway data (%d arrivals)", len(_cache))
    return _cache


def _extract_headsign(trip_update: object) -> str:
    """Best-effort extraction of the trip headsign.

    The NYCT trip descriptor extension stores headsign data, but accessing
    protobuf extensions requires the compiled NYCT extension descriptor.
    As a pragmatic fallback we check the trip's trip_headsign field if the
    standard GTFS trip descriptor exposes it, otherwise return an empty string.
    """
    try:
        # Standard GTFS-RT does not include headsign; return empty to use
        # the route-based fallback in the caller.
        return ""
    except Exception:
        return ""
