"""
display/epd_driver.py — Clean wrapper around the Waveshare epd7in5_V2 driver.

In MOCK_MODE the driver saves images to disk instead of pushing to hardware,
so the full application can be exercised on a non-Pi machine.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import config
from display.layout import Region

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attempt to import the Waveshare library.
# This will succeed only on a Raspberry Pi with the library installed.
# ---------------------------------------------------------------------------
_WAVESHARE_IMPORT_ERROR: ImportError | None = None
try:
    from waveshare_epd import epd7in5_V2 as _epd_module  # type: ignore[import]

    _WAVESHARE_AVAILABLE = True
except ImportError as exc:
    _WAVESHARE_AVAILABLE = False
    _WAVESHARE_IMPORT_ERROR = exc
    logger.warning(
        "waveshare_epd hardware driver not loaded (%s: %s). "
        "On a Pi: `poetry install` (pulls in gpiozero), install Waveshare lib via setup.sh, "
        "enable SPI, user in spi+gpio groups.",
        type(exc).__name__,
        exc,
    )


class EPDDriver:
    """High-level interface to the Waveshare 7.5-inch V2 e-ink panel.

    All public methods are safe to call in mock mode; they write a PNG to
    ``config.MOCK_OUTPUT_PATH`` instead of touching hardware.
    """

    def __init__(self) -> None:
        self._epd: Optional[object] = None
        self._mock: bool = config.MOCK_MODE or not _WAVESHARE_AVAILABLE

        if self._mock:
            if not config.MOCK_MODE and _WAVESHARE_IMPORT_ERROR is not None:
                logger.warning(
                    "EPDDriver: MOCK output (hardware import failed — see log above). "
                    "Writing to %s",
                    config.MOCK_OUTPUT_PATH,
                )
            else:
                logger.info("EPDDriver: running in MOCK mode (no hardware)")
        else:
            logger.info("EPDDriver: hardware mode (epd7in5_V2)")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Initialise the display panel.

        Must be called once before any refresh operation.  In mock mode
        this is a no-op.
        """
        if self._mock:
            return

        self._epd = _epd_module.EPD()
        self._epd.init()
        logger.debug("EPD initialised")

    def sleep(self) -> None:
        """Put the panel into low-power sleep mode.

        Always call this after a refresh to protect the e-ink panel from
        prolonged voltage stress.  Safe to call even if the panel is
        already asleep.
        """
        if self._mock or self._epd is None:
            return
        try:
            self._epd.sleep()
            logger.debug("EPD sleeping")
        except Exception:
            logger.exception("EPD sleep failed")

    def wake(self) -> None:
        """Wake the panel from sleep before the next refresh.

        Re-initialises the controller registers.
        """
        if self._mock or self._epd is None:
            return
        try:
            self._epd.init()
            logger.debug("EPD woken")
        except Exception:
            logger.exception("EPD wake failed")

    # ------------------------------------------------------------------
    # Refresh methods
    # ------------------------------------------------------------------

    def full_refresh(self, image: "PIL.Image.Image") -> None:  # type: ignore[name-defined]
        """Push *image* to the entire panel with a full (non-partial) refresh.

        A full refresh eliminates ghosting but takes ~3 seconds and causes a
        characteristic flash.  Use for the periodic full redraw.

        In mock mode the image is saved to ``config.MOCK_OUTPUT_PATH``.
        """
        if self._mock:
            _save_mock(image)
            return

        if self._epd is None:
            logger.error("full_refresh called before init()")
            return

        try:
            # The Waveshare 7.5" V2 getbuffer() expects a 1-bit image.
            bw_image = image.convert("1")
            self._epd.display(self._epd.getbuffer(bw_image))
            logger.debug("EPD full refresh complete")
        except Exception:
            logger.exception("EPD full_refresh failed")
        finally:
            self.sleep()

    def partial_refresh(
        self,
        image: "PIL.Image.Image",  # type: ignore[name-defined]
        region: Region,
    ) -> None:
        """Refresh only the pixels within *region*.

        Note: the 7.5-inch V2 panel does not support true hardware partial
        refresh.  This method performs a full refresh using only the pixels
        from *image* within *region* composited onto a blank white canvas.
        For panels that do support partial refresh, override this method.

        In mock mode the full image is saved (the region argument is logged).
        """
        if self._mock:
            logger.debug(
                "Mock partial refresh: region x=%d y=%d w=%d h=%d",
                region.x,
                region.y,
                region.w,
                region.h,
            )
            _save_mock(image)
            return

        if self._epd is None:
            logger.error("partial_refresh called before init()")
            return

        # Fall back to full refresh for panels without partial support.
        logger.debug(
            "partial_refresh: panel does not support hardware partial — "
            "performing full refresh"
        )
        self.full_refresh(image)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _save_mock(image: "PIL.Image.Image") -> None:  # type: ignore[name-defined]
    """Save *image* to the mock output path, creating parent dirs as needed."""
    from PIL import Image

    out_path = Path(config.MOCK_OUTPUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Save as RGB PNG (more viewable than 1-bit on a desktop).
    rgb = image.convert("RGB")
    rgb.save(out_path, format="PNG")
    logger.info("Mock image saved → %s", out_path)
