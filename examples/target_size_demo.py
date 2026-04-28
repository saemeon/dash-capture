"""Target-size capture demo — run with::

    uv run python examples/target_size_demo.py

Then open http://127.0.0.1:8050 and click "Capture at target size".

What this demonstrates
----------------------
``capture_element`` + ``html2canvas_strategy`` now honour
``capture_width`` / ``capture_height`` on the renderer signature, the
same way ``plotly_strategy`` already did. Before capture, the strategy:

1. Saves the element's inline ``width`` / ``height`` / ``visibility``.
2. Sets the new dimensions from the wizard form (via
   ``capture_resolver``).
3. Awaits a couple of ``requestAnimationFrame`` ticks so any
   ``ResizeObserver`` listeners or CSS reflow can settle.
4. Runs ``html2canvas``.
5. Restores the saved styles in a ``finally`` block.

The element below is a CSS-flex card layout — reduce the width and the
cards stack vertically; widen it and they spread out. Pick a few
sizes from the form and compare the downloaded PNGs.
"""

from __future__ import annotations

import dash
from dash import html

from dash_capture import capture_element

# ---------------------------------------------------------------------------
# A CSS-reflowing layout to capture
# ---------------------------------------------------------------------------

CARD_STYLE = {
    "flex": "1 1 220px",
    "minHeight": "120px",
    "padding": "16px",
    "borderRadius": "10px",
    "color": "white",
    "fontFamily": "system-ui, sans-serif",
}

LAYOUT = html.Div(
    id="reportcard-grid",
    style={
        "display": "flex",
        "flexWrap": "wrap",
        "gap": "12px",
        "padding": "16px",
        "background": "#f1f3f5",
        "borderRadius": "12px",
        # Initial size — the live render is 720×260, but the capture
        # form below will resize it to whatever you pick.
        "width": "720px",
        "height": "260px",
    },
    children=[
        html.Div(
            style={**CARD_STYLE, "background": "#1f77b4"},
            children=[html.H3("Revenue"), html.P("CHF 12.4M (+8.3% YoY)")],
        ),
        html.Div(
            style={**CARD_STYLE, "background": "#ff7f0e"},
            children=[html.H3("Active users"), html.P("184k (+12.1%)")],
        ),
        html.Div(
            style={**CARD_STYLE, "background": "#2ca02c"},
            children=[html.H3("NPS"), html.P("47 (+3 vs Q3)")],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Renderer + resolver
# ---------------------------------------------------------------------------


def renderer(
    _target,
    _snapshot_img,
    width: int = 1200,
    height: int = 600,
    capture_width: int = 1200,
    capture_height: int = 600,
):
    """Two pairs of fields — wizard-visible vs strategy-visible.

    ``width`` / ``height`` show up as form fields in the wizard
    (auto-generated from type hints). ``capture_width`` /
    ``capture_height`` are the wire-protocol the strategy reads to
    actually resize the element. The ``capture_resolver`` below maps
    one to the other so a single set of form values drives both.
    """
    _target.write(_snapshot_img())


def resolve(width, height, **_):
    """Translate form values to ``capture_*`` opts the strategy reads."""
    return {"capture_width": width, "capture_height": height}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = dash.Dash(__name__)

app.layout = html.Div(
    style={
        "maxWidth": "960px",
        "margin": "0 auto",
        "padding": "32px",
        "fontFamily": "system-ui, sans-serif",
    },
    children=[
        html.H2("Target-size capture"),
        html.P(
            "The card grid below is 720×260 on screen. Click "
            "Capture and pick a different width/height in the wizard "
            "— the cards reflow to the new aspect before the screenshot "
            "is taken, so the downloaded PNG matches the report layout "
            "you want, not the live render."
        ),
        LAYOUT,
        html.Br(),
        capture_element(
            "reportcard-grid",
            renderer=renderer,
            capture_resolver=resolve,
            trigger="Capture at target size",
            filename="reportcard-grid.png",
        ),
    ],
)


if __name__ == "__main__":
    app.run(debug=False)
