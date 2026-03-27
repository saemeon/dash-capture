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
