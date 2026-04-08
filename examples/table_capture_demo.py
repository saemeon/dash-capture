"""dash-capture table demo — run with: uv run python examples/table_capture_demo.py

Captures a ``dash_table.DataTable`` to PNG using ``capture_element`` and
``html2canvas``. Shows two renderers:

  1. passthrough — write the raw screenshot bytes to the download target
  2. titled     — wrap the screenshot with a PIL title bar before download
"""

import io
from datetime import date

import dash
import pandas as pd
from dash import dash_table, html

from dash_capture import capture_element

# --- sample table ---
df = pd.DataFrame(
    {
        "Country": ["Switzerland", "Germany", "France", "Italy", "Austria"],
        "Population (M)": [8.7, 83.2, 67.4, 59.6, 9.0],
        "GDP per capita ($)": [93_720, 51_380, 44_850, 35_550, 53_640],
        "Life expectancy": [83.4, 80.9, 82.5, 82.9, 81.6],
    }
)

table = dash_table.DataTable(
    id="country-table",
    columns=[{"name": c, "id": c} for c in df.columns],
    data=df.to_dict("records"),
    style_table={"width": "600px"},
    style_header={
        "backgroundColor": "#2c3e50",
        "color": "white",
        "fontWeight": "bold",
    },
    style_cell={"padding": "8px", "fontFamily": "system-ui, sans-serif"},
    style_data_conditional=[
        {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
    ],
)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def passthrough(_target, _snapshot_img):
    """No parameters → wizard shows just Generate + Download."""
    _target.write(_snapshot_img())


def titled(
    _target,
    _snapshot_img,
    title: str = "Country statistics",
    report_date: date = date(2026, 4, 8),
):
    """Add a title bar above the captured table.

    str → text input, date → date picker (auto-generated from type hints).
    """
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(_snapshot_img()))
    bar_h = 50
    new = Image.new("RGB", (img.width, img.height + bar_h), "white")
    new.paste(img, (0, bar_h))
    draw = ImageDraw.Draw(new)
    draw.text((10, 10), title, fill="black")
    draw.text((10, 28), str(report_date), fill="gray")
    buf = io.BytesIO()
    new.save(buf, format="PNG")
    _target.write(buf.getvalue())


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = dash.Dash(__name__)

app.layout = html.Div(
    style={
        "maxWidth": "800px",
        "margin": "0 auto",
        "padding": "20px",
        "fontFamily": "system-ui, sans-serif",
    },
    children=[
        html.H2("dash-capture — DataTable example"),
        html.P(
            "capture_element() uses html2canvas to screenshot any DOM "
            "element, including dash_table.DataTable."
        ),
        html.Hr(),
        table,
        html.Br(),
        html.H4("1. Simple capture"),
        capture_element(
            "country-table",
            renderer=passthrough,
            trigger="Capture table",
            filename="country-table.png",
        ),
        html.Br(),
        html.H4("2. Capture with title bar"),
        capture_element(
            "country-table",
            renderer=titled,
            trigger="Capture with title",
            filename="country-table-titled.png",
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=False)
