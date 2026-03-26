# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.dropdown — toggle dropdown component."""

from dash import html

from dash_capture.dropdown import build_dropdown


class TestBuildDropdown:
    def test_returns_div(self):
        result = build_dropdown("dd1", children="Hello")
        assert isinstance(result, html.Div)

    def test_contains_button(self):
        result = build_dropdown("dd2", children="Content")
        # The outer div should have children including a Button
        types = [type(c) for c in result.children]
        assert html.Button in types

    def test_default_trigger_label(self):
        result = build_dropdown("dd3", children="X")
        buttons = [c for c in result.children if isinstance(c, html.Button)]
        assert any(b.children == "···" for b in buttons)

    def test_custom_trigger_label(self):
        result = build_dropdown("dd4", children="X", trigger_label="Menu")
        buttons = [c for c in result.children if isinstance(c, html.Button)]
        assert any(b.children == "Menu" for b in buttons)

    def test_panel_hidden_by_default(self):
        result = build_dropdown("dd5", children="X")
        # Find the panel div (last child with style containing display: none)
        divs = [c for c in result.children if isinstance(c, html.Div)]
        panel = divs[-1]  # panel is the last div
        assert panel.style.get("display") == "none"

    def test_custom_styles(self):
        result = build_dropdown(
            "dd6",
            children="X",
            styles={"button": {"color": "red"}},
        )
        buttons = [c for c in result.children if isinstance(c, html.Button)]
        assert buttons[0].style == {"color": "red"}

    def test_custom_class_names(self):
        result = build_dropdown(
            "dd7",
            children="X",
            class_names={"button": "my-btn"},
        )
        buttons = [c for c in result.children if isinstance(c, html.Button)]
        assert buttons[0].className == "my-btn"
