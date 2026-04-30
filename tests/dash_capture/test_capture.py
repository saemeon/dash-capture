# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.capture — core capture API."""

import inspect
import io

import pytest
from dash import dcc, html
from dash_fn_form import FieldHook, FromComponent

from dash_capture._wizard import (
    _make_snapshot_fn,
    _resolve_download_name,
    _to_src,
)
from dash_capture.capture import (
    CaptureBinding,
    FromPlotly,
    WizardConfig,
    _classify_params,
    _default_renderer,
    _get_nested,
    _make_wizard,
    _NullFnForm,
    _renderer_meta,
    _RendererMeta,
    _resolve_show_format,
    capture_binding,
    capture_element,
    capture_graph,
)
from dash_capture.strategies import html2canvas_strategy, plotly_strategy

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


class TestCaptureResolverPath:
    """Construction-time guards for the ``capture_resolver`` flow.

    The resolver flow registers four extra callbacks for snapshot caching
    (resolve → cache_check → JS capture → cache_update) plus a
    clear-cache-on-close. Multiple of these output to the same
    ``snapshot_cache`` store, so they need ``allow_duplicate=True`` —
    forgetting that raises a ``DuplicateCallback`` exception at Dash
    registration time, before the app ever serves a request.

    These tests do nothing more than instantiate the wizard. If Dash's
    callback validation fails, the test fails. That's the entire point.
    """

    def test_capture_element_with_resolver_constructs(self):
        """Smoke test for the resolver-flow callback wiring.

        Catches duplicate-Output regressions in ``_register_capture_resolved``
        and ``clear_cache_on_close`` — both target ``snapshot_cache_store``.
        """
        import dash

        from dash_capture import capture_element

        # Fresh app per test so callback registration starts clean.
        dash.Dash(__name__)

        def renderer(
            _target,
            _snapshot_img,
            width: int = 100,
            capture_width: int = 100,
        ):
            _target.write(_snapshot_img())

        def resolve(width, **_):
            return {"capture_width": width}

        result = capture_element(
            "el",
            renderer=renderer,
            capture_resolver=resolve,
        )
        assert isinstance(result, html.Div)

    def test_capture_graph_with_resolver_constructs(self):
        """Same guard, for the ``capture_graph`` entry point."""
        import dash

        from dash_capture import capture_graph

        dash.Dash(__name__)

        def renderer(
            _target,
            _snapshot_img,
            width: int = 100,
            capture_width: int = 100,
        ):
            _target.write(_snapshot_img())

        def resolve(width, **_):
            return {"capture_width": width}

        result = capture_graph(
            "g-resolver",
            renderer=renderer,
            capture_resolver=resolve,
        )
        assert isinstance(result, html.Div)

    def test_resolver_js_capture_listens_to_cache_miss_not_resolved(self):
        """Architectural assertion — encodes WHY the cache works.

        The clientside JS capture must be triggered by the ``cache_miss``
        store, not ``resolved``. If a refactor accidentally re-points it
        at ``resolved``, the cache silently degrades: every ``resolved``
        update would fire the JS and overwrite the cached snapshot, which
        is exactly the bug this whole architecture exists to prevent.

        We introspect Dash's global callback registry and assert the JS
        clientside callback whose output is the snapshot store has its
        Input on ``_dcap_cache_miss_*``.
        """
        from dash._callback import GLOBAL_CALLBACK_LIST

        from dash_capture import capture_element

        n_before = len(GLOBAL_CALLBACK_LIST)

        def renderer(
            _target,
            _snapshot_img,
            width: int = 100,
            capture_width: int = 100,
        ):
            _target.write(_snapshot_img())

        def resolve(width, **_):
            return {"capture_width": width}

        capture_element("el2", renderer=renderer, capture_resolver=resolve)
        added = GLOBAL_CALLBACK_LIST[n_before:]

        # Find the clientside callback whose output is the snapshot store.
        # That's the JS capture callback. There's exactly one.
        snapshot_js_callbacks = [
            cb
            for cb in added
            if cb.get("clientside_function")
            and "_dcap_snapshot_" in str(cb.get("output", ""))
            and "_dcap_snapshot_cache_" not in str(cb.get("output", ""))
        ]
        assert len(snapshot_js_callbacks) == 1, (
            f"Expected exactly one clientside JS capture callback writing "
            f"to the snapshot store, found {len(snapshot_js_callbacks)}."
        )

        js_cb = snapshot_js_callbacks[0]
        input_ids = [inp["id"] for inp in js_cb["inputs"]]

        assert any("_dcap_cache_miss_" in i for i in input_ids), (
            f"JS capture callback must be wired to cache_miss store; "
            f"found inputs {input_ids!r}. If this is now '_dcap_resolved_*' "
            f"the cache is broken — the JS capture will fire on every "
            f"resolver update, including cache hits."
        )
        assert not any("_dcap_resolved_" in i for i in input_ids), (
            f"JS capture callback is wired to resolved store directly. "
            f"That bypasses the cache. Inputs: {input_ids!r}."
        )

    def test_cache_check_clears_cache_miss_on_hit(self):
        """Regression test for cache poisoning.

        Sequence that used to corrupt the cache:
          1. Capture at A → cache[A] = snapA, cache_miss = A
          2. Capture at B → cache[B] = snapB, cache_miss = B
          3. Switch back to A → HIT.

        At step 3 the hit-callback writes snapA to snapshot_store. If
        cache_miss is still B (left over from step 2), the cache_update
        callback that fires on snapshot_store changes would re-store snapA
        under hash(B) — corrupting the B entry.

        The fix: hit-callback explicitly clears cache_miss to None. This
        test asserts the second output of cache_check_and_apply is None
        (not no_update) on a hit.
        """
        import dash
        from dash._callback import GLOBAL_CALLBACK_MAP

        from dash_capture import capture_element

        keys_before = set(GLOBAL_CALLBACK_MAP.keys())

        def renderer(
            _target,
            _snapshot_img,
            width: int = 100,
            capture_width: int = 100,
        ):
            _target.write(_snapshot_img())

        def resolve(width, **_):
            return {"capture_width": width}

        capture_element("el-poison", renderer=renderer, capture_resolver=resolve)
        added_keys = set(GLOBAL_CALLBACK_MAP.keys()) - keys_before

        # Find cache_check_and_apply by its dual output (snapshot + cache_miss).
        cache_check_key = next(
            (k for k in added_keys if "_dcap_snapshot_" in k and "_dcap_cache_miss_" in k),
            None,
        )
        assert cache_check_key is not None, (
            "Couldn't locate cache_check_and_apply callback in GLOBAL_CALLBACK_MAP."
        )

        # `callback` is the Dash-wrapped function (expects outputs_list etc).
        # `__wrapped__` is the original `cache_check_and_apply` from the
        # closure inside _register_capture_resolved — that's what we want
        # to call with raw args.
        wrapped = GLOBAL_CALLBACK_MAP[cache_check_key]["callback"]
        fn = wrapped.__wrapped__
        capture_opts = {"capture_width": 100}

        # ── Cache HIT ────────────────────────────────────────────────
        # Pre-populate the cache as if a previous capture ran.
        from dash_capture._wizard import _hash_capture_options

        key = _hash_capture_options(capture_opts)
        cache_dict = {key: "data:image/png;base64,FAKE_SNAP_A"}

        result = fn(capture_opts, cache_dict)
        # Expected: (cached_snapshot, None) — the None is the fix. If the
        # implementation regresses to returning dash.no_update here,
        # cache_update will re-cache the hit's snapshot under a stale
        # cache_miss key and poison the cache.
        assert result[0] == "data:image/png;base64,FAKE_SNAP_A", (
            "On cache hit, snapshot output should be the cached value."
        )
        assert result[1] is None, (
            f"On cache hit, cache_miss output must be None to clear stale "
            f"opts from a previous miss. Got {result[1]!r}. If this is "
            f"dash.no_update, the cache-poisoning bug is back."
        )

        # ── Cache MISS ───────────────────────────────────────────────
        # Empty cache; same opts.
        result = fn(capture_opts, {})
        assert result[0] is dash.no_update, (
            "On cache miss, snapshot output should be no_update so the "
            "JS clientside callback runs and writes the fresh capture."
        )
        assert result[1] == capture_opts, (
            "On cache miss, cache_miss output should be the capture_opts "
            "to trigger the JS callback."
        )


