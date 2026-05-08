from __future__ import annotations

import pytest
from PIL import Image

from app.quantizer import (
    SPECTRA_6_PALETTE,
    quantize,
    quantize_to_png,
    rotate_png,
)


def _solid(color: tuple[int, int, int], size: tuple[int, int] = (4, 4)) -> Image.Image:
    return Image.new("RGB", size, color)


@pytest.mark.parametrize(
    "src_color,expected",
    [
        ((10, 10, 10), (0, 0, 0)),  # near-black → black
        ((250, 250, 250), (255, 255, 255)),  # near-white → white
        ((250, 10, 10), (255, 0, 0)),  # bright red → red
        ((10, 240, 10), (0, 255, 0)),  # bright green → green
        ((10, 10, 240), (0, 0, 255)),  # bright blue → blue
        ((250, 250, 10), (255, 255, 0)),  # yellow → yellow
        ((250, 140, 10), (255, 140, 0)),  # orange → orange
    ],
)
def test_solid_colour_snaps_to_nearest_palette_entry(
    src_color: tuple[int, int, int], expected: tuple[int, int, int]
) -> None:
    out = quantize(_solid(src_color), dither="none")
    sampled = out.getpixel((0, 0))
    assert sampled == expected


def test_dither_modes_produce_different_outputs_on_a_gradient() -> None:
    """A horizontal grey gradient: nearest-neighbour collapses to a hard edge,
    Floyd-Steinberg spreads black/white pixels."""
    img = Image.new("RGB", (40, 1))
    for x in range(40):
        v = int(255 * x / 39)
        img.putpixel((x, 0), (v, v, v))
    nn = quantize(img, dither="none")
    fs = quantize(img, dither="floyd-steinberg")
    nn_pixels = [nn.getpixel((x, 0)) for x in range(40)]
    fs_pixels = [fs.getpixel((x, 0)) for x in range(40)]
    assert nn_pixels != fs_pixels


def test_quantize_only_emits_palette_colours() -> None:
    img = Image.new("RGB", (32, 32))
    for x in range(32):
        for y in range(32):
            img.putpixel((x, y), (x * 8, y * 8, 128))
    out = quantize(img, dither="floyd-steinberg")
    palette_set = set(SPECTRA_6_PALETTE)
    pixels = {out.getpixel((x, y)) for x in range(32) for y in range(32)}
    assert pixels.issubset(palette_set)


def test_unknown_dither_raises() -> None:
    with pytest.raises(ValueError, match="unknown dither mode"):
        quantize(_solid((128, 128, 128)), dither="zzz")  # type: ignore[arg-type]


def test_quantize_to_png_returns_valid_png_bytes() -> None:
    png = quantize_to_png(_solid((128, 128, 128), (16, 16)))
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    # Round-trip check: bytes load back as a valid image.
    import io

    Image.open(io.BytesIO(png)).load()


def test_rotate_png_quarter_turn_swaps_dimensions() -> None:
    import io

    # Asymmetric input so swap is observable.
    src = Image.new("RGB", (40, 10), (255, 0, 0))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    rotated = rotate_png(buf.getvalue(), quarters=1)
    out = Image.open(io.BytesIO(rotated))
    assert out.size == (10, 40)


def test_rotate_png_zero_quarters_is_no_op() -> None:
    import io

    src = Image.new("RGB", (12, 8), (0, 0, 255))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out = rotate_png(buf.getvalue(), quarters=0)
    # Same bytes returned (pass-through, not re-encoded).
    assert out is buf.getvalue() or out == buf.getvalue()


def test_rotate_png_full_revolution_returns_original_dims() -> None:
    import io

    src = Image.new("RGB", (12, 8), (0, 0, 255))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out = rotate_png(buf.getvalue(), quarters=4)
    img = Image.open(io.BytesIO(out))
    assert img.size == (12, 8)


def test_rotate_png_pixel_position_after_clockwise_quarter() -> None:
    """A red pixel at top-left should land at top-right after a 90° clockwise turn."""
    import io

    src = Image.new("RGB", (4, 4), (255, 255, 255))
    src.putpixel((0, 0), (255, 0, 0))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    out = rotate_png(buf.getvalue(), quarters=1)
    img = Image.open(io.BytesIO(out)).convert("RGB")
    # Source (0,0) → after 90° CW on a 4×4 image → (3, 0).
    assert img.getpixel((3, 0)) == (255, 0, 0)
    assert img.getpixel((0, 0)) != (255, 0, 0)
