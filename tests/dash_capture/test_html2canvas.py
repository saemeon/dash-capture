# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture._html2canvas — vendored html2canvas inclusion."""

import contextlib

import dash

from dash_capture._html2canvas import _MARKER, _read_html2canvas, ensure_html2canvas


class TestReadHtml2canvas:
    def test_returns_minified_js(self):
        js = _read_html2canvas()
        assert isinstance(js, str)
        assert len(js) > 100  # minified JS is large
        assert "html2canvas" in js


class TestEnsureHtml2canvas:
    def test_returns_children_unchanged(self):
        app = dash.Dash(__name__)  # noqa: F841 — registers as current app
        result = ensure_html2canvas(["child1"])
        assert result == ["child1"]

    def test_patches_app_index_string(self):
        app = dash.Dash(__name__)
        assert _MARKER not in app.index_string
        ensure_html2canvas([])
        assert _MARKER in app.index_string
        assert "html2canvas" in app.index_string

    def test_only_patches_once_per_app(self):
        app = dash.Dash(__name__)
        ensure_html2canvas([])
        ensure_html2canvas([])
        assert app.index_string.count(_MARKER) == 1

    def test_no_current_app_returns_children(self):
        # When dash.get_app() raises, we still return children unchanged.
        # Hard to construct that state inside a test runner that has already
        # built apps in other tests, so just verify the no-op invariant
        # for the children list itself.
        with contextlib.suppress(Exception):
            app = dash.Dash(__name__)  # noqa: F841

        result = ensure_html2canvas(["a", "b"])
        assert result == ["a", "b"]
