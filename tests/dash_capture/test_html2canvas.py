# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture._html2canvas — vendored html2canvas inclusion."""

import dash
from dash._callback import GLOBAL_INLINE_SCRIPTS

from dash_capture._html2canvas import _MARKER, _read_html2canvas, ensure_html2canvas


def _our_in_globals() -> int:
    return sum(1 for s in GLOBAL_INLINE_SCRIPTS if _MARKER in s)


def _our_in_app(app) -> int:
    return sum(1 for s in getattr(app, "_inline_scripts", []) if _MARKER in s)


class TestReadHtml2canvas:
    def test_returns_minified_js(self):
        js = _read_html2canvas()
        assert isinstance(js, str)
        assert len(js) > 100  # minified JS is large
        assert "html2canvas" in js


class TestEnsureHtml2canvas:
    def test_returns_children_unchanged(self):
        result = ensure_html2canvas(["child1"])
        assert result == ["child1"]

    def test_queues_in_global_inline_scripts(self):
        # Dash's module-level queue is the integration point.
        # Even if no app exists yet, this is where we register.
        before = _our_in_globals()
        ensure_html2canvas([])
        # Either we added it to GLOBAL, or it was already drained
        # into some prior app's _inline_scripts — either way, the
        # script will be emitted on the next page serve.
        assert _our_in_globals() >= before

    def test_idempotent_within_queue(self):
        # Repeated calls must not duplicate before the drain.
        ensure_html2canvas([])
        count_after_first = _our_in_globals()
        ensure_html2canvas([])
        ensure_html2canvas([])
        assert _our_in_globals() == count_after_first

    def test_works_without_current_app(self):
        # The key improvement: ensure_html2canvas can be called in
        # layout-building modules before any Dash() instance exists.
        # (In this test runner other apps already exist — but the
        # function must not raise or depend on an app.)
        result = ensure_html2canvas(["x", "y"])
        assert result == ["x", "y"]

    def test_drain_moves_to_app_inline_scripts(self):
        app = dash.Dash(__name__)
        ensure_html2canvas([])
        # Dash drains GLOBAL_INLINE_SCRIPTS into self._inline_scripts
        # when rendering scripts HTML (once per page serve).
        app._generate_scripts_html()
        assert _our_in_app(app) == 1

    def test_idempotent_across_drain(self):
        # After a drain, a subsequent call must not re-queue (which would
        # produce a duplicate in the app after the next serve).
        app = dash.Dash(__name__)
        ensure_html2canvas([])
        app._generate_scripts_html()
        before = _our_in_app(app)

        ensure_html2canvas([])
        app._generate_scripts_html()
        assert _our_in_app(app) == before, "must not duplicate after drain"
