# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.mpl — matplotlib snapshot renderer."""

import inspect
import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from dash_capture.mpl import snapshot_renderer


def _make_png_bytes() -> bytes:
    """Create a minimal valid PNG image."""
    fig, ax = plt.subplots(figsize=(2, 2), dpi=72)
    ax.plot([0, 1], [0, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


class TestSnapshotRenderer:
    def test_signature(self):
        sig = inspect.signature(snapshot_renderer)
        params = list(sig.parameters)
        assert "_target" in params
        assert "_snapshot_img" in params
        assert "title" in params

    def test_renders_to_buffer(self):
        png = _make_png_bytes()
        target = io.BytesIO()
        snapshot_renderer(target, lambda: png)
        target.seek(0)
        data = target.read()
        assert len(data) > 0
        # PNG magic bytes
        assert data[:4] == b"\x89PNG"

    def test_renders_with_title(self):
        png = _make_png_bytes()
        target = io.BytesIO()
        snapshot_renderer(target, lambda: png, title="Test Title")
        target.seek(0)
        data = target.read()
        assert data[:4] == b"\x89PNG"
