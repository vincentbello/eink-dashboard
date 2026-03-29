"""
config.py — All user-facing configuration in one place.

Edit this file to customise the dashboard for your location and services.
No hardcoded values should exist anywhere else in the codebase.
"""

import os

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------
LATITUDE: float = 40.71771557633474
LONGITUDE: float = -73.95739191241212
TIMEZONE: str = "America/New_York"

# ---------------------------------------------------------------------------
# MTA Subway
# ---------------------------------------------------------------------------
# The stop ID to monitor.  Look up your stop in the MTA static GTFS stops.txt
# (see README for instructions).  The suffix is the direction:
#   N = Northbound (Uptown)   S = Southbound (Downtown)
SUBWAY_STOP_ID: str = "L08N"  # Bedford Av – L towards Manhattan
SUBWAY_STATION_LABEL: str = "Bedford Ave - Manhattan"

# GTFS-RT feed URL for the subway lines serving your stop.
SUBWAY_LINE_FEED_URL: str = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l"
)

NUM_ARRIVALS_TO_SHOW: int = 3

# ---------------------------------------------------------------------------
# Citi Bike
# ---------------------------------------------------------------------------
# Find your nearest station IDs from the GBFS feed – see README.
CITIBIKE_STATION_IDS: list[str] = [
    "1786698974100683436",                   # N 7 St & Driggs Ave
    "66dd039b-0aca-11e7-82f6-3863bb44ef7c",  # N 6 St & Bedford Ave
]

# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------
# Each entry is one Google account. Use a separate token_path per account so
# that multiple Google accounts can be authorised independently.
GOOGLE_CALENDAR_ACCOUNTS: list[dict] = [
    {
        "token_path": "token_personal.json",
        "calendar_ids": ["primary"],
    },
    {
        "token_path": "token_work.json",
        "calendar_ids": ["primary"],  # "primary" = vince@joyfulhealth.io
        "exclude_reclaim_syncs": True,
    },
]
GOOGLE_CREDENTIALS_PATH: str = "credentials.json"
NUM_CALENDAR_EVENTS: int = 5

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
DISPLAY_WIDTH: int = 800
DISPLAY_HEIGHT: int = 480

# Set to True to render to a PNG file instead of the e-ink panel.
# Useful for developing / testing on a non-Pi machine.
MOCK_MODE: bool = os.environ.get("MOCK_MODE", "0") == "1"
MOCK_OUTPUT_PATH: str = "mock_output.png"

# ---------------------------------------------------------------------------
# Refresh intervals (seconds)
# ---------------------------------------------------------------------------
TRANSIT_REFRESH_INTERVAL: int = 60        # subway + Citi Bike
FULL_REFRESH_INTERVAL: int = 900          # weather + calendar + full redraw (15 min)

# ---------------------------------------------------------------------------
# Fonts  (paths relative to the project root)
# ---------------------------------------------------------------------------
FONT_REGULAR: str = "assets/fonts/SpaceGrotesk-Regular.ttf"
FONT_BOLD: str = "assets/fonts/SpaceGrotesk-Bold.ttf"

# Font sizes (pixels)
FONT_SIZE_XL: int = 52   # clock
FONT_SIZE_LG: int = 32   # section headers, temperature
FONT_SIZE_MD: int = 24   # primary content
FONT_SIZE_SM: int = 18   # secondary content / labels

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Override at runtime via the LOG_LEVEL environment variable.
# Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
