"""
renderers/weather.py — Draws weather conditions in the HEADER_WEATHER region.

Layout within the region (260 × 80 px):
  ┌─────────────────────────────┐
  │  [ICON]   22°C              │
  │           Partly cloudy     │
  │           Wind 8 mph        │
  └─────────────────────────────┘

The icon is drawn with PIL primitives — no external image files required.
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import ImageDraw

from display.layout import FontSet, Region
from fetchers.weather import WeatherData, temperature_unit_suffix
from renderers.base import BaseRenderer

logger = logging.getLogger(__name__)

# Icon canvas size (pixels) – drawn in the left portion of the region.
_ICON_SIZE = 56
_ICON_PAD = 8   # padding from region edges


class WeatherRenderer(BaseRenderer):
    """Renders current weather into the right-hand header sub-region."""

    def __init__(self, draw: ImageDraw.ImageDraw, region: Region, fonts: FontSet) -> None:
        super().__init__(draw, region, fonts)

    def render(self, data: Optional[WeatherData]) -> None:
        """Draw weather conditions.

        Args:
            data: A :class:`~fetchers.weather.WeatherData` instance, or
                  ``None`` if no data is available (draws a placeholder).
        """
        self.fill_region()

        if data is None:
            self.draw_text(
                self.region.x + 10,
                self.region.cy - self._text_height(self.fonts.sm) // 2,
                "Weather unavailable",
                self.fonts.sm,
            )
            return

        r = self.region

        # Layout: temperature and icon inline, vertically centered
        # ┌─────────────────────┐
        # │  22°C  [ICON]       │
        # └─────────────────────┘

        # Vertically centered, nudged down slightly
        row_y = r.y + (r.h - self.fonts.lg.size) // 2 + 2
        temp_h = self._text_height(self.fonts.lg)

        # Temperature (large font), nudged down slightly for alignment
        temp_str = f"{data.temperature:.0f}{temperature_unit_suffix()}"
        temp_x = r.x + _ICON_PAD
        self.draw_text(temp_x, row_y + 12, temp_str, self.fonts.lg)

        # Icon to the right of temperature
        temp_bbox = self.draw.textbbox((0, 0), temp_str, font=self.fonts.lg)
        temp_w = temp_bbox[2] - temp_bbox[0]
        icon_x = temp_x + temp_w + 12
        icon_y = row_y + (temp_h - _ICON_SIZE) // 2

        self._draw_icon(data.icon_key, icon_x, icon_y, _ICON_SIZE)

    # ------------------------------------------------------------------
    # Icon drawing (PIL primitives only)
    # ------------------------------------------------------------------

    def _draw_icon(self, key: str, x: int, y: int, size: int) -> None:
        """Dispatch to the appropriate icon-drawing method.

        Args:
            key:  One of: sunny | cloudy | rainy | snowy | stormy | foggy
            x, y: Top-left corner of the icon bounding square (absolute px).
            size: Width and height of the bounding square in pixels.
        """
        dispatch = {
            "sunny": self._icon_sunny,
            "cloudy": self._icon_cloudy,
            "rainy": self._icon_rainy,
            "snowy": self._icon_snowy,
            "stormy": self._icon_stormy,
            "foggy": self._icon_foggy,
        }
        fn = dispatch.get(key, self._icon_cloudy)
        fn(x, y, size)

    def _icon_sunny(self, x: int, y: int, size: int) -> None:
        """Draw a sun: filled circle with radiating lines."""
        cx, cy = x + size // 2, y + size // 2
        r = size // 4

        # Sun disc
        self.draw.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            fill=0,
        )

        # Rays (8 directions)
        import math

        ray_inner = r + 4
        ray_outer = size // 2 - 2
        for angle_deg in range(0, 360, 45):
            angle = math.radians(angle_deg)
            x1 = int(cx + ray_inner * math.cos(angle))
            y1 = int(cy + ray_inner * math.sin(angle))
            x2 = int(cx + ray_outer * math.cos(angle))
            y2 = int(cy + ray_outer * math.sin(angle))
            self.draw.line([(x1, y1), (x2, y2)], fill=0, width=2)

    def _icon_cloudy(self, x: int, y: int, size: int) -> None:
        """Draw a cloud: three overlapping filled ellipses."""
        cy = y + size * 2 // 3
        w, h = size * 2 // 3, size // 3

        # Left puff
        self.draw.ellipse([(x, cy - h // 2), (x + w, cy + h // 2)], fill=0)
        # Right puff
        rx = x + size // 3
        self.draw.ellipse(
            [(rx, cy - h * 2 // 3), (rx + w, cy + h * 2 // 3)], fill=0
        )
        # Centre puff (top, larger)
        mx = x + size // 5
        self.draw.ellipse(
            [
                (mx, cy - int(h * 1.2)),
                (mx + int(w * 0.9), cy + h // 3),
            ],
            fill=0,
        )

    def _icon_rainy(self, x: int, y: int, size: int) -> None:
        """Draw a cloud with rain drops below."""
        # Cloud in upper 60 %
        sub_size = int(size * 0.6)
        self._icon_cloudy(x + size // 6, y, sub_size)

        # Rain drops (short diagonal lines)
        drop_y_start = y + sub_size + 2
        for col in range(3):
            drop_x = x + 6 + col * (size // 3)
            drop_y = drop_y_start + (col % 2) * 5
            self.draw.line(
                [(drop_x, drop_y), (drop_x - 4, drop_y + 8)],
                fill=0,
                width=2,
            )

    def _icon_snowy(self, x: int, y: int, size: int) -> None:
        """Draw a cloud with snowflake dots below."""
        sub_size = int(size * 0.6)
        self._icon_cloudy(x + size // 6, y, sub_size)

        dot_y = y + sub_size + 4
        dot_r = 2
        for col in range(4):
            dot_x = x + 4 + col * (size // 4)
            offset = (col % 2) * 5
            self.draw.ellipse(
                [
                    (dot_x - dot_r, dot_y + offset - dot_r),
                    (dot_x + dot_r, dot_y + offset + dot_r),
                ],
                fill=0,
            )

    def _icon_stormy(self, x: int, y: int, size: int) -> None:
        """Draw a cloud with a lightning bolt below."""
        sub_size = int(size * 0.55)
        self._icon_cloudy(x + size // 8, y, sub_size)

        # Lightning bolt polygon
        bx = x + size // 2
        by = y + sub_size + 2
        bolt = [
            (bx + 6, by),
            (bx - 2, by + size // 4),
            (bx + 3, by + size // 4),
            (bx - 6, by + size // 2),
            (bx + 8, by + size // 4 - 2),
            (bx + 2, by + size // 4 - 2),
        ]
        self.draw.polygon(bolt, fill=0)

    def _icon_foggy(self, x: int, y: int, size: int) -> None:
        """Draw horizontal fog lines."""
        line_count = 4
        gap = size // (line_count + 1)
        for i in range(line_count):
            line_y = y + gap * (i + 1)
            # Stagger line widths for a wispy look.
            margin = (i % 2) * (size // 6)
            self.draw.line(
                [(x + margin, line_y), (x + size - margin, line_y)],
                fill=0,
                width=2,
            )
