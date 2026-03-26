# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.


from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dash-capture")
except PackageNotFoundError:
    __version__ = "unknown"


from dash_capture.capture import (
    BatchBinding,
    CaptureBinding,
    FromPlotly,
    capture_batch,
    capture_binding,
    capture_element,
    capture_graph,
    # backwards compat aliases
    component_exporter,
    graph_exporter,
)
from dash_capture.strategies import (
    CaptureStrategy,
    canvas_strategy,
    html2canvas_strategy,
    plotly_strategy,
)

__all__ = [
    # low-level
    "BatchBinding",
    "CaptureBinding",
    "capture_batch",
    "capture_binding",
    # high-level (wizard)
    "capture_graph",
    "capture_element",
    # strategies
    "CaptureStrategy",
    "plotly_strategy",
    "html2canvas_strategy",
    "canvas_strategy",
    # hooks
    "FromPlotly",
    # backwards compat
    "graph_exporter",
    "component_exporter",
]
