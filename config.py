"""
config.py — All user-facing configuration in one place.

Edit this file to customise the dashboard for your location and services.
No hardcoded values should exist anywhere else in the codebase.
"""

import os

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------
LATITUDE: float = 40.7128
LONGITUDE: float = -74.0060
TIMEZONE: str = "America/New_York"

# ---------------------------------------------------------------------------
# MTA Subway
# ---------------------------------------------------------------------------
MTA_API_KEY: str = os.environ.get("MTA_API_KEY", "your_mta_api_key")

# The stop ID to monitor.  Look up your stop in the MTA static GTFS stops.txt
# (see README for instructions).  The suffix is the direction:
#   N = Northbound (Uptown)   S = Southbound (Downtown)
SUBWAY_STOP_ID: str = "120S"  # Canal St – 1/2/3 southbound

# GTFS-RT feed URL for the subway lines serving your stop.
# Replace with the appropriate feed for your line:
#   1/2/3/4/5/6/7: https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs
#   A/C/E:         https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace
#   B/D/F/M:       https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm
#   G:             https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g
#   J/Z:           https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz
#   L:             https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l
#   N/Q/R/W:       https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw
#   S:             https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si
SUBWAY_LINE_FEED_URL: str = (
    "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"
)

NUM_ARRIVALS_TO_SHOW: int = 3

# ---------------------------------------------------------------------------
# Citi Bike
# ---------------------------------------------------------------------------
# Find your nearest station IDs from the GBFS feed – see README.
CITIBIKE_STATION_IDS: list[str] = ["3279", "3182"]

# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------
GOOGLE_CALENDAR_ID: str = "primary"
GOOGLE_CREDENTIALS_PATH: str = "credentials.json"
GOOGLE_TOKEN_PATH: str = "token.json"
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
FONT_REGULAR: str = "assets/fonts/DejaVuSans.ttf"
FONT_BOLD: str = "assets/fonts/DejaVuSans-Bold.ttf"

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
