# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.wizard — modal wizard component."""

import pytest
from dash import Input, html

from dash_capture._wizard import Wizard, build_wizard


class TestWizard:
    def test_dataclass_fields(self):
        w = Wizard(div=html.Div("x"), open_input=Input("s", "data"))
        assert isinstance(w.div, html.Div)
        assert isinstance(w.open_input, Input)


class TestBuildWizard:
    def test_returns_wizard(self):
        result = build_wizard("wiz1", body=html.P("body"))
        assert isinstance(result, Wizard)

    def test_div_is_html_div(self):
        result = build_wizard("wiz2", body=html.P("body"))
        assert isinstance(result.div, html.Div)

    def test_open_input_is_input(self):
        result = build_wizard("wiz3", body=html.P("body"))
        assert isinstance(result.open_input, Input)

    def test_string_trigger_creates_button(self):
        result = build_wizard("wiz4", body=html.P("body"), trigger="Go")
        # String trigger: children should include trigger_component, store, modal
        children = result.div.children
        assert len(children) == 3
        assert isinstance(children[0], html.Button)
        assert children[0].children == "Go"

    def test_custom_trigger_component(self):
        btn = html.Button("Custom", id="my-custom-btn")
        result = build_wizard("wiz5", body=html.P("body"), trigger=btn)
        # Custom trigger: children are [store, modal] only (no trigger)
        children = result.div.children
        assert len(children) == 2

    def test_custom_trigger_without_id_raises(self):
        btn = html.Span("No id")
        with pytest.raises(ValueError, match="id"):
            build_wizard("wiz6", body=html.P("body"), trigger=btn)

    def test_custom_dialog_style(self):
        result = build_wizard(
            "wiz7",
            body=html.P("body"),
            dialog_style={"minWidth": "800px"},
        )
        assert isinstance(result.div, html.Div)

    def test_title_appears(self):
        result = build_wizard("wiz8", body=html.P("body"), title="My Title")
        assert isinstance(result.div, html.Div)


class TestRegisterArmInterval:
    """Tests for ``_register_arm_interval`` — the auto-preview interval arm.

    The fix under test: on open, bump ``max_intervals`` to ``n_intervals + 1``
    instead of resetting ``n_intervals`` to 0. Resetting caused a 1→0 Input
    change that fired downstream callbacks before the interval ticked,
    producing a double-capture on re-open. Bumping leaves ``n_intervals``
    alone; the next interval tick advances it from N→N+1, firing once.
    """

    @staticmethod
    def _get_arm_interval_fn(interval_id: str, open_store_id: str):
        """Register the callback in a fresh namespace and return the
        underlying function (unwrapped from Dash's callback wrapper)."""
        from dash._callback import GLOBAL_CALLBACK_MAP

        from dash_capture._wizard import _register_arm_interval

        keys_before = set(GLOBAL_CALLBACK_MAP.keys())
        _register_arm_interval(interval_id, Input(open_store_id, "data"))
        added = set(GLOBAL_CALLBACK_MAP.keys()) - keys_before
        assert len(added) == 1, f"expected 1 new callback, got {len(added)}"
        key = next(iter(added))
        return GLOBAL_CALLBACK_MAP[key]["callback"].__wrapped__

    def test_open_enables_interval(self):
        fn = self._get_arm_interval_fn("intv1", "store1")
        disabled, _max_intervals = fn(True, 0)
        assert disabled is False, "On open the interval must be enabled."

    def test_open_bumps_max_intervals_to_current_n_plus_one(self):
        """The fix's core invariant: max_intervals = n_intervals + 1.

        Allows exactly one more tick. If we instead returned a constant
        like 1, re-opens after the first tick would either fail to fire
        (n_intervals already >= max) or require a separate reset.
        """
        fn = self._get_arm_interval_fn("intv2", "store2")
        for current_n in (0, 1, 5, 42):
            _disabled, max_intervals = fn(True, current_n)
            assert max_intervals == current_n + 1, (
                f"max_intervals must be n_intervals+1, got "
                f"{max_intervals} for current_n={current_n}"
            )

    def test_open_handles_none_n_intervals(self):
        """``current_n`` arrives as ``None`` before the interval has ever
        ticked. Must coerce to 0 to avoid a TypeError on ``None + 1``."""
        fn = self._get_arm_interval_fn("intv3", "store3")
        _disabled, max_intervals = fn(True, None)
        assert max_intervals == 1

    def test_close_disables_interval(self):
        fn = self._get_arm_interval_fn("intv4", "store4")
        disabled, _max_intervals = fn(False, 7)
        assert disabled is True, "On close the interval must be disabled."

    def test_close_does_not_touch_max_intervals(self):
        """Regression: returning a real value for max_intervals on close
        was an Input change for any callback listening on it. We must
        return ``dash.no_update`` so close stays silent."""
        import dash

        fn = self._get_arm_interval_fn("intv5", "store5")
        _disabled, max_intervals = fn(False, 7)
        assert max_intervals is dash.no_update, (
            "On close, max_intervals must be dash.no_update — returning a "
            "real number would fire downstream callbacks listening on the "
            "interval, running the JS capture chain at close-time."
        )


