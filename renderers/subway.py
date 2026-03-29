"""
renderers/subway.py — Draws subway arrivals in the SUBWAY region.

Layout (400 × 220 px):
  ┌──────────────────────────────────────────┐
  │  SUBWAY  (header)                        │
  │  ──────────────────────────────────────  │
  │  Canal St · Downtown                     │
  │  [1]  Due                                │
  │  [2]  7 min                              │
  │  [3]  12 min                             │
  └──────────────────────────────────────────┘

Route bullet: white text on black filled rounded rectangle, mimicking
the MTA's iconic bullet style.
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import ImageDraw

from display.layout import FontSet, Region
from fetchers.subway import SubwayArrival
from renderers.base import BaseRenderer
import config

logger = logging.getLogger(__name__)

_SECTION_HEADER = "SUBWAY"
_HEADER_HEIGHT = 38
_BULLET_SIZE = 28   # bullet circle diameter
_LEFT_PAD = 10
_ROW_GAP = 6


class SubwayRenderer(BaseRenderer):
    """Renders real-time subway arrivals into the SUBWAY region."""

    def __init__(self, draw: ImageDraw.ImageDraw, region: Region, fonts: FontSet) -> None:
        super().__init__(draw, region, fonts)

    def render(self, data: Optional[list[SubwayArrival]]) -> None:
        """Draw upcoming arrivals.

        Args:
            data: List of :class:`~fetchers.subway.SubwayArrival` objects,
                  or ``None`` if no data is available.
        """
        self.fill_region()

        r = self.region
        x = r.x + _LEFT_PAD

        # ── Section header ────────────────────────────────────────────
        self.draw_text(x, r.y + 6, _SECTION_HEADER, self.fonts.lg)
        self.draw_divider(_HEADER_HEIGHT)

        if data is None:
            self.draw_text(x, r.y + _HEADER_HEIGHT + 10, "Subway unavailable", self.fonts.sm)
            return

        if not data:
            self.draw_text(x, r.y + _HEADER_HEIGHT + 10, "No arrivals found", self.fonts.sm)
            return

        # Stop sub-header
        sub_y = r.y + _HEADER_HEIGHT + 4
        self.draw_text(x, sub_y, config.SUBWAY_STATION_LABEL, self.fonts.sm)

        # ── Arrival rows ─────────────────────────────────────────────
        row_height = max(_BULLET_SIZE, self._text_height(self.fonts.md)) + _ROW_GAP
        y = sub_y + self._text_height(self.fonts.sm) + 8

        for arrival in data:
            if y + row_height > r.y2:
                break

            # Minutes away text
            mins_str = "Due" if arrival.minutes_away == 0 else f"{arrival.minutes_away} min"
            font = self.fonts.lg if arrival.minutes_away == 0 else self.fonts.md

            # Use textbbox for pixel-accurate vertical centering (excludes descent whitespace)
            bbox = self.draw.textbbox((0, 0), mins_str, font=font)
            text_visual_h = bbox[3] - bbox[1]
            text_top_offset = bbox[1]  # gap between anchor point and visible top

            item_h = max(_BULLET_SIZE, text_visual_h)
            bullet_y = y + (item_h - _BULLET_SIZE) // 2
            text_y = y + (item_h - text_visual_h) // 2 - text_top_offset + 6

            self._draw_bullet(arrival.route_id, r.x + _LEFT_PAD, bullet_y)
            text_x = r.x + _LEFT_PAD + _BULLET_SIZE + 10
            self.draw_text(text_x, text_y, mins_str, font)

            y += row_height

    # ------------------------------------------------------------------
    # Route bullet helper
    # ------------------------------------------------------------------

    def _draw_bullet(self, route_id: str, x: int, y: int) -> None:
        """Draw a filled black circle with white route text centred inside.

        Args:
            route_id: Route identifier string (e.g. "1", "A", "SIR").
            x, y:     Top-left corner of the bullet bounding square.
        """
        size = _BULLET_SIZE
        # Filled black circle
        self.draw.ellipse([(x, y), (x + size, y + size)], fill=0)

        # White route label centred in the circle
        label = route_id[:2]  # cap at 2 chars to fit
        label_w = self._text_width(label, self.fonts.sm)
        label_h = self._text_height(self.fonts.sm)
        label_x = x + (size - label_w) // 2
        label_y = y + (size - label_h) // 2

        self.draw.text((label_x, label_y), label, font=self.fonts.sm, fill=255)
