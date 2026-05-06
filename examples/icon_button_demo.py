"""dash-capture icon-button demo — run with: uv run python examples/icon_button_demo.py

Reuses a :class:`ModebarIcon` as a normal Dash button next to the captured
element. Useful for ``capture_element``, where there's no Plotly modebar
to inject into.

The same ``ModebarIcon`` definition drives both:

  1. a modebar-injected button on a ``dcc.Graph`` (via ``capture_graph``)
  2. a standalone ``html.Button`` next to a ``dash_table.DataTable``
     (via ``capture_element(trigger=...)``)

The icon is rendered into the standalone button as an inline SVG data URI
on an ``html.Img`` — works on every Dash version without needing
``dangerously_allow_html``.
"""

from __future__ import annotations

from urllib.parse import quote

from dash import Dash, dash_table, dcc, html

from dash_capture import (
    ModebarButton,
    ModebarIcon,
    capture_element,
    capture_graph,
)


# ── Helper: ModebarIcon → html.Button ────────────────────────────────────────


def icon_button(
    icon: ModebarIcon,
    button_id: str,
    *,
    tooltip: str = "",
    height: int = 20,
) -> html.Button:
    """Render a :class:`ModebarIcon` as a standalone Dash button.

    Mirrors how ``_modebar.py`` sizes the icon in the Plotly modebar:
    height is fixed, width is computed from the icon's viewBox aspect
    ratio. The SVG is embedded as a data URI on an ``html.Img`` so this
    works on any Dash version (no ``dangerously_allow_html`` needed).
    """
    width = round(height * icon.width / icon.height)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {icon.width} {icon.height}" '
        f'width="{width}" height="{height}">'
        f"{icon.to_svg_inner()}</svg>"
    )
    return html.Button(
        id=button_id,
        n_clicks=0,
        title=tooltip,
        children=html.Img(
            src="data:image/svg+xml;utf8," + quote(svg),
            height=height,
            style={"display": "block"},
        ),
        style={
            "background": "transparent",
            "border": "1px solid #ccc",
            "borderRadius": "4px",
            "padding": "6px 8px",
            "cursor": "pointer",
        },
    )


# ── Shared icon ──────────────────────────────────────────────────────────────

# Download-arrow glyph in Plotly's default 1000x1000 viewBox (same icon
# used by examples/modebar_demo.py).
download_arrow = ModebarIcon(
    path="M350 100 H650 V450 H800 L500 750 L200 450 H350 Z M200 820 H800 V900 H200 Z"
)


# ── Components to capture ────────────────────────────────────────────────────

graph = dcc.Graph(
    id="demo-graph",
    figure={
        "data": [{"x": [1, 2, 3, 4], "y": [4, 1, 3, 2], "type": "bar"}],
        "layout": {"title": "Demo chart", "height": 320},
    },
)

table = dash_table.DataTable(
    id="demo-table",
    columns=[{"name": c, "id": c} for c in ("Country", "Score")],
    data=[
        {"Country": "Switzerland", "Score": 92},
        {"Country": "Germany", "Score": 87},
        {"Country": "France", "Score": 81},
    ],
    style_table={"width": "400px"},
    style_cell={"padding": "8px", "fontFamily": "system-ui, sans-serif"},
)


# ── Capture wiring ───────────────────────────────────────────────────────────

# 1. Modebar — icon lives inside the Plotly modebar.
graph_wizard = capture_graph(
    graph,
    trigger=ModebarButton(icon=download_arrow, tooltip="Export chart"),
    filename="chart.png",
)

# 2. Standalone — same icon as a normal Dash button next to the table.
table_trigger = icon_button(
    download_arrow,
    button_id="capture-table-btn",
    tooltip="Export table",
)
table_wizard = capture_element(
    "demo-table",
    trigger=table_trigger,
    filename="table.png",
)


# ── App ──────────────────────────────────────────────────────────────────────

app = Dash(__name__)

app.layout = html.Div(
    style={"maxWidth": "800px", "margin": "40px auto", "fontFamily": "sans-serif"},
    children=[
        html.H2("dash-capture — same icon, two trigger styles"),
        html.H4("1. ModebarIcon in the Plotly modebar"),
        html.P("trigger=ModebarButton(icon=download_arrow, ...)"),
        graph,
        graph_wizard,
        html.Hr(style={"margin": "40px 0"}),
        html.H4("2. Same ModebarIcon as a standalone html.Button"),
        html.P("trigger=icon_button(download_arrow, ...) — for capture_element"),
        table,
        html.Br(),
        table_trigger,
        table_wizard,
    ],
)

if __name__ == "__main__":
    app.run(debug=True)