class TestCaptureElementWiresParams:
    """``capture_element`` forwards renderer ``capture_*`` params to the
    default html2canvas strategy so the live-resize preprocess kicks in."""

    def test_renderer_with_capture_width_triggers_reflow_preprocess(self):
        # capture_element must hand the renderer signature to
        # html2canvas_strategy via _params so the preprocess gets emitted.
        # Mirror of how capture_graph already does it for plotly_strategy.
        from dash_capture import html2canvas_strategy

        def renderer(_target, _snapshot_img, capture_width: int = 800):
            _target.write(_snapshot_img())

        s = html2canvas_strategy(
            _params=__import__("inspect").signature(renderer).parameters
        )
        assert s.preprocess is not None
        assert "opts.width" in s.preprocess

    def test_capture_element_does_not_crash_with_capture_dim_renderer(self):
        def renderer(
            _target,
            _snapshot_img,
            capture_width: int = 1200,
            capture_height: int = 800,
        ):
            _target.write(_snapshot_img())

        result = capture_element("el-reflow", renderer=renderer)
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
        default that forced matplotlib on every user)
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
        # renderer must work without matplotlib installed. Historic bug:
        # capture_graph used to do `from dash_capture.mpl import
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
                    node.module == "matplotlib" or node.module.startswith("matplotlib.")
                )
            ):
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
        assert not offenders, (
            "dash_capture.capture must not import matplotlib at any scope. "
            "Offenders:\n  " + "\n  ".join(offenders)
        )


