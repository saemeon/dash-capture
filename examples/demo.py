"""dash-capture demo — run with: uv run python examples/demo.py

Sections
--------
1. Plotly modebar          — default 📷 button + custom SVG icon
2. Hover toolbar           — with_capture over DataTable, Div, KPI card, Graph, full-width block
3. Renderers / field types — full range of auto-generated form fields (str, int, float, bool,
                             Literal, date) + built-in PIL renderers + fig-data access
4. Size control            — user-controlled, preset (fixed()), strip + fixed
5. Explicit button         — capture_element with a standalone trigger button (escape hatch)
"""

from __future__ import annotations

import io
from datetime import date
from typing import Literal

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash_fn_form import fixed

from dash_capture import (
    CaptureButton,
    SvgIcon,
    capture_graph,
    plotly_strategy,
    with_capture,
)
from dash_capture.pil import bordered as pil_bordered
from dash_capture.pil import titled as pil_titled
from dash_capture.pil import watermarked as pil_watermarked

# ── Shared assets ─────────────────────────────────────────────────────────────

download_arrow = SvgIcon(
    path="M350 100 H650 V450 H800 L500 750 L200 450 H350 Z M200 820 H800 V900 H200 Z"
)

SECTION = {"marginBottom": "32px"}
HR = html.Hr(style={"margin": "48px 0"})

# ── Sample data ───────────────────────────────────────────────────────────────

rng = np.random.default_rng(42)
years = list(range(2018, 2025))
gdp = rng.uniform(-1.0, 3.5, len(years)).tolist()
cpi = rng.uniform(0.0, 4.0, len(years)).tolist()

df = pd.DataFrame(
    {
        "Country": ["Switzerland", "Germany", "France", "Italy", "Austria"],
        "GDP per capita ($)": [93_720, 51_380, 44_850, 35_550, 53_640],
        "Life expectancy": [83.4, 80.9, 82.5, 82.9, 81.6],
    }
)

# ── Figures ───────────────────────────────────────────────────────────────────


def make_bar_line(title: str, graph_id: str) -> dcc.Graph:
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
    return dcc.Graph(id=graph_id, figure=fig)


field_fig = go.Figure(
    data=[
        go.Scatter(
            x=[1, 2, 3, 4, 5], y=[2, 5, 3, 8, 4], mode="lines+markers", name="A"
        ),
        go.Scatter(
            x=[1, 2, 3, 4, 5], y=[1, 3, 6, 4, 7], mode="lines+markers", name="B"
        ),
    ],
    layout={
        "title": "Sample Chart",
        "xaxis_title": "X",
        "yaxis_title": "Y",
        "width": 700,
        "height": 400,
        "showlegend": True,
    },
)
field_graph = dcc.Graph(id="demo-graph", figure=field_fig)

size_fig = go.Figure(
    data=[
        go.Scatter(
            x=[1, 2, 3, 4, 5], y=[2, 5, 3, 8, 4], mode="lines+markers", name="A"
        ),
        go.Scatter(
            x=[1, 2, 3, 4, 5], y=[1, 3, 6, 4, 7], mode="lines+markers", name="B"
        ),
    ],
    layout={"title": "Monthly KPIs", "xaxis_title": "Month", "yaxis_title": "Value"},
)
size_graph = dcc.Graph(id="size-demo-graph", figure=size_fig)

# ── Renderers (Section 3) ─────────────────────────────────────────────────────


def passthrough(_target, _snapshot_img):
    """No user parameters → empty wizard (just Generate + Download)."""
    _target.write(_snapshot_img())


def str_and_int_renderer(
    _target, _snapshot_img, title: str = "My Report", dpi: int = 150
):
    """str → text input, int → number input. Overlays a matplotlib title."""
    import matplotlib.pyplot as plt

    plt.switch_backend("agg")
    raw = plt.imread(io.BytesIO(_snapshot_img()))
    h, w = raw.shape[:2]
    fig_mpl, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    try:
        ax.imshow(raw)
        ax.axis("off")
        if title:
            ax.set_title(title, fontsize=10)
        fig_mpl.savefig(_target, format="png", bbox_inches="tight", pad_inches=0)
    finally:
        plt.close(fig_mpl)


