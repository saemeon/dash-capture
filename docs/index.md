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

### FromPlotly

::: dash_capture.capture.FromPlotly
