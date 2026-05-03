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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from dash_capture import ModebarButton, add_modebar_button, capture_graph


def _hover_graph(dash_duo, graph_id: str) -> None:
    """Hover the chart so Plotly fades the modebar in (opacity 0 → 1).

    Without hovering, modebar buttons have ``opacity: 0`` and Selenium's
    ``.text`` accessor returns ``""``. We use ``textContent`` for
    DOM-level reads, but for click-then-react flows the visual state
    matters too — hovering puts the page into the same state a real
    user would interact with.
    """
    el = dash_duo.driver.find_element(By.ID, graph_id)
    ActionChains(dash_duo.driver).move_to_element(el).perform()


def _make_figure():
    return go.Figure(
        data=go.Bar(x=[1, 2, 3], y=[4, 5, 6]),
        layout={"width": 400, "height": 300},
    )


def _wait_for_modebar_btn(dash_duo, bridge_id, timeout=10):
    """Wait for the injected modebar button to appear."""
    WebDriverWait(dash_duo.driver, timeout).until(
        lambda d: d.find_element(By.CSS_SELECTOR, f'[data-dcap-id="{bridge_id}"]')
    )
    return dash_duo.driver.find_element(
        By.CSS_SELECTOR, f'[data-dcap-id="{bridge_id}"]'
    )


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

    app.layout = html.Div(
        [
            graph,
            bridge,
            html.Div(id="output", children="0"),
        ]
    )

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
    """ModebarButton with label renders text, not SVG.

    We read the button's text via ``textContent`` rather than
    Selenium's ``.text``. Plotly fades the modebar (``opacity: 0``)
    until the chart is hovered; ``.text`` returns "" for invisible
    elements, but ``textContent`` reads the DOM regardless. The label
    being correct in the DOM is what we want to assert here — the
    visual fade-in is a Plotly concern, not ours.
    """
    app = dash.Dash(__name__)
    graph = dcc.Graph(id="graph", figure=_make_figure())
    bridge = add_modebar_button(
        "graph",
        "text-btn",
        button=ModebarButton(label="SNB📷", tooltip="Export"),
    )

    app.layout = html.Div([graph, bridge])
    dash_duo.start_server(app)
    dash_duo.wait_for_element("#graph", timeout=10)

    btn = _wait_for_modebar_btn(dash_duo, "text-btn")
    text = btn.get_attribute("textContent") or ""
    assert "SNB" in text, f"button textContent = {text!r}"


# ── capture_graph with trigger="modebar" ────────────────────────────────


def test_capture_graph_modebar_trigger(dash_duo):
    """capture_graph with trigger='modebar' injects a modebar button
    that opens the wizard.

    Asserting "wizard opened" via the modal element's display style is
    more direct than waiting on a particular button's visible text:
    the Generate button is hidden (``display: none``) for renderers
    that have no form fields, and modebar buttons are ``opacity: 0``
    until hover — both make ``element.text`` an unreliable signal.
    The modal switches from ``display: none`` to ``display: block``
    when ``open_input`` flips, which is the actual contract.
    """
    app = dash.Dash(__name__)
    graph = dcc.Graph(id="graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    wizard = capture_graph(
        "graph",
        renderer=passthrough,
        trigger="modebar",
        autogenerate=True,
    )

    app.layout = html.Div([graph, wizard])
    dash_duo.start_server(app)
    dash_duo.wait_for_element("#graph", timeout=10)

    # Wait for the modebar button to be injected, then click it.
    WebDriverWait(dash_duo.driver, 10).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, "[data-dcap-id]")
    )
    btns = dash_duo.driver.find_elements(By.CSS_SELECTOR, "[data-dcap-id]")
    assert len(btns) >= 1, "No modebar button found"
    # Hovering ensures the modebar isn't intercepted by something else
    # in the chart's hover state (also matches a real user's flow).
    _hover_graph(dash_duo, "graph")
    btns[0].click()

    # Wizard modal flips to display: block when open_input is True.
    WebDriverWait(dash_duo.driver, 10).until(
        lambda d: d.execute_script(
            "var m = document.querySelector('[id^=\"_dcap_wiz_modal_\"]');"
            "return m && m.style.display === 'block';"
        )
    )
