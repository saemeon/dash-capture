"""dash-capture modebar demo — run with: uv run python examples/modebar_demo.py

Showcases the modebar-integrated capture button (the default trigger):

- Variant 1: ``capture_graph`` with default ``trigger="modebar"`` — a
  camera-emoji button is injected into the Plotly modebar.
- Variant 2: custom :class:`ModebarButton` with an SVG icon and tooltip.

Leave the tab backgrounded for a few minutes and return to verify the
button survives Chrome's tab-discard / memory-saver reactivation.
"""

import numpy as np
import plotly.graph_objects as go
from dash import Dash, dcc, html

from dash_capture import ModebarButton, ModebarIcon, capture_graph

# ── Data ──────────────────────────────────────────────────────────────────────

rng = np.random.default_rng(42)
years = list(range(2018, 2025))
gdp = rng.uniform(-1.0, 3.5, len(years)).tolist()
cpi = rng.uniform(0.0, 4.0, len(years)).tolist()


def make_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=years, y=gdp, name="GDP growth")
    fig.add_scatter(x=years, y=cpi, name="CPI", mode="lines+markers")
    fig.update_layout(
        title=title,
        barmode="group",
        xaxis_title="Year",
        yaxis_title="Percent",
        height=360,
    )
    return fig


# ── App ───────────────────────────────────────────────────────────────────────

app = Dash(__name__)

plain_graph = dcc.Graph(id="chart-plain", figure=make_fig("GDP growth and CPI"))
custom_graph = dcc.Graph(id="chart-custom", figure=make_fig("GDP growth and CPI"))

# 1. Default — trigger="modebar" puts a 📷 button in the Plotly modebar.
plain_wizard = capture_graph(plain_graph, filename="plain.png")

# 2. Custom SVG icon + tooltip via ModebarButton. Download-arrow glyph
#    drawn in Plotly's default 1000x1000 viewBox.
download_arrow = ModebarIcon(
    path="M350 100 H650 V450 H800 L500 750 L200 450 H350 Z M200 820 H800 V900 H200 Z"
)
custom_wizard = capture_graph(
    custom_graph,
    trigger=ModebarButton(icon=download_arrow, tooltip="Export chart"),
    filename="custom.png",
)

app.layout = html.Div(
    style={"maxWidth": "900px", "margin": "40px auto", "fontFamily": "sans-serif"},
    children=[
        html.H2("dash-capture modebar demo"),
        html.H4("1. Default camera-emoji button"),
        html.P(
            'capture_graph(graph) — the default trigger is "modebar", '
            "so a 📷 button is injected into the Plotly modebar."
        ),
        plain_graph,
        plain_wizard,
        html.Hr(style={"margin": "40px 0"}),
        html.H4("2. Custom icon + tooltip"),
        html.P("trigger=ModebarButton(icon=ModebarIcon(path=...), tooltip=...)"),
        custom_graph,
        custom_wizard,
    ],
)

if __name__ == "__main__":
    app.run(debug=True)