class TestRegisterCaptureDirectCaptureSpec:
    """Tests for the three-case handling of ``capture_*`` params in the
    direct flow (no ``capture_resolver``).

    Cases:
    - ``fixed(value)`` → inlined as a JS constant.
    - real Field spec → form field rendered, JS reads via State.
    - no spec        → omit from opts; strategy uses current browser size.

    The "no spec" case used to fall through to the State branch, which
    referenced a form-field ID that the FnForm ``_exclude`` list had
    suppressed — surfacing as ``ID not found in layout`` at first wizard
    open. The fix adds an explicit ``elif spec is not None:`` guard.
    """

    @staticmethod
    def _register_states(active_capture, field_specs, suffix):
        """Register a direct-flow capture callback and return its State
        component IDs for inspection."""
        from dash._callback import GLOBAL_CALLBACK_MAP

        from dash_capture._wizard import _register_capture_direct
        from dash_capture.strategies import CaptureStrategy

        keys_before = set(GLOBAL_CALLBACK_MAP.keys())
        # Minimal strategy — capture body content doesn't matter for these
        # tests; we only inspect the wiring (States + JS opts assignments).
        strategy = CaptureStrategy(capture="return null;", format="png")
        _register_capture_direct(
            element_id=f"el-{suffix}",
            strategy=strategy,
            params={},
            config_id=f"cfg-{suffix}",
            active_capture=list(active_capture),
            field_specs=field_specs,
            snapshot_store_id=f"snap-{suffix}",
            generate_id=f"gen-{suffix}",
            interval_id=f"intv-{suffix}",
            format_id=f"fmt-{suffix}",
        )
        added = set(GLOBAL_CALLBACK_MAP.keys()) - keys_before
        assert len(added) == 1
        spec = GLOBAL_CALLBACK_MAP[next(iter(added))]
        return [s["id"] for s in spec["state"]]

    def test_no_spec_creates_no_state_for_capture_param(self):
        """No spec → no State for the param.

        The previous bug: the param landed in ``dynamic_capture``, which
        created a State referencing a form-field ID that FnForm never
        rendered (``capture_*`` params live in the ``_exclude`` list).
        Result was a layout-time error at first wizard open.
        """
        ids = self._register_states(
            active_capture=["capture_width"],
            field_specs=None,
            suffix="ns",
        )
        assert all("capture_width" not in i for i in ids), (
            f"capture_width without a field_spec must not appear in States. Got: {ids}"
        )

    def test_fixed_spec_creates_no_state_for_capture_param(self):
        """``fixed(N)`` is inlined into JS — no State needed."""
        from dash_fn_form._spec import fixed

        ids = self._register_states(
            active_capture=["capture_width"],
            field_specs={"capture_width": fixed(800)},
            suffix="fix",
        )
        assert all("capture_width" not in i for i in ids), (
            f"fixed-spec capture_width must not appear in States. Got: {ids}"
        )

    def test_real_field_spec_creates_state(self):
        """Non-fixed Field spec → State references the form-field ID."""
        from dash_fn_form import Field
        from dash_fn_form._forms import field_id as fn_field_id

        ids = self._register_states(
            active_capture=["capture_width"],
            field_specs={"capture_width": Field()},
            suffix="fld",
        )
        expected_id = fn_field_id("cfg-fld", "capture_width")
        assert expected_id in ids, (
            f"Field-spec capture_width must produce a State with id "
            f"{expected_id!r}. Got: {ids}"
        )


class TestBuildCaptureJsOpts:
    """Tests for the JS ``opts`` assignment block in ``build_capture_js``.

    These pin the output side of the three-case capture_* handling:
    - dynamic param → ``opts.X`` assigned from a callback arg
    - fixed param   → ``opts.X`` inlined as a literal
    - omitted       → ``opts.X`` not assigned at all (strategy uses
                      element's current browser size)
    """

    @staticmethod
    def _build(active_capture, fixed_capture):
        from dash_capture.strategies import CaptureStrategy, build_capture_js

        strategy = CaptureStrategy(capture="return null;", format="png")
        return build_capture_js(
            element_id="el",
            strategy=strategy,
            active_capture=list(active_capture),
            params={},
            fixed_capture=fixed_capture,
        )

    def test_omitted_param_absent_from_opts(self):
        """No dynamic, no fixed → no `opts.width` line."""
        js = self._build(active_capture=[], fixed_capture={})
        assert "opts.width" not in js, (
            f"Without a capture_width spec the JS must not assign opts.width "
            f"(strategy must inherit the element's current size). Got:\n{js}"
        )

    def test_dynamic_param_assigned_from_callback_arg(self):
        """`opts.width = capture_width` reads from the callback arg."""
        js = self._build(active_capture=["capture_width"], fixed_capture={})
        assert "opts.width = capture_width" in js, (
            f"Dynamic capture_width must be read from the JS arg. Got:\n{js}"
        )

    def test_fixed_param_inlined_as_literal(self):
        """`opts.width = 800` inlined as a constant; no callback arg."""
        js = self._build(active_capture=[], fixed_capture={"capture_width": 800})
        assert "opts.width = 800" in js, f"fixed(800) must inline literally. Got:\n{js}"
