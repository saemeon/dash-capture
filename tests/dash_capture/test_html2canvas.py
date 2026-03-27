# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture._html2canvas — vendored html2canvas inclusion."""

from dash import html

from dash_capture._html2canvas import ensure_html2canvas, html2canvas_script


class TestHtml2canvasScript:
    def test_returns_script_component(self):
        script = html2canvas_script()
        assert isinstance(script, html.Script)

    def test_script_has_content(self):
        script = html2canvas_script()
        children = script.children
        assert children
        assert len(children) > 100  # minified JS is large


class TestEnsureHtml2canvas:
    def test_prepends_script(self):
        result = ensure_html2canvas(["child1"])
        assert len(result) == 2
        assert isinstance(result[0], html.Script)
        assert result[1] == "child1"

    def test_always_prepends(self):
        # No deduplication at this level — Dash handles it
        r1 = ensure_html2canvas(["a"])
        r2 = ensure_html2canvas(["b"])
        assert isinstance(r1[0], html.Script)
        assert isinstance(r2[0], html.Script)

    def test_empty_children(self):
        result = ensure_html2canvas([])
        assert len(result) == 1
        assert isinstance(result[0], html.Script)
