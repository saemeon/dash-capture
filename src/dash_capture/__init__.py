# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Browser-side capture pipeline for Dash components.

Captures Plotly figures and arbitrary DOM elements from the browser,
delivers the result to Python for post-processing, and provides
download/clipboard export -- no headless browser required.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dash-capture")
except PackageNotFoundError:
    __version__ = "unknown"


from dash_capture._modebar import ModebarButton, ModebarIcon, add_modebar_button
from dash_capture.capture import (
    CaptureBinding,
    FromPlotly,
    WizardAction,
    capture_binding,
    capture_element,
    capture_graph,
    renderer,
)
from dash_capture.strategies import (
    CaptureStrategy,
    canvas_strategy,
    html2canvas_strategy,
    plotly_strategy,
)

__all__ = [
    # low-level
    "CaptureBinding",
    "capture_binding",
    # high-level (wizard)
    "capture_graph",
    "capture_element",
    # renderer protocol
    "renderer",
    # strategies
    "CaptureStrategy",
    "plotly_strategy",
    "html2canvas_strategy",
    "canvas_strategy",
    # modebar
    "add_modebar_button",
    "ModebarButton",
    "ModebarIcon",
    # hooks
    "FromPlotly",
    # wizard extensibility
    "WizardAction",
]
