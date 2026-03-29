"""
renderers/citibike.py — Draws Citi Bike station status in the CITIBIKE region.

Layout (800 × 180 px):
  ┌──────────────────────────────────────────────────────────────────┐
  │  CITI BIKE  (header)                                             │
  │  ────────────────────────────────────────────────────────────── │
  │  Varick & Vandam     🚲 12 bikes (3 e)     🅿 4 docks           │
  │  King & 6th Ave      🚲 3 bikes             🅿 11 docks         │
  └──────────────────────────────────────────────────────────────────┘

Unicode icons are replaced with short ASCII labels for maximum e-ink
font compatibility.
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import ImageDraw

from display.layout import FontSet, Region
from fetchers.citibike import CitiBikeStation
from renderers.base import BaseRenderer

logger = logging.getLogger(__name__)

_SECTION_HEADER = "CITI BIKE"
_HEADER_HEIGHT = 38
_LEFT_PAD = 10
_ROW_GAP = 8


class CitiBikeRenderer(BaseRenderer):
    """Renders Citi Bike station status into the CITIBIKE region."""

    def __init__(self, draw: ImageDraw.ImageDraw, region: Region, fonts: FontSet) -> None:
        super().__init__(draw, region, fonts)

    def render(self, data: Optional[list[CitiBikeStation]]) -> None:
        """Draw station availability rows.

        Args:
            data: List of :class:`~fetchers.citibike.CitiBikeStation` objects,
                  or ``None`` if no data is available.
        """
        self.fill_region()

        r = self.region
        x = r.x + _LEFT_PAD

        # ── Section header ────────────────────────────────────────────
        self.draw_text(x, r.y + 6, _SECTION_HEADER, self.fonts.lg)
        self.draw_divider(_HEADER_HEIGHT)

        if data is None:
            self.draw_text(x, r.y + _HEADER_HEIGHT + 10, "Citi Bike unavailable", self.fonts.sm)
            return

        if not data:
            self.draw_text(x, r.y + _HEADER_HEIGHT + 10, "No stations configured", self.fonts.sm)
            return

        # ── Station rows ──────────────────────────────────────────────
        row_height = self._text_height(self.fonts.md) + _ROW_GAP
        y = r.y + _HEADER_HEIGHT + 20

        for station in data:
            if y + row_height > r.y2:
                break

            if not station.is_renting:
                avail_str = "Station offline"
            else:
                bikes_str = self._format_bikes(station)
                dock_str = f"P {station.docks_available} dock"
                avail_str = f"{bikes_str}  {dock_str}"

            # Right-aligned availability string
            avail_w = self._text_width(avail_str, self.fonts.md)
            avail_x = r.x2 - _LEFT_PAD - avail_w

            # Left-aligned name, truncated so it doesn't collide with avail
            max_name_w = avail_x - x - 16
            name = self.truncate_text(station.name, self.fonts.md, max_name_w)
            self.draw_text(x, y, name, self.fonts.md)
            self.draw_text(avail_x, y, avail_str, self.fonts.md)

            y += row_height

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _draw_bike_icon(self, x: int, y: int, size: int) -> None:
        """Draw a minimal bicycle icon using PIL primitives.

        Two wheels, a frame triangle, seat, and handlebars — all in a
        *size* × *size* bounding box with top-left at (x, y).
        """
        w = 3          # line width
        r_wheel = size // 2 - 1
        # Wheel centres
        lx = x + r_wheel
        rx = x + size - r_wheel
        cy = y + size - r_wheel  # both wheels share the same vertical centre

        # Wheels
        self.draw.ellipse([(lx - r_wheel, cy - r_wheel), (lx + r_wheel, cy + r_wheel)], outline=0, width=w - 1)
        self.draw.ellipse([(rx - r_wheel, cy - r_wheel), (rx + r_wheel, cy + r_wheel)], outline=0, width=w - 1)

        # Frame: rear axle → seat post → head tube → front axle
        seat_x = lx + size // 5
        seat_y = y + size // 4
        self.draw.line([(lx, cy), (seat_x, seat_y)], fill=0, width=w)   # seat tube
        self.draw.line([(seat_x, seat_y), (rx, cy)], fill=0, width=w)   # down tube
        self.draw.line([(lx, cy), (rx, cy - size // 5)], fill=0, width=w)  # chain stay / top tube

        # Seat
        self.draw.line([(seat_x - 3, seat_y), (seat_x + 4, seat_y)], fill=0, width=w)

        # Handlebars
        bar_x = rx
        bar_y = cy - size // 5
        self.draw.line([(bar_x - 2, bar_y - 4), (bar_x + 3, bar_y - 4)], fill=0, width=w)

    @staticmethod
    def _format_bikes(station: CitiBikeStation) -> str:
        """Return a human-readable bikes-available string.

        Shows e-bike count in parentheses when non-zero:
          "12 bikes (3e)" or "5 bikes"
        """
        total = station.bikes_available
        ebikes = station.ebikes_available
        if ebikes > 0:
            return f"B {total} bikes ({ebikes}e)"
        return f"B {total} bikes"
