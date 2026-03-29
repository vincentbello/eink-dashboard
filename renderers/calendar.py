"""
renderers/calendar.py — Draws today's calendar events in the CALENDAR region.

Layout (400 × 220 px):
  ┌─────────────────────────────┐
  │  CALENDAR  (header)         │
  │  ─────────────────────────  │
  │  9:00 AM  Standup           │
  │  11:30 AM Dentist           │
  │  2:00 PM  Design review     │
  │  …                          │
  └─────────────────────────────┘
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import ImageDraw

from display.layout import FontSet, Region
from fetchers.calendar import CalendarEvent
from renderers.base import BaseRenderer

logger = logging.getLogger(__name__)

_SECTION_HEADER = "CALENDAR"
_HEADER_HEIGHT = 38
_ROW_PAD = 4
_LEFT_PAD = 10
_TIME_COL_WIDTH = 96   # pixels reserved for the time label
_TIME_TITLE_GAP = 10  # gap between time and event title


class CalendarRenderer(BaseRenderer):
    """Renders today's calendar events into the CALENDAR region."""

    def __init__(self, draw: ImageDraw.ImageDraw, region: Region, fonts: FontSet) -> None:
        super().__init__(draw, region, fonts)

    def render(self, data: Optional[list[CalendarEvent]]) -> None:
        """Draw up to :data:`~config.NUM_CALENDAR_EVENTS` events.

        Args:
            data: List of :class:`~fetchers.calendar.CalendarEvent` objects,
                  or ``None`` if no data is available.
        """
        self.fill_region()

        r = self.region
        x = r.x + _LEFT_PAD

        # ── Section header ────────────────────────────────────────────
        self.draw_text(x, r.y + 6, _SECTION_HEADER, self.fonts.lg)
        self.draw_divider(_HEADER_HEIGHT)

        if data is None:
            self.draw_text(
                x,
                r.y + _HEADER_HEIGHT + 10,
                "Calendar unavailable",
                self.fonts.sm,
            )
            return

        if not data:
            # Use smaller font and slight indentation for the empty state.
            self.draw_text(
                x,
                r.y + _HEADER_HEIGHT + 12,
                "No events today",
                self.fonts.sm,
            )
            return

        # ── Event rows ────────────────────────────────────────────────
        md_h = self._text_height(self.fonts.md)
        sm_h = self._text_height(self.fonts.sm)
        row_height = md_h + _ROW_PAD
        y = r.y + _HEADER_HEIGHT + 40

        time_x = r.x + _LEFT_PAD
        title_x = r.x + _LEFT_PAD + _TIME_COL_WIDTH + _TIME_TITLE_GAP

        for event in data:
            if y + row_height > r.y2:
                break  # region full

            time_str = self._format_time(event)
            dur_str = self._format_duration(event)

            # Right-align duration; title truncated so it doesn't collide.
            if dur_str:
                dur_w = self._text_width(dur_str, self.fonts.sm)
                dur_x = r.x2 - _LEFT_PAD - dur_w
                max_title_width = dur_x - title_x - 8
            else:
                dur_x = None
                max_title_width = r.x2 - title_x - _LEFT_PAD

            title = self.truncate_text(event.title, self.fonts.md, max_title_width)

            # Time label (small font)
            self.draw_text(time_x, y + 2, time_str, self.fonts.sm)

            # Event title
            self.draw_text(title_x, y, title, self.fonts.md)

            # Duration (right-aligned, vertically centred with title)
            if dur_x is not None:
                dur_y = y + (md_h - sm_h) // 2 + 2
                self.draw_text(dur_x, dur_y, dur_str, self.fonts.sm)

            y += row_height

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_time(event: CalendarEvent) -> str:
        """Return a short time string for an event.

        Returns "All day" for all-day events, or a 12-hour formatted time
        (e.g. "9:00 AM") for timed events.
        """
        if event.is_all_day:
            return "All day"
        return event.start_time.strftime("%-I:%M %p")

    @staticmethod
    def _format_duration(event: CalendarEvent) -> str:
        """Return a compact duration string, e.g. '30m', '1h', '1h 30m'.

        Returns an empty string for all-day events or zero-duration events.
        """
        if event.is_all_day:
            return ""
        delta = event.end_time - event.start_time
        total_minutes = round(delta.total_seconds() / 60)
        if total_minutes <= 0:
            return ""
        hours = total_minutes // 60
        mins = total_minutes % 60
        if hours == 0:
            return f"{mins}m"
        if mins == 0:
            return f"{hours}h"
        return f"{hours}h {mins}m"
