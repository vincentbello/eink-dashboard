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
_HEADER_HEIGHT = 30
_ROW_PAD = 4
_LEFT_PAD = 10
_TIME_COL_WIDTH = 72   # pixels reserved for the time label


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
        row_height = self._text_height(self.fonts.md) + _ROW_PAD
        y = r.y + _HEADER_HEIGHT + 6

        max_title_width = r.w - _LEFT_PAD - _TIME_COL_WIDTH - 8

        for event in data:
            if y + row_height > r.y2:
                break  # region full

            time_str = self._format_time(event)
            title = self.truncate_text(event.title, self.fonts.md, max_title_width)

            # Time label (small, right-aligned within its column)
            time_x = r.x + _LEFT_PAD
            time_font = self.fonts.sm
            self.draw_text(time_x, y + 2, time_str, time_font)

            # Event title
            title_x = r.x + _LEFT_PAD + _TIME_COL_WIDTH
            self.draw_text(title_x, y, title, self.fonts.md)

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