def literal_and_bool_renderer(
    _target,
    _snapshot_img,
    border_color: Literal["white", "black", "gray", "navy"] = "white",
    border_width: int = 20,
    add_shadow: bool = False,
):
    """Literal → dropdown, int → number input, bool → checkbox."""
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(_snapshot_img()))
    bw = border_width
    new = Image.new("RGB", (img.width + 2 * bw, img.height + 2 * bw), border_color)
    new.paste(img, (bw, bw))
    if add_shadow:
        new = new.filter(ImageFilter.GaussianBlur(radius=3))
        new.paste(img, (bw, bw))
    buf = io.BytesIO()
    new.save(buf, format="PNG")
    _target.write(buf.getvalue())


def float_renderer(
    _target, _snapshot_img, brightness: float = 1.0, contrast: float = 1.0
):
    """float → number input with decimal step."""
    from PIL import Image, ImageEnhance

    img = Image.open(io.BytesIO(_snapshot_img()))
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    _target.write(buf.getvalue())


def date_renderer(
    _target,
    _snapshot_img,
    report_date: date = date(2026, 3, 22),
    author: str = "Data Team",
):
    """date → date picker, str → text input. Stamps a date/author line."""
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(_snapshot_img()))
    new = Image.new("RGB", (img.width, img.height + 30), "white")
    new.paste(img, (0, 0))
    draw = ImageDraw.Draw(new)
    draw.text((10, img.height + 5), f"{report_date} — {author}", fill="gray")
    buf = io.BytesIO()
    new.save(buf, format="PNG")
    _target.write(buf.getvalue())


def figdata_renderer(
    _target, _fig_data, output_format: Literal["summary", "json"] = "summary"
):
    """_fig_data → receives Plotly figure dict (no browser capture needed)."""
    import json

    if output_format == "json":
        text = json.dumps(_fig_data, indent=2, default=str)
    else:
        n_traces = len(_fig_data.get("data", []))
        title = _fig_data.get("layout", {}).get("title", {}) or {}
        title_text = (
            title.get("text", "(no title)") if isinstance(title, dict) else title
        )
        text = f"Figure: {title_text}\nTraces: {n_traces}"
    _target.write(text.encode())


def error_renderer(_target, _snapshot_img, max_size_kb: int = 50):
    """Fails if image exceeds max_size_kb — demonstrates error display."""
    data = _snapshot_img()
    size_kb = len(data) / 1024
    if size_kb > max_size_kb:
        raise ValueError(
            f"Image too large: {size_kb:.0f} KB (max {max_size_kb} KB). "
            "Try a smaller chart or lower resolution."
        )
    _target.write(data)


# ── Size-control renderers (Section 4) ────────────────────────────────────────


def renderer_controlled(
    _target,
    _snapshot_img,
    width: int = 1200,
    height: int = 600,
    capture_width: int = 0,
    capture_height: int = 0,
):
    _target.write(_snapshot_img())


def resolver_controlled(width, height, **_):
    return {"capture_width": width, "capture_height": height}


def renderer_preset(
    _target, _snapshot_img, capture_width: int = 0, capture_height: int = 0
):
    _target.write(_snapshot_img())


def renderer_stripped(
    _target, _snapshot_img, capture_width: int = 0, capture_height: int = 0
):
    _target.write(_snapshot_img())


# ── Section 1: Plotly modebar ─────────────────────────────────────────────────

modebar_graph_plain = make_bar_line("GDP growth and CPI", "chart-plain")
modebar_graph_custom = make_bar_line("GDP growth and CPI", "chart-custom")
modebar_wizard_plain = capture_graph(modebar_graph_plain, filename="plain.png")

modebar_wizard_custom = capture_graph(
    modebar_graph_custom,
    trigger=CaptureButton(icon=download_arrow, tooltip="Export chart"),
    filename="custom.png",
)

# ── Section 2: Hover toolbar (with_capture) ───────────────────────────────────

hover_table = with_capture(
    dash_table.DataTable(
        id="poc-table",
        columns=[{"name": c, "id": c} for c in df.columns],
        data=df.to_dict("records"),
        style_table={"width": "560px"},
        style_header={
            "backgroundColor": "#2c3e50",
            "color": "white",
            "fontWeight": "bold",
        },
        style_cell={"padding": "8px", "fontFamily": "system-ui, sans-serif"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"}
        ],
    ),
    download_arrow,
    tooltip="Export table",
    filename="table.png",
)

hover_text_div = with_capture(
    html.Div(
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
    ),
    download_arrow,
    tooltip="Export text block",
    filename="text-block.png",
)

