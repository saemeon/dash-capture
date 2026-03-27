# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Matplotlib renderers for use with :func:`dash_capture.capture_graph`."""

from __future__ import annotations

import io

import matplotlib.pyplot as plt

plt.switch_backend("agg")


def snapshot_renderer(_target, _snapshot_img, title: str = ""):
    """Render a browser snapshot as a matplotlib figure.

    Use this renderer when you want to annotate the captured image
    server-side using matplotlib — for example, to add a title, text
    overlay, or branding that isn't part of the live Plotly figure.

    Pass it to :func:`dash_capture.capture_graph`::

        from dash_capture import capture_graph
        from dash_capture.mpl import snapshot_renderer

        capture_graph("my-graph", renderer=snapshot_renderer)

    Parameters
    ----------
    _target :
        File-like object to write the final PNG to (injected by the
        export pipeline).
    _snapshot_img :
        Callable returning raw PNG bytes of the captured graph (injected
        by the export pipeline).
    title :
        Optional title drawn by matplotlib above the snapshot image.
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
