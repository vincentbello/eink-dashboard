"""
fetchers/citibike.py — Real-time Citi Bike station data via GBFS.

No API key required.  Data is joined from two public feeds:
  - station_information.json  (static metadata: name, capacity, …)
  - station_status.json       (live counters: bikes, docks, …)

GBFS spec: https://gbfs.mobilitydata.org/specification/reference/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

_GBFS_BASE = "https://gbfs.citibikenyc.com/gbfs/en"
_STATUS_URL = f"{_GBFS_BASE}/station_status.json"
_INFO_URL = f"{_GBFS_BASE}/station_information.json"
_HTTP_TIMEOUT = 10  # seconds

# Module-level cache.
_cache: Optional[list[CitiBikeStation]] = None  # type: ignore[name-defined]


@dataclass(frozen=True)
class CitiBikeStation:
    """Live status of a single Citi Bike docking station."""

    station_id: str
    name: str
    bikes_available: int       # classic + e-bikes
    ebikes_available: int
    docks_available: int
    is_renting: bool           # False when the station is disabled


def fetch_citibike() -> Optional[list[CitiBikeStation]]:
    """Fetch live status for the configured Citi Bike stations.

    Joins station_information and station_status on station_id, then
    filters to :data:`config.CITIBIKE_STATION_IDS`.

    Returns a list ordered to match the configured IDs.  Returns the
    cached list on failure.
    """
    global _cache
    try:
        info_resp = requests.get(_INFO_URL, timeout=_HTTP_TIMEOUT)
        info_resp.raise_for_status()
        status_resp = requests.get(_STATUS_URL, timeout=_HTTP_TIMEOUT)
        status_resp.raise_for_status()

        info_by_id: dict[str, dict] = {
            str(s["station_id"]): s
            for s in info_resp.json()["data"]["stations"]
        }
        status_by_id: dict[str, dict] = {
            str(s["station_id"]): s
            for s in status_resp.json()["data"]["stations"]
        }

        target_ids = [str(sid) for sid in config.CITIBIKE_STATION_IDS]
        stations: list[CitiBikeStation] = []

        for sid in target_ids:
            info = info_by_id.get(sid)
            status = status_by_id.get(sid)

            if info is None or status is None:
                logger.warning("Citi Bike station %s not found in GBFS feed", sid)
                continue

            ebikes = int(status.get("num_ebikes_available", 0))
            bikes_total = int(status.get("num_bikes_available", 0))

            stations.append(
                CitiBikeStation(
                    station_id=sid,
                    name=info.get("name", f"Station {sid}"),
                    bikes_available=bikes_total,
                    ebikes_available=ebikes,
                    docks_available=int(status.get("num_docks_available", 0)),
                    is_renting=bool(status.get("is_renting", True)),
                )
            )

        _cache = stations
        logger.debug("Citi Bike fetched: %d stations", len(stations))
        return stations

    except requests.RequestException as exc:
        logger.warning("Citi Bike fetch failed (network): %s", exc)
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Citi Bike fetch failed (parse): %s", exc)
    except Exception:
        logger.exception("Citi Bike fetch failed (unexpected)")

    if _cache is not None:
        logger.info("Returning stale Citi Bike data (%d stations)", len(_cache))
    return _cache