# ---------------------------------------------------------------------------
# show_format auto-resolution
# ---------------------------------------------------------------------------


def _find_format_dropdown_style(
    layout: html.Div, format_id_prefix: str = "_dcap_format_"
):
    """Walk a wizard layout tree and return the style dict of the div
    that wraps the format dropdown — i.e. the parent of any component
    whose id starts with ``_dcap_format_``. Returns ``None`` if no
    format dropdown is present in the tree.
    """

    def walk(node):
        if hasattr(node, "children"):
            children = node.children
            if children is None:
                return None
            if not isinstance(children, list | tuple):
                children = [children]
            for child in children:
                # Found the format dropdown — return *this* node's style
                # (the parent div is what gets display:none).
                if (
                    getattr(child, "id", None)
                    and isinstance(child.id, str)
                    and child.id.startswith(format_id_prefix)
                ):
                    return getattr(node, "style", None)
                found = walk(child)
                if found is not None:
                    return found
        return None

    return walk(layout)


class TestResolveShowFormat:
    """Unit tests for the show_format auto-resolution helper.

    The rule is: ``None`` (the default) means "auto" — show iff the
    renderer produces an image. Explicit ``True`` / ``False`` always
    overrides the auto behavior.
    """

    def test_none_with_snapshot_resolves_true(self):
        assert _resolve_show_format(None, has_snapshot=True) is True

    def test_none_without_snapshot_resolves_false(self):
        assert _resolve_show_format(None, has_snapshot=False) is False

    def test_explicit_true_overrides_auto(self):
        # User can force the dropdown on even for fig-data-only renderers
        assert _resolve_show_format(True, has_snapshot=False) is True

    def test_explicit_false_overrides_auto(self):
        # User can force the dropdown off even for snapshot renderers
        assert _resolve_show_format(False, has_snapshot=True) is False


class TestShowFormatInWizard:
    """End-to-end checks: build a wizard with various renderers and
    verify the format dropdown's display style matches the auto-rule.
    """

    def test_snapshot_renderer_shows_format(self):
        # Default renderer takes _snapshot_img → format dropdown visible
        wizard = capture_graph("g-fmt-snap")
        style = _find_format_dropdown_style(wizard)
        assert style is not None, "format dropdown not found in wizard tree"
        assert style.get("display") != "none", (
            f"snapshot renderer should show the format dropdown, got style={style}"
        )

    def test_fig_data_only_renderer_hides_format(self):
        def fig_only_renderer(_target, _fig_data):
            _target.write(b"")

        wizard = capture_graph("g-fmt-fig", renderer=fig_only_renderer)
        style = _find_format_dropdown_style(wizard)
        assert style is not None, "format dropdown div not found in wizard tree"
        assert style.get("display") == "none", (
            f"fig-data-only renderer should hide the format dropdown, got style={style}"
        )

    def test_explicit_show_format_false_hides_for_snapshot(self):
        def snap_renderer(_target, _snapshot_img):
            _target.write(_snapshot_img())

        wizard = capture_graph(
            "g-fmt-explicit-false",
            renderer=snap_renderer,
            show_format=False,
        )
        style = _find_format_dropdown_style(wizard)
        assert style is not None
        assert style.get("display") == "none"

    def test_explicit_show_format_true_shows_for_fig_data(self):
        def fig_only_renderer(_target, _fig_data):
            _target.write(b"")

        wizard = capture_graph(
            "g-fmt-explicit-true",
            renderer=fig_only_renderer,
            show_format=True,
        )
        style = _find_format_dropdown_style(wizard)
        assert style is not None
        assert style.get("display") != "none"


# ---------------------------------------------------------------------------
# _classify_params + _renderer_meta (validation is always-on)
# ---------------------------------------------------------------------------


class TestClassifyParams:
    """``_classify_params`` walks a renderer's signature without validation."""

    def test_snapshot_only(self):
        def fn(_target, _snapshot_img):
            pass

        meta = _classify_params(fn)
        assert meta.has_snapshot is True
        assert meta.has_fig_data is False
        assert meta.active_capture == ()
        assert meta.fields == ()

    def test_fig_data_only(self):
        def fn(_target, _fig_data):
            pass

        meta = _classify_params(fn)
        assert meta.has_snapshot is False
        assert meta.has_fig_data is True
        assert meta.fields == ()

    def test_both_magic_plus_user_fields(self):
        def fn(_target, _snapshot_img, _fig_data, title: str = "", dpi: int = 150):
            pass

        meta = _classify_params(fn)
        assert meta.has_snapshot is True
        assert meta.has_fig_data is True
        assert meta.fields == ("title", "dpi")

    def test_active_capture_params(self):
        def fn(
            _target, _snapshot_img, capture_width: int = 800, capture_height: int = 600
        ):
            pass

        meta = _classify_params(fn)
        assert meta.active_capture == ("capture_width", "capture_height")
        # capture_* params are NOT user fields — they're plumbed to the JS layer
        assert meta.fields == ()

    def test_user_fields_only_no_magic(self):
        # Renderer that takes _target and a regular field — no snapshot, no fig_data
        def fn(_target, message: str = ""):
            pass

        meta = _classify_params(fn)
        assert meta.has_snapshot is False
        assert meta.has_fig_data is False
        assert meta.fields == ("message",)