hover_kpi = with_capture(
    html.Div(
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
    ),
    download_arrow,
    tooltip="Export KPI card",
    filename="kpi-card.png",
)

_hover_fig = go.Figure()
_hover_fig.add_bar(x=["Q1", "Q2", "Q3", "Q4"], y=[4.1, 5.3, 4.8, 6.2], name="Revenue")
_hover_fig.update_layout(
    title="Revenue by quarter", height=300, margin={"t": 40, "b": 30}
)

hover_graph = with_capture(
    dcc.Graph(id="poc-graph", figure=_hover_fig, style={"width": "560px"}),
    download_arrow,
    tooltip="Export chart",
    filename="chart.png",
)

hover_fullwidth = with_capture(
    html.Div(
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
    ),
    download_arrow,
    tooltip="Export banner",
    filename="banner.png",
    display="block",
)

# ── Section 4: Size control ───────────────────────────────────────────────────

wizard_controlled = capture_graph(
    "size-demo-graph",
    renderer=renderer_controlled,
    capture_resolver=resolver_controlled,
    trigger="Export (user size)",
    filename="chart-custom.png",
)

wizard_preset = capture_graph(
    "size-demo-graph",
    renderer=renderer_preset,
    trigger="Export 1200×800",
    filename="chart-1200x800.png",
    field_specs={"capture_width": fixed(1200), "capture_height": fixed(800)},
)

wizard_stripped = capture_graph(
    "size-demo-graph",
    renderer=renderer_stripped,
    trigger="Export stripped 1400×700",
    filename="chart-stripped.png",
    strategy=plotly_strategy(strip_title=True, strip_legend=True),
    field_specs={"capture_width": fixed(1400), "capture_height": fixed(700)},
)

# ── Section 5: Explicit button (escape hatch) ─────────────────────────────────

_explicit_fig = go.Figure()
_explicit_fig.add_bar(
    x=["Q1", "Q2", "Q3", "Q4"], y=[120, 145, 132, 178], name="Revenue"
)
_explicit_fig.update_layout(title="Revenue", height=300)
explicit_graph = dcc.Graph(id="explicit-graph", figure=_explicit_fig)

explicit_wizard = capture_graph(
    "explicit-graph",
    renderer=passthrough,
    trigger=CaptureButton(icon=download_arrow, tooltip="Export"),
    filename="explicit.png",
)

# ── App layout ────────────────────────────────────────────────────────────────

app = dash.Dash(__name__)

