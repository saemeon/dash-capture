# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.capture — core capture API."""

import inspect
import io

from dash import dcc, html
from dash_fn_form import FieldHook, FromComponent

from dash_capture._wizard_callbacks import _make_snapshot_fn, _to_src
from dash_capture.capture import (
    CaptureBinding,
    FromPlotly,
    _default_renderer,
    _get_nested,
    capture_binding,
    capture_element,
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

    def test_with_strategy(self):
        from dash_capture import plotly_strategy

        def renderer(_target):
            pass

        result = capture_graph(
            "g2",
            renderer=renderer,
            strategy=plotly_strategy(strip_title=True, strip_legend=True),
        )
        assert isinstance(result, html.Div)


# ---------------------------------------------------------------------------
# Default renderer (passthrough)
# ---------------------------------------------------------------------------


class TestDefaultRenderer:
    """The default renderer is a zero-dependency passthrough.

    It must:
      - write the captured bytes through unchanged
      - take only ``(_target, _snapshot_img)`` so the wizard shows no
        form fields (just Generate + Download)
      - be importable without matplotlib (regression for the historic
        ``from dash_capture.mpl import snapshot_renderer`` default)
    """

    def test_writes_bytes_unchanged(self):
        target = io.BytesIO()
        payload = b"\x89PNG\r\n\x1a\nfake-image-data"
        _default_renderer(target, lambda: payload)
        assert target.getvalue() == payload

    def test_signature_has_no_form_fields(self):
        params = inspect.signature(_default_renderer).parameters
        # Only the two magic params, no user-facing fields
        assert list(params) == ["_target", "_snapshot_img"]

    def test_used_by_capture_graph_when_renderer_none(self):
        # Construct a wizard with no explicit renderer; the form must
        # have zero generated fields because _default_renderer has none.
        result = capture_graph("g-default")
        assert isinstance(result, html.Div)

    def test_used_by_capture_element_when_renderer_none(self):
        result = capture_element("el-default")
        assert isinstance(result, html.Div)

    def test_no_matplotlib_import_in_capture_module(self):
        # Regression guard: capture.py must not import matplotlib at any
        # scope (module-level OR inside a function), because the default
        # renderer must work without the [mpl] extra installed. Historic
        # bug: capture_graph used to do `from dash_capture.mpl import
        # snapshot_renderer` inside `if renderer is None:`, which forced
        # matplotlib on every default user.
        import ast
        import pathlib

        import dash_capture.capture

        source = pathlib.Path(dash_capture.capture.__file__).read_text()
        tree = ast.parse(source)
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend(
                    f"line {node.lineno}: import {alias.name}"
                    for alias in node.names
                    if alias.name == "matplotlib"
                    or alias.name.startswith("matplotlib.")
                )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (
                    node.module == "matplotlib"
                    or node.module.startswith("matplotlib.")
                    or node.module == "dash_capture.mpl"
                )
            ):
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
        assert not offenders, (
            "dash_capture.capture must not import matplotlib (or "
            "dash_capture.mpl) at any scope. Offenders:\n  " + "\n  ".join(offenders)
        )