class TestRendererMeta:
    """``_renderer_meta`` validates + classifies + caches."""

    def test_validation_result_cached_on_fn(self):
        def fn(_target, _snapshot_img, title: str = ""):
            pass

        meta = _renderer_meta(fn)
        assert isinstance(meta, _RendererMeta)
        # Cached on the function for subsequent calls
        assert getattr(fn, "__dcap_meta__", None) is meta

    def test_raises_when_target_missing(self):
        def fn(_snapshot_img):
            pass

        with pytest.raises(ValueError, match="must declare a ``_target``"):
            _renderer_meta(fn)

    def test_raises_on_typo_with_suggestion(self):
        def fn(_target, _snaphot_img):  # typo: missing 's'
            pass

        with pytest.raises(ValueError) as exc_info:
            _renderer_meta(fn)
        msg = str(exc_info.value)
        assert "_snaphot_img" in msg
        assert "Did you mean" in msg
        assert "_snapshot_img" in msg  # difflib suggestion

    def test_raises_on_unknown_magic_param(self):
        def fn(_target, _wat):
            pass

        with pytest.raises(ValueError, match="unknown magic parameter"):
            _renderer_meta(fn)

    def test_raises_on_image_typo(self):
        def fn(_target, _snapshot_image):  # extra 'image' suffix
            pass

        with pytest.raises(ValueError) as exc_info:
            _renderer_meta(fn)
        assert "_snapshot_image" in str(exc_info.value)

    def test_accepts_capture_star_params(self):
        def fn(_target, _snapshot_img, capture_width: int = 800):
            pass

        meta = _renderer_meta(fn)
        # capture_* doesn't start with `_` so it's not subject to the magic-name
        # whitelist; should pass validation and end up in active_capture
        assert meta.active_capture == ("capture_width",)
        assert meta.fields == ()

    def test_accepts_minimal_target_only(self):
        # A renderer with just _target is valid (writes constant content)
        def fn(_target):
            _target.write(b"const")

        meta = _renderer_meta(fn)
        assert meta.has_snapshot is False
        assert meta.has_fig_data is False

    def test_uses_cached_meta(self):
        def fn(_target, _snapshot_img, title: str = ""):
            pass

        first = _renderer_meta(fn)
        second = _renderer_meta(fn)
        assert first is second  # exact same object — no recomputation

    def test_lazy_fallback_for_undecorated(self):
        def fn(_target, _snapshot_img, title: str = ""):
            pass

        # No __dcap_meta__ attribute → must compute lazily
        assert not hasattr(fn, "__dcap_meta__")
        meta = _renderer_meta(fn)
        assert meta.has_snapshot is True
        assert meta.fields == ("title",)

    def test_lazy_fallback_for_default_renderer(self):
        # _default_renderer is intentionally not decorated; verify the
        # lazy path works for it.
        meta = _renderer_meta(_default_renderer)
        assert meta.has_snapshot is True
        assert meta.fields == ()

    def test_undecorated_typo_raises(self):
        # The whole point of "always-on" validation: a typo in an
        # undecorated renderer must raise at _renderer_meta time, not
        # silently produce a wizard with a broken form field.
        def fn(_target, _snaphot_img):  # typo
            pass

        with pytest.raises(ValueError) as exc_info:
            _renderer_meta(fn)
        assert "_snaphot_img" in str(exc_info.value)
        assert "_snapshot_img" in str(exc_info.value)  # difflib suggestion

    def test_undecorated_missing_target_raises(self):
        def fn(_snapshot_img):  # no _target
            pass

        with pytest.raises(ValueError, match="_target"):
            _renderer_meta(fn)

    def test_undecorated_validation_result_is_cached(self):
        # After the first _renderer_meta call, the validation+classification
        # result is attached to the callable so subsequent calls are free.
        def fn(_target, _snapshot_img, title: str = ""):
            pass

        assert not hasattr(fn, "__dcap_meta__")
        meta = _renderer_meta(fn)
        assert getattr(fn, "__dcap_meta__", None) is meta
        # Second call returns the cached object, no re-validation
        assert _renderer_meta(fn) is meta

    def test_capture_graph_propagates_validation_error(self):
        # End-to-end: passing an undecorated typo'd renderer to
        # capture_graph raises before the wizard is constructed.
        from dash_capture import capture_graph

        def bad(_target, _snaphot_img):
            pass

        with pytest.raises(ValueError, match="_snaphot_img"):
            capture_graph("g", renderer=bad)

    def test_setattr_failure_does_not_crash(self):
        # Some callables reject attribute assignment (e.g. bound methods on
        # slotted classes). Validation still runs; caching just doesn't.
        class R:
            __slots__ = ()

            def __call__(self, _target, _snapshot_img):
                pass

        r = R()
        # Validation + classification should still succeed; the setattr
        # inside _renderer_meta must swallow the failure silently.
        meta = _renderer_meta(r)
        assert meta.has_snapshot is True


