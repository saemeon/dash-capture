"""interact() demo — dash-fn-interact equivalent of ipywidgets.interact().

Three panels on one page:

  1. Sine wave    — live update, returns plotly Figure
  2. Text stats  — live update, returns plain text (repr)
  3. Filtered df — manual Apply, returns an html.Table

Run:
    uv run python examples/interact_demo.py
then open http://localhost:1237
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import plotly.graph_objects as go
from dash import Dash, html

from dash_fn_interact import Field, interact

app = Dash(__name__)


# ── 1. Sine wave — returns a plotly Figure ──────────────────────────────────


def sine_wave(
    amplitude: float = 1.0,
    frequency: float = 2.0,
    phase: float = 0.0,
    color: Literal["royalblue", "tomato", "seagreen"] = "royalblue",
) -> go.Figure:
    """Adjust the sliders to reshape the wave in real time."""
    t = np.linspace(0, 2 * np.pi, 500)
    y = amplitude * np.sin(frequency * t + phase)
    fig = go.Figure(go.Scatter(x=t, y=y, line={"color": color}))
    fig.update_layout(
        margin={"t": 20, "b": 20, "l": 40, "r": 20},
        yaxis_range=[-2.5, 2.5],
        height=280,
    )
    return fig


panel1 = interact(
    sine_wave,
    amplitude=Field(ge=0.0, le=2.5, step=0.05),
    frequency=Field(ge=0.1, le=10.0, step=0.1),
    phase=Field(ge=0.0, le=6.28, step=0.05),
)


# ── 2. Text stats — returns a plain string (shown via repr) ─────────────────


def text_stats(
    text: str = "Hello, Dash!",
    case: Literal["original", "upper", "lower", "title"] = "original",
    reverse: bool = False,
) -> str:
    """Type anything to see live statistics."""
    transformed = {
        "original": text,
        "upper": text.upper(),
        "lower": text.lower(),
        "title": text.title(),
    }[case]
    if reverse:
        transformed = transformed[::-1]
    words = len(text.split())
    chars = len(text)
    return f"{transformed!r}\n\nwords: {words}  chars: {chars}"


panel2 = interact(
    text_stats,
    text=Field(min_length=0, max_length=200),
)


# ── 3. Number table — manual Apply ──────────────────────────────────────────


def number_table(
    start: int = 1,
    count: int = 5,
    step: int = 1,
    show_squares: bool = True,
) -> html.Table:
    """Generate a table of numbers. Click Apply to update."""
    nums = list(range(start, start + count * step, step))
    header = ["n", "n²"] if show_squares else ["n"]
    rows = (
        [[str(n), str(n * n)] for n in nums]
        if show_squares
        else [[str(n)] for n in nums]
    )
    return html.Table(
        [html.Thead(html.Tr([html.Th(h) for h in header]))]
        + [html.Tbody([html.Tr([html.Td(c) for c in row]) for row in rows])],
        style={"borderCollapse": "collapse", "fontFamily": "monospace"},
    )


panel3 = interact(
    number_table,
    _manual=True,
    start=Field(ge=1, le=1000),
    count=Field(ge=1, le=50),
    step=Field(ge=1, le=100),
)


# ── layout ───────────────────────────────────────────────────────────────────

_section_style = {
    "background": "#f9f9f9",
    "border": "1px solid #e0e0e0",
    "borderRadius": "8px",
    "padding": "20px 24px",
    "maxWidth": "700px",
}


def _section(title: str, panel: html.Div) -> html.Div:
    return html.Div(
        style={**_section_style, "marginBottom": "32px"},
        children=[
            html.H3(
                title,
                style={"margin": "0 0 16px 0", "fontSize": "1rem", "color": "#333"},
            ),
            panel,
        ],
    )


app.layout = html.Div(
    style={"fontFamily": "sans-serif", "padding": "32px", "maxWidth": "780px"},
    children=[
        html.H1("interact() demo", style={"marginBottom": "8px"}),
        html.P(
            "dash-fn-interact equivalent of ipywidgets.interact(). "
            "Panels 1 & 2 update live; panel 3 requires Apply.",
            style={"color": "#666", "marginBottom": "32px"},
        ),
        _section("1 — Sine wave  (live · returns plotly Figure)", panel1),
        _section("2 — Text stats  (live · returns str → repr)", panel2),
        _section("3 — Number table  (manual Apply · returns html.Table)", panel3),
    ],
)

if __name__ == "__main__":
    app.run(debug=True, port=1237)
