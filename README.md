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

Optional extras for built-in decoration renderers:

```bash
pip install 'dash-capture[pil]'   # bordered / titled / watermarked
```

## Usage

### Default — one-line wizard, no setup

```python
from dash_capture import capture_graph

# Returns an html.Div — place it next to your dcc.Graph
capture_graph("my-graph", trigger="Export")
```

The default renderer is a zero-dependency passthrough: the wizard shows just *Generate* + *Download*. Clicking the trigger opens a modal with the live preview and a PNG / JPEG / SVG download.

### Plotly chart capture

```python
from dash_capture import capture_graph, plotly_strategy

capture_graph(
    "my-graph",
    trigger="Export",
    strategy=plotly_strategy(
        strip_title=True,
        strip_legend=True,
        strip_margin=True,
        format="png",   # or "jpeg", "webp", "svg"
    ),
)
```

Strip patches remove chart decorations before capture without touching the live chart.

### Any DOM element (table, custom widget) — html2canvas

```python
from dash_capture import capture_element

capture_element("my-data-table", trigger="Capture table")
```

`capture_element` defaults to `html2canvas_strategy()` and works with any Dash component that has an `id`.

### Built-in PIL renderers (`dash-capture[pil]`)

```python
from dash_capture import capture_graph
from dash_capture.pil import titled, bordered, watermarked

# Title bar above the captured chart
capture_graph("my-graph", renderer=titled)

# Colored border
capture_graph("my-graph", renderer=bordered)

# Diagonal watermark
capture_graph("my-graph", renderer=watermarked)
```

The wizard auto-generates form fields (text input, color picker, dropdown) from each renderer's type hints, so users can edit `title`, `color`, `width`, etc. before downloading.

### Custom renderer

Define a function that takes `_target` (file-like) and `_snapshot_img` (callable returning raw PNG bytes). Type-hinted parameters become auto-generated form fields in the wizard.

```python
from dash_capture import capture_graph, renderer

@renderer
def my_renderer(_target, _snapshot_img, title: str = "", dpi: int = 150):
    png = _snapshot_img()
    # post-process: add a watermark, corporate frame, etc.
    _target.write(png)

capture_graph("my-graph", renderer=my_renderer)
```

The `@renderer` decorator validates the magic parameter names at definition time. A typo like `_snaphot_img` raises `ValueError` with a "did you mean ...?" hint instead of silently failing at runtime.

### Low-level — wire capture to your own UI

```python
from dash import Input
from dash_capture import capture_binding, plotly_strategy

binding = capture_binding(
    "my-graph",
    strategy=plotly_strategy(strip_title=True),
    trigger=Input("my-btn", "n_clicks"),
)

# Place binding.store in the layout
# React to binding.store_id to get the base64 PNG
```

## Strategies

| Strategy | Method | Use case |
|----------|--------|----------|
| `plotly_strategy()` | `Plotly.toImage()` | Plotly charts — exact resolution |
| `html2canvas_strategy()` | html2canvas | Any DOM element (tables, divs) |
| `canvas_strategy()` | `canvas.toDataURL()` | Raw `<canvas>` elements |

`plotly_strategy()` accepts strip flags (`strip_title`, `strip_legend`, `strip_annotations`, `strip_axis_titles`, `strip_colorbar`, `strip_margin`) and `format`. For per-export width / height / scale, declare `capture_width: int` / `capture_height: int` / `capture_scale: float` parameters on your renderer — they get plumbed into `Plotly.toImage()` automatically.

## Pre-filling fields from the live figure

`FromPlotly` reads a value from the running Plotly figure to pre-populate auto-generated form fields:

```python
from dash import dcc
from dash_capture import capture_graph, FromPlotly, renderer

graph = dcc.Graph(id="my-graph", figure=fig)

@renderer
def export(_target, _snapshot_img, title: str = "", sources: str = ""):
    _target.write(_snapshot_img())

capture_graph(
    graph,
    renderer=export,
    field_specs={"title": FromPlotly("layout.title.text", graph)},
)
```

## License

MIT
