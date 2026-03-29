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
_HEADER_HEIGHT = 30
_LEFT_PAD = 10
_ROW_GAP = 8
_NAME_COL_WIDTH = 240   # pixels for station name column
_BIKES_COL_WIDTH = 200  # pixels for bikes column


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
        y = r.y + _HEADER_HEIGHT + 8

        for station in data:
            if y + row_height > r.y2:
                break

            if not station.is_renting:
                # Station offline — show name + warning.
                name = self.truncate_text(station.name, self.fonts.md, _NAME_COL_WIDTH)
                self.draw_text(x, y, name, self.fonts.md)
                offline_x = x + _NAME_COL_WIDTH + 10
                self.draw_text(offline_x, y, "Station offline", self.fonts.sm)
            else:
                # Name column
                name = self.truncate_text(station.name, self.fonts.md, _NAME_COL_WIDTH)
                self.draw_text(x, y, name, self.fonts.md)

                # Bikes column
                bikes_str = self._format_bikes(station)
                bikes_x = x + _NAME_COL_WIDTH + 10
                self.draw_text(bikes_x, y, bikes_str, self.fonts.md)

                # Docks column
                docks_str = f"P {station.docks_available} docks"
                docks_x = bikes_x + _BIKES_COL_WIDTH
                self.draw_text(docks_x, y, docks_str, self.fonts.md)

            y += row_height

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
