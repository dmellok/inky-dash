"""Server-side image-composition helpers for the Send pipeline.

Used when a Send option needs the panel to receive a pre-composed image
that the listener can't produce itself. Currently that's "blurred-fit",
which mimics the CSS ``.scale-blurred`` mode the Gallery / APOD / Wikimedia
widgets use in the browser — a heavily-blurred cover-fit copy of the
image fills the panel, and the original aspect-preserved version sits on
top, centred.
"""

from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageOps


def blurred_fit(
    source_bytes: bytes,
    *,
    target_w: int,
    target_h: int,
    blur_radius: int = 40,
) -> bytes:
    """Compose a panel-sized PNG: blurred cover-fit background +
    aspect-preserving foreground centred on top.

    Args:
      source_bytes: raw bytes of any Pillow-supported image format.
      target_w / target_h: panel render dimensions.
      blur_radius: Gaussian blur sigma applied to the background layer.

    Returns: PNG byte string at exactly ``target_w × target_h``.
    """
    with Image.open(io.BytesIO(source_bytes)) as src:
        src = ImageOps.exif_transpose(src)
        if src.mode != "RGB":
            src = src.convert("RGB")
        src_w, src_h = src.size

        # Background: cover-fit. Scale source so its shorter axis matches the
        # target, then crop the overflow off symmetrically so the centre of
        # the source sits at the centre of the panel.
        bg_scale = max(target_w / src_w, target_h / src_h)
        bg = src.resize(
            (max(1, round(src_w * bg_scale)), max(1, round(src_h * bg_scale))),
            Image.LANCZOS,
        )
        bx = max(0, (bg.width - target_w) // 2)
        by = max(0, (bg.height - target_h) // 2)
        bg = bg.crop((bx, by, bx + target_w, by + target_h))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        # Foreground: contain-fit. Keep the original aspect, scale up to the
        # largest size that still fits inside the target.
        fg_scale = min(target_w / src_w, target_h / src_h)
        fg = src.resize(
            (max(1, round(src_w * fg_scale)), max(1, round(src_h * fg_scale))),
            Image.LANCZOS,
        )

        canvas = bg.copy()
        fx = (target_w - fg.width) // 2
        fy = (target_h - fg.height) // 2
        canvas.paste(fg, (fx, fy))

        out = io.BytesIO()
        canvas.save(out, format="PNG", optimize=True)
        return out.getvalue()