# ---------------------------------------------------------------------------
# No-fields short-circuit (_NullFnForm)
# ---------------------------------------------------------------------------


def _find_config_in_wizard(wizard: html.Div):
    """Walk a wizard tree and return the first object with a non-trivial
    ``states`` attribute (i.e. the FnForm-or-stub config component).
    Returns None if no such component is found.
    """
    seen = set()

    def walk(node):
        if id(node) in seen:
            return None
        seen.add(id(node))
        # Any component carrying a `.states` attribute is a form-config
        if hasattr(node, "states") and isinstance(getattr(node, "states", None), list):
            return node
        if hasattr(node, "children"):
            children = node.children
            if children is None:
                return None
            if not isinstance(children, list | tuple):
                children = [children]
            for child in children:
                found = walk(child)
                if found is not None:
                    return found
        return None

    return walk(wizard)


class TestNullFnForm:
    """``_NullFnForm`` is a drop-in stub for FnForm with zero fields."""

    def test_is_dash_div_subclass(self):
        # Must be placeable directly in a Dash layout tree
        assert issubclass(_NullFnForm, html.Div)

    def test_construction_sets_id(self):
        stub = _NullFnForm("my-config-id")
        assert stub.id == "my-config-id"

    def test_states_is_empty_list(self):
        stub = _NullFnForm("c")
        assert stub.states == []

    def test_register_callbacks_are_noop(self):
        stub = _NullFnForm("c")
        # Should not raise — no-op
        stub.register_populate_callback(None)
        stub.register_restore_callback(None)

    def test_build_kwargs_returns_empty(self):
        stub = _NullFnForm("c")
        assert stub.build_kwargs(()) == {}
        assert stub.build_kwargs(("ignored",)) == {}


class TestNoFieldsShortCircuit:
    """When the renderer has no form fields, _make_wizard must skip
    FnForm entirely and use the lightweight _NullFnForm stub.
    """

    def test_default_renderer_uses_null_stub(self):
        # capture_graph() with no renderer override → _default_renderer →
        # zero fields → _NullFnForm short-circuit
        wizard = capture_graph("g-shortcut-default")
        config = _find_config_in_wizard(wizard)
        assert config is not None
        assert isinstance(config, _NullFnForm)

    def test_capture_element_default_uses_null_stub(self):
        wizard = capture_element("el-shortcut-default")
        config = _find_config_in_wizard(wizard)
        assert config is not None
        assert isinstance(config, _NullFnForm)

    def test_renderer_with_field_uses_real_fnform(self):
        # Renderer with a user field → must NOT short-circuit, must use FnForm
        from dash_fn_form import FnForm

        def with_title(_target, _snapshot_img, title: str = ""):
            _target.write(_snapshot_img())

        wizard = capture_graph("g-shortcut-fnform", renderer=with_title)
        config = _find_config_in_wizard(wizard)
        assert config is not None
        assert isinstance(config, FnForm)
        assert not isinstance(config, _NullFnForm)

    def test_does_not_invoke_fnform_for_default_renderer(self):
        # Stronger guard: if FnForm is constructed at all on the default
        # path, this test fails. Patch dash_capture.capture.FnForm with a
        # spy that records calls.
        from dash_fn_form import FnForm as RealFnForm

        import dash_capture.capture as cap_module

        calls: list[tuple] = []

        class SpyFnForm(RealFnForm):
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))
                super().__init__(*args, **kwargs)

        original = cap_module.FnForm
        cap_module.FnForm = SpyFnForm  # type: ignore[misc]
        try:
            capture_graph("g-shortcut-spy")
        finally:
            cap_module.FnForm = original  # type: ignore[misc]

        assert calls == [], (
            f"FnForm should not be constructed for the default no-fields "
            f"renderer; got {len(calls)} call(s): {calls}"
        )

    def test_does_invoke_fnform_when_user_passes_field_specs(self):
        # Even if the renderer has zero fields, an explicit field_specs
        # arg means the user wants form behavior — don't short-circuit.
        from dash_fn_form import Field

        def no_field_renderer(_target, _snapshot_img):
            _target.write(_snapshot_img())

        wizard = capture_graph(
            "g-shortcut-explicit-specs",
            renderer=no_field_renderer,
            field_specs={"some_field": Field()},
        )
        config = _find_config_in_wizard(wizard)
        assert config is not None
        # Real FnForm — not the stub — because field_specs was explicit
        from dash_fn_form import FnForm

        assert isinstance(config, FnForm)
        assert not isinstance(config, _NullFnForm)

    def test_short_circuit_wizard_still_renders_format_dropdown(self):
        # The format dropdown is independent of FnForm — verify it still
        # appears in the no-fields short-circuit path (since the default
        # renderer produces an image).
        wizard = capture_graph("g-shortcut-fmt")
        style = _find_format_dropdown_style(wizard)
        assert style is not None
        assert style.get("display") != "none"


