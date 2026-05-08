"""Project sRGB pixels onto the panel's 7-colour gamut.

The Pimoroni Inky Impression "Spectra 6" panel renders ~7 distinct ink
primaries; everything in between has to be dithered. Pillow handles the
heavy lifting via ``Image.quantize(palette=…, dither=…)``.

Themes are NOT restricted to the gamut (v4-brief §3): off-gamut colours
often dither into pleasing results on the panel. The /calibrate page (later
milestone) helps curate which off-gamut sRGB colours are worth picking.
"""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image

DitherMode = Literal["floyd-steinberg", "none"]


# Spectra 6 7-colour palette. Nominal sRGB approximations; the panel
# firmware maps these to its real ink primaries. /calibrate (later
# milestone) is the tool for curating themes against the actual paint.
SPECTRA_6_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),  # black
    (255, 255, 255),  # white
    (255, 255, 0),  # yellow
    (255, 0, 0),  # red
    (0, 0, 255),  # blue
    (0, 255, 0),  # green
    (255, 140, 0),  # orange
)


_DITHER_MAP: dict[str, Image.Dither] = {
    "floyd-steinberg": Image.Dither.FLOYDSTEINBERG,
    "none": Image.Dither.NONE,
}


def _palette_image(palette: tuple[tuple[int, int, int], ...]) -> Image.Image:
    """Build a Pillow palette image (mode 'P') from RGB triples."""
    pal = Image.new("P", (1, 1))
    flat: list[int] = []
    for r, g, b in palette:
        flat.extend([r, g, b])
    flat.extend([0] * (256 * 3 - len(flat)))  # pad to 256 entries
    pal.putpalette(flat)
    return pal


def quantize(
    src: bytes | Image.Image,
    *,
    dither: DitherMode = "floyd-steinberg",
    palette: tuple[tuple[int, int, int], ...] = SPECTRA_6_PALETTE,
) -> Image.Image:
    """Project an image to the panel gamut. Returns a Pillow Image (mode RGB)."""
    if dither not in _DITHER_MAP:
        raise ValueError(f"unknown dither mode: {dither!r}")
    img = src if isinstance(src, Image.Image) else Image.open(io.BytesIO(src))
    rgb = img.convert("RGB")
    pal_img = _palette_image(palette)
    return rgb.quantize(palette=pal_img, dither=_DITHER_MAP[dither]).convert("RGB")


def quantize_to_png(
    src: bytes | Image.Image,
    *,
    dither: DitherMode = "floyd-steinberg",
    palette: tuple[tuple[int, int, int], ...] = SPECTRA_6_PALETTE,
) -> bytes:
    out = io.BytesIO()
    quantize(src, dither=dither, palette=palette).save(out, format="PNG", optimize=True)
    return out.getvalue()


def rotate_png(png_bytes: bytes, *, quarters: int) -> bytes:
    """Rotate a PNG by N 90° clockwise turns. ``quarters=0`` is a no-op pass-through."""
    n = quarters % 4
    if n == 0:
        return png_bytes
    img = Image.open(io.BytesIO(png_bytes))
    # PIL.Image.rotate() with expand=True keeps every pixel; angle is CCW so
    # we negate to get clockwise.
    rotated = img.rotate(-90 * n, expand=True)
    out = io.BytesIO()
    rotated.save(out, format="PNG", optimize=True)
    return out.getvalue()