app.layout = html.Div(
    style={
        "maxWidth": "960px",
        "margin": "0 auto",
        "padding": "32px",
        "fontFamily": "system-ui, sans-serif",
    },
    children=[
        html.H1("dash-capture demo"),
        # ── 1. Modebar ────────────────────────────────────────────────────────
        html.H2("1. Plotly modebar"),
        html.Div(
            style=SECTION,
            children=[
                html.H4("1a. Default — 📷 button injected into modebar"),
                html.P('capture_graph(graph) — trigger defaults to "modebar".'),
                modebar_graph_plain,
                modebar_wizard_plain,
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("1b. Custom SVG icon + tooltip"),
                html.P("trigger=CaptureButton(icon=SvgIcon(path=...), tooltip=...)"),
                modebar_graph_custom,
                modebar_wizard_custom,
            ],
        ),
        HR,
        # ── 2. Hover toolbar ──────────────────────────────────────────────────
        html.H2("2. Hover toolbar — with_capture"),
        html.P("Hover over any element — a capture button appears top-right."),
        html.Div(style=SECTION, children=[html.H4("2a. DataTable"), hover_table]),
        html.Div(
            style=SECTION, children=[html.H4("2b. Plain html.Div"), hover_text_div]
        ),
        html.Div(style=SECTION, children=[html.H4("2c. KPI card"), hover_kpi]),
        html.Div(
            style=SECTION,
            children=[html.H4("2d. dcc.Graph (html2canvas)"), hover_graph],
        ),
        html.Div(
            style=SECTION,
            children=[html.H4("2e. Full-width block (display:block)"), hover_fullwidth],
        ),
        HR,
        # ── 3. Renderers / field types ────────────────────────────────────────
        html.H2("3. Renderers / field types"),
        html.P(
            "Each button opens a wizard. Form fields are auto-generated from type hints."
        ),
        field_graph,
        html.Br(),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3a. No parameters → empty wizard"),
                html.Code("def passthrough(_target, _snapshot_img)"),
                html.Br(),
                html.Br(),
                capture_graph(
                    field_graph, renderer=passthrough, trigger="Capture (simple)"
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3b. str + int → text input + number input"),
                html.Code("def renderer(_target, _snapshot_img, title: str, dpi: int)"),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=str_and_int_renderer,
                    trigger="Capture (matplotlib)",
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3c. Literal + int + bool → dropdown + number + checkbox"),
                html.Code(
                    "def renderer(..., border_color: Literal[...], add_shadow: bool)"
                ),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=literal_and_bool_renderer,
                    trigger="Capture (PIL border)",
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3d. float → number input with decimal step"),
                html.Code("def renderer(..., brightness: float, contrast: float)"),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=float_renderer,
                    trigger="Capture (brightness/contrast)",
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3e. date → date picker"),
                html.Code("def renderer(..., report_date: date, author: str)"),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph", renderer=date_renderer, trigger="Capture (date stamp)"
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3f. Strip patches — preprocess before capture"),
                html.P(
                    "Same passthrough renderer, Plotly title + legend removed before capture."
                ),
                capture_graph(
                    "demo-graph",
                    renderer=passthrough,
                    trigger="Capture (stripped)",
                    strategy=plotly_strategy(strip_title=True, strip_legend=True),
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3g. _fig_data — server-side figure access (no screenshot)"),
                html.P(
                    "Renderer receives the Plotly figure dict directly. No browser capture."
                ),
                html.Code(
                    "def renderer(_target, _fig_data, output_format: Literal[...])"
                ),
                html.Br(),
                html.Br(),
                capture_graph(
                    "demo-graph",
                    renderer=figdata_renderer,
                    trigger="Capture (fig data)",
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3h. Format selection — JPEG and SVG"),
                capture_graph(
                    "demo-graph",
                    renderer=passthrough,
                    trigger="Capture (JPEG)",
                    strategy=plotly_strategy(format="jpeg"),
                ),
                html.Span(" "),
                capture_graph(
                    "demo-graph",
                    renderer=passthrough,
                    trigger="Capture (SVG)",
                    strategy=plotly_strategy(format="svg"),
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3i. Error display"),
                html.P("The error message is shown in red below the preview."),
                capture_graph(
                    "demo-graph",
                    renderer=error_renderer,
                    trigger="Capture (error demo)",
                ),
            ],
        ),
        html.H3("Built-in PIL renderers — dash_capture.pil"),
        html.P("Requires the [pil] extra: pip install 'dash-capture[pil]'."),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3j. pil.titled — title bar above the chart"),
                capture_graph(
                    "demo-graph", renderer=pil_titled, trigger="Capture (PIL titled)"
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3k. pil.bordered — colored border"),
                capture_graph(
                    "demo-graph",
                    renderer=pil_bordered,
                    trigger="Capture (PIL bordered)",
                ),
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("3l. pil.watermarked — diagonal watermark"),
                capture_graph(
                    "demo-graph",
                    renderer=pil_watermarked,
                    trigger="Capture (PIL watermarked)",
                ),
            ],
        ),
        HR,
        # ── 4. Size control ───────────────────────────────────────────────────
        html.H2("4. Size control"),
        size_graph,
        html.Hr(),
        html.Div(
            style=SECTION,
            children=[
                html.H4("4a. User-controlled size"),
                html.P(
                    "width / height are visible form fields; resolver maps them to capture_width / capture_height."
                ),
                wizard_controlled,
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("4b. Preset size — fixed()"),
                html.P(
                    "No form field — dimensions pinned to 1200×800. Wizard shows just Generate + Download."
                ),
                wizard_preset,
            ],
        ),
        html.Div(
            style=SECTION,
            children=[
                html.H4("4c. Strip patches + fixed size"),
                html.P(
                    "plotly_strategy removes title and legend; offscreen clone built at 1400×700."
                ),
                wizard_stripped,
            ],
        ),
        HR,
        # ── 5. Explicit button ────────────────────────────────────────────────
        html.H2("5. Explicit button placement (escape hatch)"),
        html.P(
            "Place the wizard anywhere in the layout — separate from the graph. "
            "Use trigger=CaptureButton(...) instead of the default modebar injection."
        ),
        explicit_graph,
        html.Br(),
        html.Div(
            style=SECTION,
            children=[
                html.H4("5a. Standalone trigger button"),
                html.P(
                    "The button lives here, not in the modebar. Works for any element type."
                ),
                explicit_wizard,
            ],
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True)
