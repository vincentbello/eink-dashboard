"""
display/layout.py — Screen regions and font set definitions.

All pixel coordinates are absolute (origin = top-left corner of the screen).
Every renderer receives one Region and must confine all drawing to it.

Screen: 800 × 480 px, black and white only.

Layout
------
┌──────────────────────────────────────────────────────────────┐
│  TIME (large)          DATE              WEATHER             │  y:   0  h: 80
├───────────────────────────┬──────────────────────────────────┤
│                           │                                  │
│  CALENDAR                 │  SUBWAY                          │  y:  80  h: 220
│                           │                                  │
│                           │                                  │
├───────────────────────────┴──────────────────────────────────┤
│  CITI BIKE                                                   │  y: 300  h: 180
└──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from PIL.ImageFont import FreeTypeFont


@dataclass(frozen=True)
class Region:
    """Axis-aligned bounding box for one display section."""

    x: int
    y: int
    w: int
    h: int

    # -----------------------------------------------------------------
    # Convenience helpers
    # -----------------------------------------------------------------

    @property
    def x2(self) -> int:
        """Right edge (exclusive)."""
        return self.x + self.w

    @property
    def y2(self) -> int:
        """Bottom edge (exclusive)."""
        return self.y + self.h

    @property
    def cx(self) -> int:
        """Horizontal centre."""
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        """Vertical centre."""
        return self.y + self.h // 2

    def inner(self, padding: int = 8) -> Region:
        """Return a region inset by *padding* on all sides."""
        return Region(
            x=self.x + padding,
            y=self.y + padding,
            w=max(0, self.w - padding * 2),
            h=max(0, self.h - padding * 2),
        )


# ---------------------------------------------------------------------------
# Named screen regions
# ---------------------------------------------------------------------------

HEADER: Region = Region(x=0, y=0, w=config.DISPLAY_WIDTH, h=100)

# Header sub-regions
HEADER_TIME: Region = Region(x=0, y=0, w=260, h=100)
HEADER_DATE: Region = Region(x=260, y=0, w=280, h=100)
HEADER_WEATHER: Region = Region(x=540, y=0, w=260, h=100)

# Middle row
_MIDDLE_Y: int = HEADER.h
_MIDDLE_H: int = 220

CALENDAR: Region = Region(x=0, y=_MIDDLE_Y, w=400, h=_MIDDLE_H)
SUBWAY: Region = Region(x=400, y=_MIDDLE_Y, w=400, h=_MIDDLE_H)

# Bottom row
_BOTTOM_Y: int = _MIDDLE_Y + _MIDDLE_H  # 300
CITIBIKE: Region = Region(
    x=0,
    y=_BOTTOM_Y,
    w=config.DISPLAY_WIDTH,
    h=config.DISPLAY_HEIGHT - _BOTTOM_Y,  # 180
)

# ---------------------------------------------------------------------------
# Font set
# ---------------------------------------------------------------------------


@dataclass
class FontSet:
    """Pre-loaded PIL fonts at the four canonical sizes."""

    xl: "FreeTypeFont"
    lg: "FreeTypeFont"
    md: "FreeTypeFont"
    sm: "FreeTypeFont"


def load_fonts() -> FontSet:
    """Load Space Grotesk from the paths declared in *config*.

    Falls back to PIL's built-in bitmap font if the TTF files are missing
    (useful for CI environments without the font assets).
    """
    from PIL import ImageFont

    def _load(path: str, size: int) -> "FreeTypeFont":
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            import logging

            logging.getLogger(__name__).warning(
                "Font not found: %s — falling back to default bitmap font. "
                "Add the bundled TTFs under assets/fonts/ or run scripts/setup.sh on the Pi.",
                path,
            )
            # FreeType fallback: PIL default is not a FreeTypeFont but the
            # API is compatible for our purposes.
            return ImageFont.load_default()  # type: ignore[return-value]

    return FontSet(
        xl=_load(config.FONT_BOLD, config.FONT_SIZE_XL),
        lg=_load(config.FONT_BOLD, config.FONT_SIZE_LG),
        md=_load(config.FONT_REGULAR, config.FONT_SIZE_MD),
        sm=_load(config.FONT_REGULAR, config.FONT_SIZE_SM),
    )
