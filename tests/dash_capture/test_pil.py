# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.pil — Pillow-based decoration renderers."""

import inspect
import io

from PIL import Image

from dash_capture.pil import bordered, titled, watermarked


def _make_png(width: int = 100, height: int = 50, color: str = "red") -> bytes:
    """Build a small PNG of the requested size and color for tests."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _read_png(data: bytes) -> Image.Image:
    """Decode PNG bytes back into a PIL Image (asserts magic header)."""
    assert data[:4] == b"\x89PNG", f"not a PNG, got {data[:4]!r}"
    return Image.open(io.BytesIO(data))


# ---------------------------------------------------------------------------
# bordered
# ---------------------------------------------------------------------------


class TestBordered:
    def test_returns_png(self):
        target = io.BytesIO()
        bordered(target, lambda: _make_png())
        out = target.getvalue()
        assert out[:4] == b"\x89PNG"

    def test_increases_dimensions_by_2x_width(self):
        target = io.BytesIO()
        bordered(target, lambda: _make_png(100, 50), width=15)
        result = _read_png(target.getvalue())
        assert result.width == 100 + 2 * 15
        assert result.height == 50 + 2 * 15

    def test_corner_pixel_is_border_color(self):
        target = io.BytesIO()
        bordered(target, lambda: _make_png(100, 50, "red"), color="white", width=10)
        result = _read_png(target.getvalue())
        assert result.getpixel((0, 0)) == (255, 255, 255)

    def test_center_pixel_is_original_color(self):
        target = io.BytesIO()
        bordered(target, lambda: _make_png(100, 50, "red"), color="white", width=10)
        result = _read_png(target.getvalue())
        # Center of the original image (offset by border)
        assert result.getpixel((50 + 10, 25 + 10)) == (255, 0, 0)

    def test_default_signature_has_color_and_width_fields(self):
        sig = inspect.signature(bordered)
        params = list(sig.parameters)
        assert "_target" in params
        assert "_snapshot_img" in params
        assert "color" in params
        assert "width" in params

    def test_decorated_with_renderer(self):
        # @renderer attaches __dcap_meta__
        meta = bordered.__dcap_meta__
        assert meta.has_snapshot is True
        assert meta.fields == ("color", "width")


# ---------------------------------------------------------------------------
# titled
# ---------------------------------------------------------------------------


class TestTitled:
    def test_returns_png(self):
        target = io.BytesIO()
        titled(target, lambda: _make_png(), title="Hello")
        assert target.getvalue()[:4] == b"\x89PNG"

    def test_no_subtitle_uses_short_bar(self):
        target = io.BytesIO()
        titled(target, lambda: _make_png(100, 50), title="T")
        result = _read_png(target.getvalue())
        assert result.height == 50 + 40  # bar_h=40 when no subtitle

    def test_with_subtitle_uses_taller_bar(self):
        target = io.BytesIO()
        titled(target, lambda: _make_png(100, 50), title="T", subtitle="sub")
        result = _read_png(target.getvalue())
        assert result.height == 50 + 60  # bar_h=60 when subtitle present

    def test_width_unchanged(self):
        target = io.BytesIO()
        titled(target, lambda: _make_png(123, 50), title="T")
        result = _read_png(target.getvalue())
        assert result.width == 123

    def test_empty_title_still_renders_bar(self):
        # Empty title should not crash; bar is still added
        target = io.BytesIO()
        titled(target, lambda: _make_png(100, 50))
        result = _read_png(target.getvalue())
        assert result.height == 50 + 40

    def test_decorated_with_renderer(self):
        meta = titled.__dcap_meta__
        assert meta.has_snapshot is True
        assert "title" in meta.fields
        assert "subtitle" in meta.fields
        assert "bar_color" in meta.fields
        assert "text_color" in meta.fields


# ---------------------------------------------------------------------------
# watermarked
# ---------------------------------------------------------------------------


class TestWatermarked:
    def test_returns_png(self):
        target = io.BytesIO()
        watermarked(target, lambda: _make_png())
        assert target.getvalue()[:4] == b"\x89PNG"

    def test_dimensions_unchanged(self):
        target = io.BytesIO()
        watermarked(target, lambda: _make_png(200, 150))
        result = _read_png(target.getvalue())
        assert result.width == 200
        assert result.height == 150

    def test_diagonal_position_default(self):
        # Just verify it runs and returns a valid PNG
        target = io.BytesIO()
        watermarked(target, lambda: _make_png(), text="DRAFT", position="diagonal")
        assert target.getvalue()[:4] == b"\x89PNG"

    def test_center_position(self):
        target = io.BytesIO()
        watermarked(target, lambda: _make_png(), text="DRAFT", position="center")
        assert target.getvalue()[:4] == b"\x89PNG"

    def test_opacity_clamped(self):
        # Out-of-range opacity values should not crash — they get clamped
        target = io.BytesIO()
        watermarked(target, lambda: _make_png(), opacity=2.0)
        assert target.getvalue()[:4] == b"\x89PNG"

        target = io.BytesIO()
        watermarked(target, lambda: _make_png(), opacity=-1.0)
        assert target.getvalue()[:4] == b"\x89PNG"

    def test_decorated_with_renderer(self):
        meta = watermarked.__dcap_meta__
        assert meta.has_snapshot is True
        assert "text" in meta.fields
        assert "opacity" in meta.fields
        assert "position" in meta.fields


# ---------------------------------------------------------------------------
# Integration with capture_graph
# ---------------------------------------------------------------------------


class TestPilRenderersInWizard:
    """The PIL renderers must integrate cleanly with capture_graph —
    auto-generating form fields from their type hints.
    """

    def test_bordered_in_capture_graph(self):
        from dash import html

        from dash_capture import capture_graph

        wizard = capture_graph("g-pil-bordered", renderer=bordered)
        assert isinstance(wizard, html.Div)

    def test_titled_in_capture_graph(self):
        from dash import html

        from dash_capture import capture_graph

        wizard = capture_graph("g-pil-titled", renderer=titled)
        assert isinstance(wizard, html.Div)

    def test_watermarked_in_capture_graph(self):
        from dash import html

        from dash_capture import capture_graph

        wizard = capture_graph("g-pil-watermarked", renderer=watermarked)
        assert isinstance(wizard, html.Div)


# ---------------------------------------------------------------------------
# Round-trip: chain renderers (output of one is input to another)
# ---------------------------------------------------------------------------


def test_bordered_then_titled_round_trip():
    """Apply bordered to a base image, then titled to the result.

    Sanity check that PIL renderers produce well-formed PNGs that can
    be re-fed into another renderer.
    """
    base = _make_png(100, 50, "blue")

    step1 = io.BytesIO()
    bordered(step1, lambda: base, color="white", width=10)

    step2 = io.BytesIO()
    titled(step2, lambda: step1.getvalue(), title="My Chart")

    final = _read_png(step2.getvalue())
    # Original 100x50 + 2*10 border + 40 title bar = 120x110
    assert final.width == 120
    assert final.height == 110
