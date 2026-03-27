[![PyPI](https://img.shields.io/pypi/v/dash-capture)](https://pypi.org/project/dash-capture/)
[![Python](https://img.shields.io/pypi/pyversions/dash-capture)](https://pypi.org/project/dash-capture/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/python/)
[![Dash](https://img.shields.io/badge/Dash-008DE4?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/badge/prek-checked-blue)](https://github.com/saemeon/prek)

# dash-capture

Plotly figures in Dash are rendered by JavaScript in the browser — the Python server never holds the chart as pixels. dash-capture bridges this gap by triggering the capture directly in the running browser, with no server-side headless browser (Chrome, Playwright, webshot2) required. The result is delivered to Python for post-processing, custom rendering, and download.

## Installation

```bash
pip install dash-capture
```

## Usage

### High-level — one-line wizard with form, preview, and download

```python
from dash_capture import capture_graph, plotly_strategy

# Returns an html.Div — place it next to your dcc.Graph
capture_graph(
    graph="my-graph",
    trigger="Export",
    strip_title=True,
    width=2400,
    height=1600,
)
```

Clicking the trigger opens a modal with editable fields, a live preview, and a download button.

### Low-level — wire capture to your own UI

```python
from dash_capture import capture_binding, plotly_strategy

binding = capture_binding(
    "my-graph",
    strategy=plotly_strategy(strip_title=True, width=2400),
    trigger=Input("my-btn", "n_clicks"),
)

# Place binding.store in the layout
# React to binding.store_id to get the base64 PNG
```

### Custom renderer

```python
def my_renderer(_target, _snapshot_img, title: str = ""):
    """_target: file-like, _snapshot_img: callable → raw PNG bytes."""
    png = _snapshot_img()
    # post-process: add watermark, corporate frame, etc.
    _target.write(png)

capture_graph("my-graph", renderer=my_renderer)
```

## Strategies

| Strategy | Method | Use case |
|----------|--------|----------|
| `plotly_strategy()` | `Plotly.toImage()` | Plotly charts — exact resolution |
| `html2canvas_strategy()` | html2canvas | Any DOM element |
| `canvas_strategy()` | `canvas.toDataURL()` | Raw `<canvas>` elements |

Strip patches remove chart decorations before capture without touching the live chart:

```python
plotly_strategy(
    strip_title=True,
    strip_legend=True,
    strip_margin=True,
    width=2400,
    height=1600,
    format="png",   # or "jpeg", "webp", "svg"
)
```

## Pre-filling fields from the live figure

`FromPlotly` reads a value from the running Plotly figure to pre-populate form fields — no re-typing needed:

```python
from dash_capture import capture_graph, FromPlotly

capture_graph(
    "my-graph",
    title=FromPlotly("layout.title.text"),   # reads current title
    sources="Internal data",
)
```

## License

MIT