# ---------------------------------------------------------------------------
# html2canvas script injection — driven by strategy, not public function
# ---------------------------------------------------------------------------


class TestHtml2canvasScriptInjection:
    """The vendored html2canvas.min.js injection used to live only in
    ``capture_element``. After the unification it moved into
    ``_make_wizard`` so that ``capture_graph`` users who explicitly pass
    ``strategy=html2canvas_strategy()`` also get the script. This was a
    latent bug — capture_graph + html2canvas silently failed before.
    """

    def _injected_marker_in_app(self) -> bool:
        """Check whether html2canvas has been registered for this app.

        The new implementation queues via ``GLOBAL_INLINE_SCRIPTS``
        (pre-drain) and ``app._inline_scripts`` (post-drain). Either
        indicates the script will be emitted on next page serve.
        """
        import dash
        from dash._callback import GLOBAL_INLINE_SCRIPTS

        from dash_capture._html2canvas import _MARKER

        if any(_MARKER in s for s in GLOBAL_INLINE_SCRIPTS):
            return True
        try:
            app = dash.get_app()
        except Exception:
            return False
        return any(_MARKER in s for s in getattr(app, "_inline_scripts", []))

    def test_capture_element_default_injects_script(self):
        # Fresh app per test — get_app() gives the most recent
        import dash

        dash.Dash(__name__)
        capture_element("el-h2c-default")
        assert self._injected_marker_in_app(), (
            "capture_element with default html2canvas strategy must queue "
            "the vendored script for emission on page serve"
        )

    def test_capture_graph_with_explicit_html2canvas_injects_script(self):
        # The latent bug fix: capture_graph + html2canvas_strategy() must
        # also trigger script injection. Before this change it didn't.
        import dash

        from dash_capture import html2canvas_strategy

        dash.Dash(__name__)
        capture_graph("g-h2c-explicit", strategy=html2canvas_strategy())
        assert self._injected_marker_in_app(), (
            "capture_graph with strategy=html2canvas_strategy() must also "
            "queue the vendored script — this was a latent bug fixed by "
            "moving the injection into _make_wizard."
        )

    def test_capture_graph_with_plotly_does_not_inject_script(self):
        # Conversely, plain capture_graph (Plotly strategy) must NOT
        # queue html2canvas — wasted bytes for users who don't need it.
        import dash
        from dash._callback import GLOBAL_INLINE_SCRIPTS

        from dash_capture._html2canvas import _MARKER

        # Fresh app + baseline queue size for this test
        app = dash.Dash(__name__)
        before = sum(1 for s in GLOBAL_INLINE_SCRIPTS if _MARKER in s)
        before += sum(1 for s in getattr(app, "_inline_scripts", []) if _MARKER in s)

        capture_graph("g-h2c-not-needed")

        after = sum(1 for s in GLOBAL_INLINE_SCRIPTS if _MARKER in s)
        after += sum(1 for s in getattr(app, "_inline_scripts", []) if _MARKER in s)
        assert after == before, (
            "capture_graph with default plotly_strategy must not queue "
            "html2canvas (wasted bytes)"
        )


# ---------------------------------------------------------------------------
# WizardConfig dataclass
# ---------------------------------------------------------------------------


