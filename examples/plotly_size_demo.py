"""Plotly export-size demo — run with::

    uv run python examples/plotly_size_demo.py

Three patterns for controlling the pixel dimensions of a captured Plotly chart:

1. **User-controlled size** — ``width`` / ``height`` form fields mapped to
   ``capture_width`` / ``capture_height`` via ``capture_resolver``.
2. **Preset size** — ``fixed(1200)`` / ``fixed(800)`` pins dimensions at
   app-construction time; the wizard collapses to just Generate + Download.
3. **Strip patches + size** — ``plotly_strategy(strip_title=True)`` + fixed
   size; the offscreen clone is built at target dimensions before capture.
"""

from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dcc, html
from dash_fn_form import fixed

from dash_capture import capture_graph, plotly_strategy

fig = go.Figure(
    data=[
        go.Scatter(x=[1, 2, 3, 4, 5], y=[2, 5, 3, 8, 4], mode="lines+markers", name="A"),
        go.Scatter(x=[1, 2, 3, 4, 5], y=[1, 3, 6, 4, 7], mode="lines+markers", name="B"),
    ],
    layout={"title": "Monthly KPIs", "xaxis_title": "Month", "yaxis_title": "Value"},
)
graph = dcc.Graph(id="size-demo-graph", figure=fig)


# 1. User-controlled size — width/height are visible form fields
def renderer_controlled(
    _target, _snapshot_img,
    width: int = 1200,
    height: int = 600,
    capture_width: int = 0,
    capture_height: int = 0,
):
    _target.write(_snapshot_img())


def resolver_controlled(width, height, **_):
    return {"capture_width": width, "capture_height": height}


wizard_controlled = capture_graph(
    "size-demo-graph",
    renderer=renderer_controlled,
    capture_resolver=resolver_controlled,
    trigger="Export (user size)",
    filename="chart-custom.png",
)


# 2. Preset size — capture_width/height pinned via fixed(), no form field shown
def renderer_preset(_target, _snapshot_img, capture_width: int = 0, capture_height: int = 0):
    _target.write(_snapshot_img())


wizard_preset = capture_graph(
    "size-demo-graph",
    renderer=renderer_preset,
    trigger="Export 1200×800",
    filename="chart-1200x800.png",
    field_specs={"capture_width": fixed(1200), "capture_height": fixed(800)},
)


# 3. Strip patches + fixed size
def renderer_stripped(_target, _snapshot_img, capture_width: int = 0, capture_height: int = 0):
    _target.write(_snapshot_img())


wizard_stripped = capture_graph(
    "size-demo-graph",
    renderer=renderer_stripped,
    trigger="Export stripped 1400×700",
    filename="chart-stripped.png",
    strategy=plotly_strategy(strip_title=True, strip_legend=True),
    field_specs={"capture_width": fixed(1400), "capture_height": fixed(700)},
)


SECTION = {"marginBottom": "32px"}

app = dash.Dash(__name__)
app.layout = html.Div(
    style={"maxWidth": "900px", "margin": "0 auto", "padding": "32px", "fontFamily": "system-ui, sans-serif"},
    children=[
        html.H2("Plotly export-size control"),
        graph,
        html.Hr(),
        html.Div(style=SECTION, children=[
            html.H4("1. User-controlled size"),
            html.P("width / height are visible form fields; the resolver maps them to capture_width / capture_height."),
            wizard_controlled,
        ]),
        html.Div(style=SECTION, children=[
            html.H4("2. Preset size (fixed())"),
            html.P("No form field — dimensions pinned to 1200×800 at app construction. Wizard shows just Generate + Download."),
            wizard_preset,
        ]),
        html.Div(style=SECTION, children=[
            html.H4("3. Strip patches + fixed size"),
            html.P("plotly_strategy removes title and legend; offscreen clone is built at 1400×700 before capture."),
            wizard_stripped,
        ]),
    ],
)

if __name__ == "__main__":
    app.run(debug=False)
