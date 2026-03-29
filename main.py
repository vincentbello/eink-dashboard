"""
main.py — Entry point and main refresh loop for the e-ink dashboard.

Run directly:
    python main.py

Or via the systemd service installed by scripts/setup.sh.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

import config
from display import (
    EPDDriver,
    load_fonts,
    HEADER_TIME,
    HEADER_DATE,
    HEADER_WEATHER,
    CALENDAR,
    SUBWAY,
    CITIBIKE,
)
from display.layout import FontSet, Region
from fetchers import (
    WeatherData, fetch_weather,
    CalendarEvent, fetch_calendar,
    SubwayArrival, fetch_subway,
    CitiBikeStation, fetch_citibike,
)
from renderers import (
    WeatherRenderer,
    CalendarRenderer,
    SubwayRenderer,
    CitiBikeRenderer,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canvas helpers
# ---------------------------------------------------------------------------


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Create a fresh white 1-bit canvas sized for the configured display.

    Returns:
        A ``(Image, ImageDraw)`` tuple ready for rendering.
    """
    img = Image.new(
        "L",  # 8-bit greyscale; we convert to 1-bit before pushing to panel
        (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT),
        color=255,  # white
    )
    return img, ImageDraw.Draw(img)


# ---------------------------------------------------------------------------
# Header rendering (time + date)
# ---------------------------------------------------------------------------


def _render_header_time_date(
    draw: ImageDraw.ImageDraw,
    fonts: FontSet,
    now: datetime,
) -> None:
    """Draw the clock and date into the left/centre header sub-regions.

    Args:
        draw:  ImageDraw for the full canvas.
        fonts: Pre-loaded FontSet.
        now:   Current local datetime.
    """
    # Time  – e.g. "9:42 AM"
    time_str = now.strftime("%-I:%M %p")
    r = HEADER_TIME
    draw.text(
        (r.x + 10, r.y + (r.h - fonts.xl.size) // 2 - 3),  # type: ignore[attr-defined]
        time_str,
        font=fonts.xl,
        fill=0,
    )

    # Date  – e.g. "Sun, Mar 29"
    date_str = now.strftime("%a, %b %-d")
    r = HEADER_DATE
    draw.text(
        (r.x + 8, r.y + (r.h - fonts.lg.size) // 2 - 3),  # type: ignore[attr-defined]
        date_str,
        font=fonts.lg,
        fill=0,
    )


# ---------------------------------------------------------------------------
# Full render
# ---------------------------------------------------------------------------


def render_full(
    driver: EPDDriver,
    fonts: FontSet,
    weather: Optional[WeatherData],
    calendar: Optional[list[CalendarEvent]],
    subway: Optional[list[SubwayArrival]],
    citibike: Optional[list[CitiBikeStation]],
) -> None:
    """Compose the full screen image and push it to the display.

    Draws all four data sections plus the time/date header.

    Args:
        driver:   Initialised :class:`~display.EPDDriver`.
        fonts:    Pre-loaded :class:`~display.layout.FontSet`.
        weather:  Latest weather data (may be ``None``).
        calendar: Latest calendar events (may be ``None``).
        subway:   Latest subway arrivals (may be ``None``).
        citibike: Latest Citi Bike station data (may be ``None``).
    """
    img, draw = _new_canvas()
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)

    _render_header_time_date(draw, fonts, now)
    _draw_dividers(draw)

    WeatherRenderer(draw, HEADER_WEATHER, fonts).render(weather)
    CalendarRenderer(draw, CALENDAR, fonts).render(calendar)
    SubwayRenderer(draw, SUBWAY, fonts).render(subway)
    CitiBikeRenderer(draw, CITIBIKE, fonts).render(citibike)

    driver.wake()
    driver.full_refresh(img)
    logger.info("Full refresh complete")


# ---------------------------------------------------------------------------
# Partial (transit-only) render
# ---------------------------------------------------------------------------


def render_partial_transit(
    driver: EPDDriver,
    fonts: FontSet,
    subway: Optional[list[SubwayArrival]],
    citibike: Optional[list[CitiBikeStation]],
    last_full_image: Image.Image,
) -> None:
    """Re-draw only the transit regions and push a full-image refresh.

    We re-use the last full image as the base so unchanged sections (weather,
    calendar, time) remain visible.  The time in the header is also updated.

    Args:
        driver:          Initialised :class:`~display.EPDDriver`.
        fonts:           Pre-loaded :class:`~display.layout.FontSet`.
        subway:          Latest subway arrivals.
        citibike:        Latest Citi Bike station data.
        last_full_image: The previous full-screen PIL image to build on.
    """
    img = last_full_image.copy()
    draw = ImageDraw.Draw(img)
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)

    # Refresh the clock in place.
    _clear_region(draw, HEADER_TIME)
    _clear_region(draw, HEADER_DATE)
    _render_header_time_date(draw, fonts, now)

    SubwayRenderer(draw, SUBWAY, fonts).render(subway)
    CitiBikeRenderer(draw, CITIBIKE, fonts).render(citibike)

    driver.wake()
    driver.partial_refresh(img, SUBWAY)
    logger.info("Partial (transit) refresh complete")


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _draw_dividers(draw: ImageDraw.ImageDraw) -> None:
    """Draw structural dividing lines between the screen regions."""
    w = config.DISPLAY_WIDTH

    # Horizontal line below the header
    draw.line([(0, HEADER_TIME.h), (w, HEADER_TIME.h)], fill=0, width=1)

    # Vertical line between calendar and subway
    mid_x = CALENDAR.x2
    mid_y_top = CALENDAR.y
    mid_y_bot = CALENDAR.y2
    draw.line([(mid_x, mid_y_top), (mid_x, mid_y_bot)], fill=0, width=1)

    # Horizontal line above Citi Bike
    draw.line([(0, CITIBIKE.y), (w, CITIBIKE.y)], fill=0, width=1)