class TestWizardConfig:
    """``WizardConfig`` is the dataclass threaded through ``_make_wizard``
    and ``wire_wizard``. Tests verify field defaults, that all required
    fields are present, and that ``_make_wizard(cfg)`` produces a valid
    wizard from a minimal config.
    """

    def test_minimum_required_fields(self):
        # Must accept just the five required fields, defaults for the rest
        cfg = WizardConfig(
            element_id="test",
            renderer=_default_renderer,
            strategy=plotly_strategy(),
            trigger="Capture",
            filename="x.png",
        )
        assert cfg.element_id == "test"
        assert cfg.renderer is _default_renderer
        assert cfg.preprocess is None
        assert cfg.autogenerate is True  # default
        assert cfg.persist is True  # default
        assert cfg.styles is None
        assert cfg.field_components == "dcc"
        assert cfg.show_format is None  # default = auto
        assert cfg.actions is None

    def test_full_construction(self):
        # All fields populated
        def fn(_target, _snapshot_img, title: str = ""):
            _target.write(_snapshot_img())

        cfg = WizardConfig(
            element_id="my-graph",
            renderer=fn,
            strategy=plotly_strategy(strip_title=True),
            trigger="Export",
            filename="export.png",
            preprocess="// custom JS",
            autogenerate=False,
            persist=False,
            styles={"button": {"color": "red"}},
            class_names={"button": "my-btn"},
            field_specs=None,
            field_components="dmc",
            capture_resolver=None,
            show_format=True,
            wizard_header="Export Wizard",
            actions=None,
        )
        assert cfg.preprocess == "// custom JS"
        assert cfg.autogenerate is False
        assert cfg.persist is False
        assert cfg.styles == {"button": {"color": "red"}}
        assert cfg.field_components == "dmc"
        assert cfg.show_format is True
        assert cfg.wizard_header == "Export Wizard"

    def test_make_wizard_accepts_dataclass(self):
        # _make_wizard now takes a WizardConfig — verify it produces an
        # html.Div from a minimal config (no kwargs threading)
        cfg = WizardConfig(
            element_id="g-cfg-min",
            renderer=_default_renderer,
            strategy=plotly_strategy(),
            trigger="Capture",
            filename="x.png",
        )
        result = _make_wizard(cfg)
        assert isinstance(result, html.Div)

    def test_capture_graph_constructs_dataclass(self):
        # The public capture_graph wrapper bundles its kwargs into
        # WizardConfig and forwards to _make_wizard. Verify by walking
        # back from the result that the wizard was built.
        wizard = capture_graph("g-cfg-public")
        assert isinstance(wizard, html.Div)

    def test_capture_element_constructs_dataclass(self):
        wizard = capture_element("el-cfg-public")
        assert isinstance(wizard, html.Div)

    def test_html2canvas_via_capture_graph_through_dataclass(self):
        # Regression: capture_graph + html2canvas_strategy must still
        # queue the script after the dataclass refactor
        import dash
        from dash._callback import GLOBAL_INLINE_SCRIPTS

        from dash_capture._html2canvas import _MARKER

        dash.Dash(__name__)
        capture_graph(
            "g-cfg-h2c",
            strategy=html2canvas_strategy(),
        )
        app = dash.get_app()
        queued = any(_MARKER in s for s in GLOBAL_INLINE_SCRIPTS)
        drained = any(_MARKER in s for s in getattr(app, "_inline_scripts", []))
        assert queued or drained


# ---------------------------------------------------------------------------
# Download filename resolution (static and callable)
# ---------------------------------------------------------------------------


class TestResolveDownloadName:
    """Pure-function tests for ``_resolve_download_name`` — static vs
    callable filenames, format-extension patching, and fallback-on-error.
    """

    def test_static_filename_passes_through(self):
        assert _resolve_download_name("fig.png", "png", {}) == "fig.png"

    def test_static_filename_format_patched_for_jpeg(self):
        # "figure.png" + fmt="jpeg" → "figure.jpg" (we rename the ext)
        assert _resolve_download_name("figure.png", "jpeg", {}) == "figure.jpg"

    def test_static_filename_format_patched_for_webp(self):
        assert _resolve_download_name("figure.png", "webp", {}) == "figure.webp"

    def test_static_filename_png_no_patch(self):
        assert _resolve_download_name("figure.png", "png", {}) == "figure.png"

    def test_static_filename_no_extension_gets_one(self):
        # Original has no "." → whole name becomes the stem
        assert _resolve_download_name("figure", "jpeg", {}) == "figure.jpg"

    def test_callable_receives_field_kwargs(self):
        seen = {}

        def fn(**kwargs):
            seen.update(kwargs)
            return "out.png"

        _resolve_download_name(fn, "png", {"title": "Q1", "dpi": 150})
        assert seen == {"title": "Q1", "dpi": 150}

    def test_callable_result_used_verbatim_for_png(self):
        assert (
            _resolve_download_name(
                lambda title="chart": f"{title}.png", "png", {"title": "rev"}
            )
            == "rev.png"
        )

    def test_callable_result_format_patched(self):
        # Callable returns PNG name; fmt=jpeg rewrites to .jpg
        dl = _resolve_download_name(
            lambda title="chart": f"{title}.png", "jpeg", {"title": "rev"}
        )
        assert dl == "rev.jpg"

    def test_callable_exception_falls_back_to_default(self):
        def bad(**kwargs):
            raise RuntimeError("boom")

        dl = _resolve_download_name(bad, "png", {})
        assert dl == "capture.png"

    def test_callable_exception_fallback_still_format_patched(self):
        # Even when the callable fails and falls back, the format
        # extension is applied to the fallback name.
        def bad(**kwargs):
            raise RuntimeError("boom")

        dl = _resolve_download_name(bad, "jpeg", {})
        assert dl == "capture.jpg"

    def test_callable_kwargs_mismatch_falls_back(self):
        # Callable declares `title` but we pass `name` — the TypeError
        # is caught and falls back.
        def fn(title: str = "chart") -> str:
            return f"{title}.png"

        dl = _resolve_download_name(fn, "png", {"name": "wrong"})
        assert dl == "capture.png"


