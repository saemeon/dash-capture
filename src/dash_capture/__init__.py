# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Browser-side capture pipeline for Dash components.

Captures Plotly figures and arbitrary DOM elements from the browser,
delivers the result to Python for post-processing, and provides
download / clipboard export — no headless browser required.

Quick start::

    from dash_capture import capture_graph
    capture_graph("my-graph", trigger="Export")

The default renderer is a zero-dependency passthrough — the wizard
collapses to *Generate* + *Download* with no form fields. Custom
renderers can be defined as ordinary Python functions whose type-hinted
parameters become auto-generated form fields.

Public API:

* :func:`capture_graph` — wizard for ``dcc.Graph`` (Plotly strategy)
* :func:`capture_element` — wizard for any DOM element (html2canvas)
* :func:`capture_binding` — low-level JS-capture → ``dcc.Store`` binding
* :class:`CaptureStrategy`, :func:`plotly_strategy`,
  :func:`html2canvas_strategy`, :func:`canvas_strategy`,
  :func:`multi_canvas_strategy` — capture strategies
* :func:`build_reflow_preprocess`, :data:`MULTI_CANVAS_CAPTURE_JS` —
  building blocks for custom strategies
* :class:`ModebarButton`, :class:`ModebarIcon`,
  :func:`add_modebar_button` — Plotly modebar trigger helpers
* :class:`FromPlotly` — pre-populate form fields from the live figure
* :class:`WizardAction` — extra action button for the wizard

Optional submodules:

* :mod:`dash_capture.pil` — built-in decoration renderers
  (``bordered`` / ``titled`` / ``watermarked``). Requires the ``[pil]``
  extra: ``pip install 'dash-capture[pil]'``.
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
)
from dash_capture.strategies import (
    MULTI_CANVAS_CAPTURE_JS,
    CaptureStrategy,
    build_reflow_preprocess,
    canvas_strategy,
    html2canvas_strategy,
    multi_canvas_strategy,
    plotly_strategy,
)

__all__ = [
    # low-level
    "CaptureBinding",
    "capture_binding",
    # high-level (wizard)
    "capture_graph",
    "capture_element",
    # strategies
    "CaptureStrategy",
    "plotly_strategy",
    "html2canvas_strategy",
    "canvas_strategy",
    "multi_canvas_strategy",
    # building blocks for custom strategies
    "build_reflow_preprocess",
    "MULTI_CANVAS_CAPTURE_JS",
    # modebar
    "add_modebar_button",
    "ModebarButton",
    "ModebarIcon",
    # hooks
    "FromPlotly",
    # wizard extensibility
    "WizardAction",
]
