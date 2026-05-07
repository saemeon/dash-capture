"""POC: CSS hover-toolbar over arbitrary Dash elements.

Run with: uv run python examples/hover_toolbar_poc.py

The pattern: wrap the target + an absolutely-positioned toolbar in a
``position:relative`` div. CSS ``:hover`` on the wrapper reveals the toolbar.
Zero JS, zero callbacks for show/hide.

The toolbar button still has ``n_clicks``, so it can trigger any Dash
callback — here it opens a ``capture_element`` wizard.

Sections:
  1. dash_table.DataTable — original POC target
  2. Plain html.Div with text content
  3. KPI card (html.Div styled as a metric tile)
  4. dcc.Graph (Plotly chart via html2canvas, not modebar)
  5. Full-width block — tests display:block wrapper variant
"""

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dash_table, dcc, html  # dcc used for dcc.Graph

from dash_capture import ModebarIcon, capture_element, hover_toolbar, icon_button

# ── Shared icon ───────────────────────────────────────────────────────────────

download_arrow = ModebarIcon(
    path="M350 100 H650 V450 H800 L500 750 L200 450 H350 Z M200 820 H800 V900 H200 Z"
)


# ── 1. DataTable ─────────────────────────────────────────────────────────────

df = pd.DataFrame(
    {
        "Country": ["Switzerland", "Germany", "France", "Italy", "Austria"],
        "GDP per capita ($)": [93_720, 51_380, 44_850, 35_550, 53_640],
        "Life expectancy": [83.4, 80.9, 82.5, 82.9, 81.6],
    }
)

table = dash_table.DataTable(
    id="poc-table",
    columns=[{"name": c, "id": c} for c in df.columns],
    data=df.to_dict("records"),
    style_table={"width": "560px"},
    style_header={"backgroundColor": "#2c3e50", "color": "white", "fontWeight": "bold"},
    style_cell={"padding": "8px", "fontFamily": "system-ui, sans-serif"},
    style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"}],
)
table_btn = icon_button(download_arrow, "cap-table", tooltip="Export table")
table_wrapped = hover_toolbar(table, buttons=[table_btn])
table_wizard = capture_element("poc-table", trigger=table_btn, filename="table.png")

# ── 2. Plain html.Div ────────────────────────────────────────────────────────

text_div = html.Div(
    id="poc-text",
    style={
        "width": "560px",
        "padding": "20px",
        "background": "#f0f4f8",
        "borderRadius": "6px",
        "lineHeight": "1.6",
    },
    children=[
        html.H3("Quarterly summary", style={"margin": "0 0 8px"}),
        html.P(
            "Revenue grew 12 % year-on-year, driven by strong performance in "
            "the DACH region. Operating costs remained flat. Net margin improved "
            "by 1.4 pp to 18.2 %."
        ),
        html.P("Next review: Q3 2026 board meeting.", style={"color": "#555"}),
    ],
)
text_btn = icon_button(download_arrow, "cap-text", tooltip="Export text block")
text_wrapped = hover_toolbar(text_div, buttons=[text_btn])
text_wizard = capture_element("poc-text", trigger=text_btn, filename="text-block.png")

# ── 3. KPI card ──────────────────────────────────────────────────────────────

kpi_card = html.Div(
    id="poc-kpi",
    style={
        "width": "220px",
        "padding": "24px",
        "background": "#1a3a5c",
        "borderRadius": "8px",
        "color": "white",
        "textAlign": "center",
    },
    children=[
        html.Div(
            "Net margin",
            style={"fontSize": "13px", "opacity": "0.75", "marginBottom": "8px"},
        ),
        html.Div("18.2 %", style={"fontSize": "40px", "fontWeight": "700"}),
        html.Div(
            "▲ 1.4 pp vs prior year",
            style={"fontSize": "12px", "opacity": "0.6", "marginTop": "8px"},
        ),
    ],
)
kpi_btn = icon_button(download_arrow, "cap-kpi", tooltip="Export KPI card")
kpi_wrapped = hover_toolbar(kpi_card, buttons=[kpi_btn])
kpi_wizard = capture_element("poc-kpi", trigger=kpi_btn, filename="kpi-card.png")

# ── 4. dcc.Graph (html2canvas, not modebar) ───────────────────────────────────

fig = go.Figure()
fig.add_bar(x=["Q1", "Q2", "Q3", "Q4"], y=[4.1, 5.3, 4.8, 6.2], name="Revenue")
fig.update_layout(title="Revenue by quarter", height=300, margin={"t": 40, "b": 30})

graph = dcc.Graph(id="poc-graph", figure=fig, style={"width": "560px"})
graph_btn = icon_button(download_arrow, "cap-graph", tooltip="Export chart")
graph_wrapped = hover_toolbar(graph, buttons=[graph_btn])
graph_wizard = capture_element("poc-graph", trigger=graph_btn, filename="chart.png")

# ── 5. Full-width block ───────────────────────────────────────────────────────

fullwidth_div = html.Div(
    id="poc-fullwidth",
    style={
        "padding": "20px",
        "background": "#fff8e1",
        "borderLeft": "4px solid #f59e0b",
        "borderRadius": "4px",
    },
    children=html.P(
        "This block is full-width. The wrapper uses display:block so the "
        "hover area stretches edge-to-edge and the toolbar still anchors top-right.",
        style={"margin": 0},
    ),
)
fullwidth_btn = icon_button(download_arrow, "cap-fullwidth", tooltip="Export banner")
fullwidth_wrapped = hover_toolbar(fullwidth_div, buttons=[fullwidth_btn], display="block")
fullwidth_wizard = capture_element(
    "poc-fullwidth", trigger=fullwidth_btn, filename="banner.png"
)

# ── App ──────────────────────────────────────────────────────────────────────

app = Dash(__name__)

app.layout = html.Div(
    style={"maxWidth": "800px", "margin": "60px auto", "fontFamily": "sans-serif"},
    children=[
        html.H2("Hover toolbar POC"),
        html.P("Hover over any element — a capture button appears top-right."),
        html.H4("1. DataTable"),
        table_wrapped,
        table_wizard,
        html.Hr(style={"margin": "40px 0"}),
        html.H4("2. Plain html.Div"),
        text_wrapped,
        text_wizard,
        html.Hr(style={"margin": "40px 0"}),
        html.H4("3. KPI card"),
        kpi_wrapped,
        kpi_wizard,
        html.Hr(style={"margin": "40px 0"}),
        html.H4("4. dcc.Graph (html2canvas)"),
        graph_wrapped,
        graph_wizard,
        html.Hr(style={"margin": "40px 0"}),
        html.H4("5. Full-width block (display:block wrapper)"),
        fullwidth_wrapped,
        fullwidth_wizard,
    ],
)

if __name__ == "__main__":
    app.run(debug=True)
