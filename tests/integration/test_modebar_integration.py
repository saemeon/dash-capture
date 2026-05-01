# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Integration tests for modebar button injection.

Run locally with:
  PATH="/opt/homebrew/bin:$PATH" uv run pytest dash-capture/tests/integration/test_modebar_integration.py -v
"""

from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dcc, html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from dash_capture import ModebarButton, add_modebar_button, capture_graph


def _make_figure():
    return go.Figure(
        data=go.Bar(x=[1, 2, 3], y=[4, 5, 6]),
        layout=dict(width=400, height=300),
    )


def _wait_for_modebar_btn(dash_duo, bridge_id, timeout=10):
    """Wait for the injected modebar button to appear."""
    WebDriverWait(dash_duo.driver, timeout).until(
        lambda d: d.find_element(By.CSS_SELECTOR, f'[data-dcap-id="{bridge_id}"]')
    )
    return dash_duo.driver.find_element(By.CSS_SELECTOR, f'[data-dcap-id="{bridge_id}"]')


# ── add_modebar_button (standalone) ─────────────────────────────────────


def test_modebar_button_appears(dash_duo):
    """add_modebar_button injects a button into the Plotly modebar."""
    app = dash.Dash(__name__)
    graph = dcc.Graph(id="graph", figure=_make_figure())
    bridge = add_modebar_button("graph", "my-btn", tooltip="Test")

    app.layout = html.Div([graph, bridge])
    dash_duo.start_server(app)
    dash_duo.wait_for_element("#graph", timeout=10)

    btn = _wait_for_modebar_btn(dash_duo, "my-btn")
    assert btn is not None
    assert btn.get_attribute("data-title") == "Test"


def test_modebar_button_click_fires_callback(dash_duo):
    """Clicking the modebar button increments the bridge's n_clicks."""
    app = dash.Dash(__name__)
    graph = dcc.Graph(id="graph", figure=_make_figure())
    bridge = add_modebar_button("graph", "click-btn", tooltip="Click me")

    app.layout = html.Div([
        graph, bridge,
        html.Div(id="output", children="0"),
    ])

    @app.callback(
        dash.Output("output", "children"),
        dash.Input("click-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_click(n):
        return str(n)

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#graph", timeout=10)

    btn = _wait_for_modebar_btn(dash_duo, "click-btn")
    btn.click()

    WebDriverWait(dash_duo.driver, 10).until(
        lambda d: d.find_element(By.ID, "output").text == "1"
    )
    assert dash_duo.driver.find_element(By.ID, "output").text == "1"


def test_modebar_button_with_text_label(dash_duo):
    """ModebarButton with label renders text, not SVG."""
    app = dash.Dash(__name__)
    graph = dcc.Graph(id="graph", figure=_make_figure())
    bridge = add_modebar_button(
        "graph", "text-btn",
        button=ModebarButton(label="SNB📷", tooltip="Export"),
    )

    app.layout = html.Div([graph, bridge])
    dash_duo.start_server(app)
    dash_duo.wait_for_element("#graph", timeout=10)

    btn = _wait_for_modebar_btn(dash_duo, "text-btn")
    assert "SNB" in btn.text


# ── capture_graph with trigger="modebar" ────────────────────────────────


def test_capture_graph_modebar_trigger(dash_duo):
    """capture_graph with trigger='modebar' injects a modebar button that opens the wizard."""
    app = dash.Dash(__name__)
    graph = dcc.Graph(id="graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    wizard = capture_graph(
        "graph", renderer=passthrough,
        trigger="modebar", autogenerate=True,
    )

    app.layout = html.Div([graph, wizard])
    dash_duo.start_server(app)
    dash_duo.wait_for_element("#graph", timeout=10)

    # Find and click the modebar button
    btns = dash_duo.driver.find_elements(By.CSS_SELECTOR, "[data-dcap-id]")
    assert len(btns) >= 1, "No modebar button found"
    btns[0].click()

    # Wizard should open — look for the Generate button
    WebDriverWait(dash_duo.driver, 10).until(
        lambda d: any(
            b.text.strip() == "Generate"
            for b in d.find_elements(By.TAG_NAME, "button")
        )
    )
