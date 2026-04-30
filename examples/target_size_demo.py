"""Target-size capture demo — run with::

    uv run python examples/target_size_demo.py

Then open http://127.0.0.1:8050 and click "Capture at target size".

What this demonstrates
----------------------
Two things at once:

1. ``capture_element`` + ``html2canvas_strategy`` honour
   ``capture_width`` / ``capture_height`` on the renderer signature,
   the same way ``plotly_strategy`` already did.

2. **Snapshot caching.** The wizard has dimensional fields
   (``width``/``height``, fed through ``capture_resolver`` to drive the
   browser-side capture) and a non-dimensional field (``title``,
   composited onto the PNG server-side). Editing the title should NOT
   trigger a fresh JS capture — the cache keys on the resolver output,
   so identical opts reuse the previous snapshot.

   Watch the browser DevTools network tab while toggling fields to
   see this: width/height changes ⇒ JS capture roundtrip; title
   changes ⇒ none.
"""

from __future__ import annotations

import io

import dash
from dash import html
from PIL import Image, ImageDraw, ImageFont

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
    title: str = "Q4 Report — Headline KPIs",
    width: int = 1200,
    height: int = 600,
    capture_width: int = 1200,
    capture_height: int = 600,
):
    """Composite a title bar onto the snapshot.

    ``width`` / ``height`` drive the browser-side capture (via
    ``capture_resolver``) and so are part of the cache key.
    ``title`` is composited onto the PNG server-side and is NOT in
    the cache key — editing the title reuses the cached snapshot.
    """
    img = Image.open(io.BytesIO(_snapshot_img()))
    bar_h = 48
    out = Image.new("RGB", (img.width, img.height + bar_h), "white")
    out.paste(img, (0, bar_h))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("Helvetica", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((16, 12), title, fill="black", font=font)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    _target.write(buf.getvalue())


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