def _clear_region(draw: ImageDraw.ImageDraw, region: Region) -> None:
    """Flood-fill *region* with white to prepare for a re-draw."""
    draw.rectangle(
        [(region.x, region.y), (region.x2 - 1, region.y2 - 1)],
        fill=255,
    )


# ---------------------------------------------------------------------------
# Fetch helpers (with per-fetcher try/except isolation)
# ---------------------------------------------------------------------------


def _safe_fetch_weather() -> Optional[WeatherData]:
    """Fetch weather, returning ``None`` on any unhandled exception."""
    try:
        return fetch_weather()
    except Exception:
        logger.exception("Unhandled error in fetch_weather")
        return None


def _safe_fetch_calendar() -> Optional[list[CalendarEvent]]:
    """Fetch calendar events, returning ``None`` on any unhandled exception."""
    try:
        return fetch_calendar()
    except Exception:
        logger.exception("Unhandled error in fetch_calendar")
        return None


def _safe_fetch_subway() -> Optional[list[SubwayArrival]]:
    """Fetch subway arrivals, returning ``None`` on any unhandled exception."""
    try:
        return fetch_subway()
    except Exception:
        logger.exception("Unhandled error in fetch_subway")
        return None


def _safe_fetch_citibike() -> Optional[list[CitiBikeStation]]:
    """Fetch Citi Bike data, returning ``None`` on any unhandled exception."""
    try:
        return fetch_citibike()
    except Exception:
        logger.exception("Unhandled error in fetch_citibike")
        return None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    """Initialise the display and run the refresh loop indefinitely.

    Two refresh cadences:
      - Full refresh  (weather + calendar + transit): every FULL_REFRESH_INTERVAL s
      - Transit-only  (subway + Citi Bike):           every TRANSIT_REFRESH_INTERVAL s

    Each fetcher is isolated so a failure in one never crashes the loop.
    """
    logger.info(
        "Dashboard starting — mock=%s, display=%dx%d",
        config.MOCK_MODE,
        config.DISPLAY_WIDTH,
        config.DISPLAY_HEIGHT,
    )

    driver = EPDDriver()
    driver.init()
    fonts = load_fonts()

    last_full_refresh: float = 0.0
    last_transit_refresh: float = 0.0

    # Cached data — kept across iterations so a failed refresh doesn't
    # blank the display.
    weather_data: Optional[WeatherData] = None
    calendar_data: Optional[list[CalendarEvent]] = None
    subway_data: Optional[list[SubwayArrival]] = None
    citibike_data: Optional[list[CitiBikeStation]] = None

    # The last rendered full image, used as the base for partial refreshes.
    last_image: Optional[Image.Image] = None

    while True:
        now = time.monotonic()
        needs_full = (now - last_full_refresh) >= config.FULL_REFRESH_INTERVAL
        needs_transit = (now - last_transit_refresh) >= config.TRANSIT_REFRESH_INTERVAL

        if needs_full:
            logger.info("Running full refresh")
            weather_data = _safe_fetch_weather() or weather_data
            calendar_data = _safe_fetch_calendar() or calendar_data
            subway_data = _safe_fetch_subway() or subway_data
            citibike_data = _safe_fetch_citibike() or citibike_data

            # Build the image so we have it for partial refreshes.
            img, draw = _new_canvas()
            tz = ZoneInfo(config.TIMEZONE)
            _render_header_time_date(draw, fonts, datetime.now(tz))
            _draw_dividers(draw)
            WeatherRenderer(draw, HEADER_WEATHER, fonts).render(weather_data)
            CalendarRenderer(draw, CALENDAR, fonts).render(calendar_data)
            SubwayRenderer(draw, SUBWAY, fonts).render(subway_data)
            CitiBikeRenderer(draw, CITIBIKE, fonts).render(citibike_data)
            last_image = img

            driver.wake()
            driver.full_refresh(img)

            last_full_refresh = now
            last_transit_refresh = now

        elif needs_transit:
            logger.info("Running transit-only refresh")
            subway_data = _safe_fetch_subway() or subway_data
            citibike_data = _safe_fetch_citibike() or citibike_data

            if last_image is not None:
                render_partial_transit(
                    driver, fonts, subway_data, citibike_data, last_image
                )
            else:
                # No prior image — fall back to a full refresh.
                render_full(driver, fonts, weather_data, calendar_data, subway_data, citibike_data)
                last_full_refresh = now

            last_transit_refresh = now

        time.sleep(10)  # poll every 10 s; intervals decide what actually executes


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user (KeyboardInterrupt)")
        sys.exit(0)
    except Exception:
        logger.exception("Fatal error in main loop")
        sys.exit(1)
