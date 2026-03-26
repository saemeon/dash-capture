# dash-capture

Browser capture & custom renderer pipeline for Plotly Dash components.

## Installation

```bash
pip install dash-capture
```

## Components

| Component | Description |
|-----------|-------------|
| `graph_exporter` | Capture wizard for `dcc.Graph` — modal with auto-generated fields, live preview, and PNG download |
| `build_wizard` | Generic modal dialog |
| `build_dropdown` | Generic anchored dropdown with click-outside-to-close |
| `FromPlotly` | `FieldHook` that pre-fills a field from the live Plotly figure |
| `FieldHook` | Base class for runtime field defaults derived from Dash component state |

**Supported field types:** `str`, `int`, `float`, `bool`, `date`, `datetime`, `Literal[...]`, `list[T]`, `tuple[T, ...]`, `T | None`

## API Reference

::: dash_capture.capture.capture_graph

::: dash_capture.capture.graph_exporter
