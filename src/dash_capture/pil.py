# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""PIL-based renderers for dash-capture.

Light-dependency renderers that decorate captured screenshots using
Pillow (PIL). Cover the common "wrap a screenshot in something" cases:
add a colored border, prepend a title bar, overlay a diagonal
watermark.

Use as the ``renderer=`` argument to :func:`dash_capture.capture_graph`
or :func:`dash_capture.capture_element`::

    from dash_capture import capture_graph
    from dash_capture.pil import titled

    capture_graph("my-graph", renderer=titled)

The wizard auto-generates form fields from each renderer's type hints,
so the user gets text inputs / number inputs / dropdowns out of the box.

Optional submodule — requires the ``pil`` extra::

    pip install 'dash-capture[pil]'
"""

from __future__ import annotations

import io
from typing import Literal

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "dash_capture.pil requires Pillow. "
        "Install it with: pip install 'dash-capture[pil]'"
    ) from e


def _load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Return a portable font at the requested size.

    Pillow 10+ supports ``load_default(size=N)`` for the built-in font,
    which gives a usable result everywhere without bundling a TTF.
    """
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Very old Pillow without size= support — fall back to bitmap
        return ImageFont.load_default()


def bordered(
    _target,
    _snapshot_img,
    color: str = "white",
    width: int = 20,
):
    """Wrap a captured screenshot in a colored border.

    Parameters
    ----------
    color :
        Border fill color. Any value PIL accepts: a name (``"white"``,
        ``"navy"``), a hex string (``"#2c3e50"``), or an RGB tuple.
    width :
        Border thickness in pixels (applied to all four sides).
    """
    img = Image.open(io.BytesIO(_snapshot_img()))
    new = Image.new(
        "RGB",
        (img.width + 2 * width, img.height + 2 * width),
        color,
    )
    new.paste(img, (width, width))
    buf = io.BytesIO()
    new.save(buf, format="PNG")
    _target.write(buf.getvalue())


def titled(
    _target,
    _snapshot_img,
    title: str = "",
    subtitle: str = "",
    bar_color: str = "white",
    text_color: str = "black",
):
    """Prepend a title bar above a captured screenshot.

    The bar height adjusts automatically based on whether a subtitle
    is provided. The wizard auto-generates a text input for ``title``
    / ``subtitle`` from the type hints.

    Parameters
    ----------
    title :
        Main title text drawn at the top-left of the bar.
    subtitle :
        Optional smaller line drawn below the title.
    bar_color :
        Background color of the title bar.
    text_color :
        Color of the title text. The subtitle is drawn one notch
        lighter (``gray``) regardless.
    """
    img = Image.open(io.BytesIO(_snapshot_img()))
    has_sub = bool(subtitle)
    bar_h = 60 if has_sub else 40
    new = Image.new("RGB", (img.width, img.height + bar_h), bar_color)
    new.paste(img, (0, bar_h))

    draw = ImageDraw.Draw(new)
    title_font = _load_font(20)
    if title:
        draw.text((12, 8), title, fill=text_color, font=title_font)
    if has_sub:
        sub_font = _load_font(13)
        draw.text((12, 34), subtitle, fill="gray", font=sub_font)

    buf = io.BytesIO()
    new.save(buf, format="PNG")
    _target.write(buf.getvalue())


def watermarked(
    _target,
    _snapshot_img,
    text: str = "DRAFT",
    opacity: float = 0.3,
    position: Literal["center", "diagonal"] = "diagonal",
):
    """Overlay a translucent watermark on a captured screenshot.

    Parameters
    ----------
    text :
        Watermark text (e.g. ``"DRAFT"``, ``"CONFIDENTIAL"``).
    opacity :
        Watermark alpha as a value between 0 and 1.
    position :
        ``"center"`` for a horizontal centered watermark,
        ``"diagonal"`` for a 30-degree rotated overlay.
    """
    img = Image.open(io.BytesIO(_snapshot_img())).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(40, img.width // 8)
    font = _load_font(font_size)

    # Measure text via textbbox (Pillow 10+ — guaranteed by [pil] extra).
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    alpha = max(0, min(255, int(255 * opacity)))
    fill = (128, 128, 128, alpha)

    x = (img.width - tw) // 2
    y = (img.height - th) // 2
    draw.text((x, y), text, fill=fill, font=font)

    if position == "diagonal":
        overlay = overlay.rotate(30, expand=False, fillcolor=(0, 0, 0, 0))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    _target.write(buf.getvalue())
