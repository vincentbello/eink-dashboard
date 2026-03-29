"""
renderers/base.py — Abstract base class for all display section renderers.

Every renderer receives:
  - draw   : PIL ImageDraw instance targeting the full screen canvas
  - region : the bounding box this renderer owns
  - fonts  : pre-loaded FontSet

Renderers must never draw outside their assigned region.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from PIL import ImageDraw, ImageFont

from display.layout import FontSet, Region


class BaseRenderer(ABC):
    """Base class shared by all section renderers."""

    def __init__(self, draw: ImageDraw.ImageDraw, region: Region, fonts: FontSet) -> None:
        """Initialise with a shared draw context, a bounding region, and fonts.

        Args:
            draw:   The PIL ImageDraw object for the full screen canvas.
            region: The axis-aligned bounding box this renderer may draw into.
            fonts:  Pre-loaded FontSet at the four canonical sizes.
        """
        self.draw = draw
        self.region = region
        self.fonts = fonts

    @abstractmethod
    def render(self, data: Any) -> None:
        """Draw *data* into ``self.region``.

        Subclasses must implement this method and must not draw outside
        ``self.region``.

        Args:
            data: The domain-specific data object produced by the matching
                  fetcher (e.g. ``WeatherData``, ``list[CalendarEvent]``).
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared drawing helpers
    # ------------------------------------------------------------------

    def draw_divider(self, y_offset: int, *, color: int = 0) -> None:
        """Draw a thin horizontal rule at *y_offset* within this region.

        Args:
            y_offset: Vertical position relative to the top of the region.
            color:    Pixel colour (0 = black, 255 = white for L-mode images).
        """
        y = self.region.y + y_offset
        self.draw.line(
            [(self.region.x, y), (self.region.x2 - 1, y)],
            fill=color,
            width=1,
        )

    def draw_vertical_divider(self, x_offset: int, *, color: int = 0) -> None:
        """Draw a thin vertical rule at *x_offset* within this region."""
        x = self.region.x + x_offset
        self.draw.line(
            [(x, self.region.y), (x, self.region.y2 - 1)],
            fill=color,
            width=1,
        )

    def truncate_text(
        self, text: str, font: ImageFont.FreeTypeFont, max_width: int
    ) -> str:
        """Return *text* truncated with an ellipsis if it exceeds *max_width* px.

        Args:
            text:      The string to (potentially) truncate.
            font:      The font used to measure text width.
            max_width: Maximum allowed pixel width.

        Returns:
            The original string if it fits, or a shortened version ending in
            "…" that fits within *max_width*.
        """
        if self._text_width(text, font) <= max_width:
            return text

        ellipsis = "…"
        while text:
            candidate = text + ellipsis
            if self._text_width(candidate, font) <= max_width:
                return candidate
            text = text[:-1]

        return ellipsis

    def _text_width(self, text: str, font: ImageFont.FreeTypeFont) -> int:
        """Return the rendered pixel width of *text* in *font*."""
        try:
            # Pillow >= 9.2 exposes getlength() on FreeTypeFont.
            return int(font.getlength(text))  # type: ignore[attr-defined]
        except AttributeError:
            # Older Pillow fallback.
            bbox = self.draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]

    def _text_height(self, font: ImageFont.FreeTypeFont) -> int:
        """Return the approximate line height in *font* (ascent + descent)."""
        try:
            ascent, descent = font.getmetrics()  # type: ignore[attr-defined]
            return ascent + descent
        except AttributeError:
            bbox = self.draw.textbbox((0, 0), "Ag", font=font)
            return bbox[3] - bbox[1]

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        font: ImageFont.FreeTypeFont,
        *,
        fill: int = 0,
        anchor: str = "lt",
    ) -> None:
        """Convenience wrapper for ``ImageDraw.text`` with absolute coords.

        Args:
            x, y:   Absolute screen coordinates (not relative to region).
            text:   String to draw.
            font:   Pillow font object.
            fill:   Pixel fill value (0 = black).
            anchor: Pillow text anchor string (default "lt" = left-top).
        """
        self.draw.text((x, y), text, font=font, fill=fill, anchor=anchor)

    def fill_region(self, *, color: int = 255) -> None:
        """Flood-fill the entire region with *color* (default white).

        Useful for clearing a region before redrawing.
        """
        self.draw.rectangle(
            [(self.region.x, self.region.y), (self.region.x2 - 1, self.region.y2 - 1)],
            fill=color,
        )
