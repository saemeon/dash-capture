# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Example: matplotlib-based renderer for dash-capture.

Demonstrates how to wrap a captured browser snapshot in a matplotlib
figure so you can decorate it server-side using matplotlib's annotation
APIs (titles, text overlays, axis annotations, etc.).

Copy the function below into your own app and pass it to
:func:`dash_capture.capture_graph` or :func:`dash_capture.capture_element`::

    from dash_capture import capture_graph
    from my_app.renderers import mpl_titled_snapshot

    capture_graph("my-graph", renderer=mpl_titled_snapshot)

The wizard auto-generates form fields from the renderer's type hints, so
the user gets a ``title`` text input out of the box.

Requires :mod:`matplotlib` (``pip install matplotlib``) — not part of
dash-capture's runtime dependencies.
"""

from __future__ import annotations

import io

import matplotlib.pyplot as plt

plt.switch_backend("agg")


def mpl_titled_snapshot(_target, _snapshot_img, title: str = ""):
    """Wrap a browser snapshot in a matplotlib figure with optional title.

    The captured PNG is decoded, drawn into a matplotlib axes (with
    axes hidden), an optional title is added via ``ax.set_title``, and
    the figure is rendered back to PNG.

    Note: this is a *demonstration* of the renderer protocol — for the
    common "add a title bar above a screenshot" case, prefer the much
    lighter PIL-based renderer (no matplotlib needed). Reach for this
    one when you actually want matplotlib's annotation APIs:
    ``ax.annotate``, mathtext, multi-panel layouts, brand-styled themes.

    Parameters
    ----------
    _target :
        File-like object the export pipeline writes the final PNG to.
    _snapshot_img :
        Callable returning the raw browser-captured PNG bytes.
    title :
        Optional title drawn above the snapshot. Wizard exposes this as
        a text input field, auto-generated from the type hint.
    """
    img = plt.imread(io.BytesIO(_snapshot_img()))
    dpi = 300
    h, w = img.shape[:2]
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    try:
        ax.imshow(img)
        ax.axis("off")
        if title:
            ax.set_title(title)
        fig.savefig(_target, format="png", bbox_inches="tight", pad_inches=0)
    finally:
        plt.close(fig)