class TestDownloadCallbackWiring:
    """The download callback's Input/State shape depends on whether
    ``filename`` is a callable (needs form-field values) or a static
    string (doesn't).
    """

    def _find_download_state(self, uid_hint: str) -> list:
        """Locate the download callback's `state` list via GLOBAL_CALLBACK_MAP.

        dash-capture component IDs embed a random uid suffix; we scan
        for the one matching our hint.
        """
        from dash._callback import GLOBAL_CALLBACK_MAP

        for key, spec in GLOBAL_CALLBACK_MAP.items():
            if "_dcap_download_" in key and uid_hint in key and key.endswith(".data"):
                return spec.get("state", [])
        raise AssertionError(f"no download callback found for uid hint {uid_hint!r}")

    def test_static_filename_excludes_field_states(self):
        # Static string → callback depends only on preview_src and format
        def r(_target, _snapshot_img, title: str = "chart"):
            _target.write(_snapshot_img())

        capture_graph("g-static-fn", renderer=r, filename="fixed.png")
        state = self._find_download_state("g-static-fn")
        # state = [preview.src, format.value] — no field.value entries
        assert len(state) == 2
        assert all("_field_" not in s.get("id", "") for s in state)

    def test_callable_filename_includes_field_states(self):
        # Callable → callback must have access to the field values
        def r(_target, _snapshot_img, title: str = "chart"):
            _target.write(_snapshot_img())

        capture_graph(
            "g-dyn-fn", renderer=r, filename=lambda title="chart": f"{title}.png"
        )
        state = self._find_download_state("g-dyn-fn")
        # state = [preview.src, format.value, title.value]
        assert len(state) == 3
        assert any("title" in s.get("id", "") for s in state)


# ---------------------------------------------------------------------------
# Autogenerate-preview error handling
# ---------------------------------------------------------------------------


class TestAutogeneratePreviewErrorHandling:
    """The autogenerate-preview callback used to have no try/except;
    a renderer raising on a specific field combination would error
    server-side and leave the wizard in a half-broken state.

    Since the fix, the callback wires the error div as an additional
    Output and catches renderer exceptions into it, mirroring the
    behavior of the other two preview-update callbacks.
    """

    def _find_autogen_callback(self, uid_hint: str):
        from dash._callback import GLOBAL_CALLBACK_MAP

        for key, spec in GLOBAL_CALLBACK_MAP.items():
            # Autogen callback has preview-src as Output; distinguish
            # from the snapshot-driven callback by the presence of a
            # field Input (not just the snapshot store).
            if (
                uid_hint in key
                and "_dcap_preview_" in key
                and any(
                    "_dcap_cfg_" in inp.get("id", "") for inp in spec.get("inputs", [])
                )
            ):
                return key, spec
        return None, None

    def test_autogen_output_includes_error_div(self):
        # After the fix, the callback's Output list contains (preview.src,
        # error.children) — the error div receives renderer exceptions.
        def r(_target, _snapshot_img, title: str = "chart"):
            _target.write(_snapshot_img())

        capture_graph("g-autogen-err", renderer=r)
        _key, spec = self._find_autogen_callback("g-autogen-err")
        assert spec is not None, "autogenerate callback was not registered"
        # `output` is the top-level Output grouping used by Dash; for our
        # tuple of outputs it will be a list of two Output specs.
        outputs = spec.get("output")
        output_ids = []
        # `output` can be a single Output or a grouping; normalize
        try:
            output_ids = [o.component_id for o in outputs]
        except TypeError:
            output_ids = [getattr(outputs, "component_id", None)]
        assert any("_dcap_preview_" in oid for oid in output_ids)
        assert any("_dcap_error_" in oid for oid in output_ids), (
            f"expected the error div as an additional Output; got {output_ids!r}"
        )

    def test_no_autogen_callback_without_form_fields(self):
        # Baseline: the default renderer has no fields, so there's
        # no autogenerate callback at all (nothing to react to).
        capture_graph("g-autogen-none")
        _key, spec = self._find_autogen_callback("g-autogen-none")
        assert spec is None, (
            "autogenerate callback should not be registered when the "
            "renderer has no form fields"
        )
