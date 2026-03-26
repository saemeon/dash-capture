# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture._html2canvas — vendored html2canvas inclusion."""

from dash import html

from dash_capture._html2canvas import html2canvas_script


class TestHtml2canvasScript:
    def test_returns_script_component(self):
        script = html2canvas_script()
        assert isinstance(script, html.Script)

    def test_script_has_content(self):
        script = html2canvas_script()
        # The Script component wraps inline JS; children should be non-empty
        children = script.children
        assert children
        assert len(children) > 100  # minified JS is large


class TestEnsureHtml2canvas:
    def test_prepends_script_on_first_call(self):
        import dash_capture._html2canvas as mod

        # Reset module-level flag
        mod._LOADED = False
        try:
            result = mod.ensure_html2canvas(["child1"])
            assert len(result) == 2
            assert isinstance(result[0], html.Script)
            assert result[1] == "child1"
        finally:
            mod._LOADED = False

    def test_skips_on_subsequent_call(self):
        import dash_capture._html2canvas as mod

        mod._LOADED = False
        try:
            mod.ensure_html2canvas(["a"])
            result = mod.ensure_html2canvas(["b"])
            # Already loaded — no script prepended
            assert result == ["b"]
        finally:
            mod._LOADED = False
