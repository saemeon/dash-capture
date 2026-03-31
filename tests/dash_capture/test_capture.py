# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.capture — core capture API."""

from dash import dcc, html
from dash_fn_form import FieldHook, FromComponent

from dash_capture._wizard_callbacks import _make_snapshot_fn, _to_src
from dash_capture.capture import (
    CaptureBinding,
    FromPlotly,
    _get_nested,
    capture_binding,
    capture_graph,
)

# ---------------------------------------------------------------------------
# FromPlotly hook
# ---------------------------------------------------------------------------


class TestFromPlotly:
    def test_is_field_hook_subclass(self):
        assert issubclass(FromPlotly, FieldHook)

    def test_is_from_component_subclass(self):
        assert issubclass(FromPlotly, FromComponent)

    def test_construction(self):
        g = dcc.Graph(id="g1")
        hook = FromPlotly("layout.title.text", g)
        assert hook.path == "layout.title.text"

    def test_get_default_extracts_value(self):
        g = dcc.Graph(id="g2")
        hook = FromPlotly("layout.title.text", g)
        figure = {"layout": {"title": {"text": "Hello"}}}
        assert hook.get_default(figure) == "Hello"

    def test_get_default_missing_path(self):
        g = dcc.Graph(id="g3")
        hook = FromPlotly("layout.title.text", g)
        assert hook.get_default({}) is None

    def test_get_default_no_args(self):
        g = dcc.Graph(id="g4")
        hook = FromPlotly("layout.title.text", g)
        assert hook.get_default() is None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestGetNested:
    def test_simple_path(self):
        assert _get_nested({"a": 1}, "a") == 1

    def test_deep_path(self):
        assert _get_nested({"a": {"b": {"c": 3}}}, "a.b.c") == 3

    def test_missing_returns_none(self):
        assert _get_nested({"a": 1}, "b") is None

    def test_non_dict_returns_none(self):
        assert _get_nested("string", "a") is None

    def test_partial_path_returns_none(self):
        assert _get_nested({"a": {"b": 2}}, "a.b.c") is None


class TestMakeSnapshotFn:
    def test_decodes_base64(self):
        import base64

        raw = b"fake-png-data"
        b64 = "data:image/png;base64," + base64.b64encode(raw).decode()
        fn = _make_snapshot_fn(b64)
        assert fn() == raw


class TestToSrc:
    def test_format(self):
        result = _to_src(b"\x89PNG")
        assert result.startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# CaptureBinding
# ---------------------------------------------------------------------------


class TestCaptureBinding:
    def test_construction(self):
        store = dcc.Store(id="s1")
        b = CaptureBinding(store=store, store_id="s1", element_id="el1")
        assert b.store_id == "s1"
        assert b.element_id == "el1"

    def test_capture_binding_factory_string(self):
        b = capture_binding("my-graph")
        assert isinstance(b, CaptureBinding)
        assert b.element_id == "my-graph"
        assert isinstance(b.store, dcc.Store)

    def test_capture_binding_factory_component(self):
        g = dcc.Graph(id="my-g")
        b = capture_binding(g)
        assert b.element_id == "my-g"

    def test_store_ids_unique(self):
        b1 = capture_binding("a")
        b2 = capture_binding("b")
        assert b1.store_id != b2.store_id


# ---------------------------------------------------------------------------
# High-level API: capture_graph / capture_graph
# ---------------------------------------------------------------------------


class TestCaptureGraph:
    def test_returns_html_div(self):
        def renderer(_target):
            pass

        result = capture_graph("test-graph", renderer=renderer)
        assert isinstance(result, html.Div)

    def test_capture_graph_is_alias(self):
        assert capture_graph is capture_graph

    def test_with_custom_renderer(self):
        def my_renderer(_target, _snapshot_img, title: str = ""):
            pass

        result = capture_graph("g", renderer=my_renderer)
        assert isinstance(result, html.Div)

    def test_with_strip_options(self):
        def renderer(_target):
            pass

        result = capture_graph(
            "g2",
            renderer=renderer,
            strip_title=True,
            strip_legend=True,
        )
        assert isinstance(result, html.Div)
