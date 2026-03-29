"""
tests/mock_display.py — Render a full dashboard layout to a PNG without hardware.

Usage:
    python tests/mock_display.py

This script:
  1. Enables mock mode so no e-ink hardware is required.
  2. Fetches live data from all four external APIs.
  3. Renders the full layout to ``mock_output.png``.
  4. Prints a data summary to stdout.

Run from the project root:
    cd dashboard && python tests/mock_display.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# Force mock mode before importing config so subsequent imports pick it up.
os.environ["MOCK_MODE"] = "1"

# Add the project root to sys.path so relative imports resolve correctly.
# Also chdir there so relative asset paths (fonts, etc.) resolve correctly.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    stream=sys.stdout,
)

import config

config.MOCK_MODE = True  # belt-and-suspenders

from PIL import Image, ImageDraw

from display import load_fonts, HEADER_WEATHER, CALENDAR, SUBWAY, CITIBIKE
from display.layout import HEADER_TIME, HEADER_DATE
from display.epd_driver import EPDDriver
from fetchers import fetch_weather, fetch_calendar, fetch_subway, fetch_citibike
from renderers import WeatherRenderer, CalendarRenderer, SubwayRenderer, CitiBikeRenderer


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Create a fresh white canvas."""
    img = Image.new("L", (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT), color=255)
    return img, ImageDraw.Draw(img)


def _draw_dividers(draw: ImageDraw.ImageDraw) -> None:
    """Draw structural borders between sections."""
    w = config.DISPLAY_WIDTH
    draw.line([(0, HEADER_TIME.h), (w, HEADER_TIME.h)], fill=0, width=1)
    draw.line([(CALENDAR.x2, CALENDAR.y), (CALENDAR.x2, CALENDAR.y2)], fill=0, width=1)
    draw.line([(0, CITIBIKE.y), (w, CITIBIKE.y)], fill=0, width=1)


def main() -> None:
    """Fetch all data, render, and save to PNG."""
    print("=" * 60)
    print("  e-ink Dashboard Mock Renderer")
    print("=" * 60)

    # ── Fetch ────────────────────────────────────────────────────────
    print("\n[1/4] Fetching weather…")
    weather = fetch_weather()
    if weather:
        print(
            f"      {weather.temperature:.1f}°F  {weather.condition}"
            f"  (icon: {weather.icon_key})  wind {weather.wind_speed:.0f} mph"
        )
    else:
        print("      !! Weather fetch returned None")

    print("\n[2/4] Fetching calendar…")
    calendar = fetch_calendar()
    if calendar is not None:
        print(f"      {len(calendar)} event(s) today:")
        for ev in calendar:
            time_str = "All day" if ev.is_all_day else ev.start_time.strftime("%-I:%M %p")
            print(f"        {time_str:10s}  {ev.title}")
    else:
        print("      !! Calendar fetch returned None")

    print("\n[3/4] Fetching subway arrivals…")
    subway = fetch_subway()
    if subway is not None:
        print(f"      {len(subway)} arrival(s) for stop {config.SUBWAY_STOP_ID}:")
        for arr in subway:
            mins = "Due" if arr.minutes_away == 0 else f"{arr.minutes_away} min"
            print(f"        [{arr.route_id}]  {mins:8s}  {arr.direction}")
    else:
        print("      !! Subway fetch returned None")

    print("\n[4/4] Fetching Citi Bike status…")
    citibike = fetch_citibike()
    if citibike is not None:
        print(f"      {len(citibike)} station(s):")
        for st in citibike:
            status = f"🚲 {st.bikes_available} bikes  🅿 {st.docks_available} docks"
            if not st.is_renting:
                status = "OFFLINE"
            print(f"        {st.name:<35s}  {status}")
    else:
        print("      !! Citi Bike fetch returned None")

    # ── Render ───────────────────────────────────────────────────────
    print("\nRendering layout…")
    fonts = load_fonts()
    img, draw = _new_canvas()

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)

    # Time & date header
    time_str = now.strftime("%-I:%M %p")
    date_str = now.strftime("%a, %b %-d")
    r = HEADER_TIME
    try:
        draw.text((r.x + 10, r.y + (r.h - fonts.xl.size) // 2 - 3), time_str, font=fonts.xl, fill=0)  # type: ignore[attr-defined]
    except Exception:
        draw.text((r.x + 10, r.y + 10), time_str, font=fonts.xl, fill=0)

    r = HEADER_DATE
    try:
        draw.text((r.x + 8, r.y + (r.h - fonts.lg.size) // 2 - 3), date_str, font=fonts.lg, fill=0)  # type: ignore[attr-defined]
    except Exception:
        draw.text((r.x + 8, r.y + 10), date_str, font=fonts.lg, fill=0)

    _draw_dividers(draw)

    WeatherRenderer(draw, HEADER_WEATHER, fonts).render(weather)
    CalendarRenderer(draw, CALENDAR, fonts).render(calendar)
    SubwayRenderer(draw, SUBWAY, fonts).render(subway)
    CitiBikeRenderer(draw, CITIBIKE, fonts).render(citibike)

    # ── Save ─────────────────────────────────────────────────────────
    driver = EPDDriver()
    driver.full_refresh(img)  # In mock mode this saves the PNG.

    print(f"\nOutput saved → {config.MOCK_OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
