# dash-capture

Plotly figures in Dash are rendered by JavaScript in the browser — the Python server never holds the chart as pixels. dash-capture bridges this gap by triggering the capture directly in the running browser, with no server-side headless browser (Chrome, Playwright, webshot2) required. The result is delivered to Python for post-processing, custom rendering, and download.

## Installation

```bash
pip install dash-capture
```

## API Reference

### capture_graph

::: dash_capture.capture.capture_graph

### capture_element

::: dash_capture.capture.capture_element

### capture_binding

::: dash_capture.capture.capture_binding

### CaptureBinding

::: dash_capture.capture.CaptureBinding

### CaptureStrategy

::: dash_capture.strategies.CaptureStrategy

### plotly_strategy

::: dash_capture.strategies.plotly_strategy

### html2canvas_strategy

::: dash_capture.strategies.html2canvas_strategy

### canvas_strategy

::: dash_capture.strategies.canvas_strategy

### multi_canvas_strategy

::: dash_capture.strategies.multi_canvas_strategy

### build_reflow_preprocess

::: dash_capture.strategies.build_reflow_preprocess

### MULTI_CANVAS_CAPTURE_JS

The raw async-IIFE source string used by
[multi_canvas_strategy](#multi_canvas_strategy). Exposed for chart
libraries that want to invoke the same JS directly from their own
component code (e.g. a built-in download button) without going through
a `CaptureStrategy`. Signature: `(el, fmt, hideSelectors, debug)`.

### FromPlotly

::: dash_capture.capture.FromPlotly
