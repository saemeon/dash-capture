# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Capture strategies: browser-side preprocess and capture JS fragments.

Built-in strategies: ``plotly_strategy``, ``html2canvas_strategy``,
``canvas_strategy``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass
class CaptureStrategy:
    """Two-stage capture pipeline: preprocess JS + capture JS.

    Parameters
    ----------
    preprocess : str or None
        JS code that runs before capture. Receives ``(el, opts)`` where
        *el* is the DOM element. ``None`` means no preprocessing.
    capture : str
        JS code that performs the capture. Must return a base64 data-URI
        string (or a Promise thereof).
    format : str
        Default output format: ``"png"``, ``"jpeg"``, ``"webp"``, ``"svg"``.

    Notes
    -----
    Both fields execute as JavaScript in the browser. Never pass untrusted
    user input into these fields.
    """

    preprocess: str | None = None
    capture: str = ""
    format: str = "png"


# ---------------------------------------------------------------------------
# Strip-patch JS fragments (shared with shinycapture R package)
# ---------------------------------------------------------------------------

_STRIP_TITLE = [
    "layout.title = {text: ''};",
    "layout.margin = {...(layout.margin || {}), t: 20};",
]
_STRIP_LEGEND = ["layout.showlegend = false;"]
_STRIP_ANNOTATIONS = ["layout.annotations = [];"]
_STRIP_AXIS_TITLES = [
    "Object.keys(layout).forEach(k => {"
    " if (/^[xy]axis/.test(k))"
    " layout[k] = {...(layout[k]||{}), title: {text: ''}}; });"
]
_STRIP_COLORBAR = ["data = data.map(t => ({...t, showscale: false}));"]
_STRIP_MARGIN = ["layout.margin = {l:0, r:0, t:0, b:0, pad:0};"]


def _build_strip_patches(
    strip_title: bool = False,
    strip_legend: bool = False,
    strip_annotations: bool = False,
    strip_axis_titles: bool = False,
    strip_colorbar: bool = False,
    strip_margin: bool = False,
) -> list[str]:
    """Build JS patch statements for stripping Plotly figure elements."""
    patches: list[str] = []
    if strip_title:
        patches += _STRIP_TITLE
    if strip_legend:
        patches += _STRIP_LEGEND
    if strip_annotations:
        patches += _STRIP_ANNOTATIONS
    if strip_axis_titles:
        patches += _STRIP_AXIS_TITLES
    if strip_colorbar:
        patches += _STRIP_COLORBAR
    if strip_margin:
        patches += _STRIP_MARGIN
    return patches


def _build_plotly_preprocess(patches: list[str], params: Mapping) -> str | None:
    """Build JS preprocess that clones the figure into an offscreen div."""
    if not patches:
        return None

    dim_w = (
        "capture_width != null ? capture_width : graphDiv.offsetWidth"
        if "capture_width" in params
        else "graphDiv.offsetWidth"
    )
    dim_h = (
        "capture_height != null ? capture_height : graphDiv.offsetHeight"
        if "capture_height" in params
        else "graphDiv.offsetHeight"
    )
    patches_js = "\n                ".join(patches)

    return f"""\
                const layout = JSON.parse(
                    JSON.stringify(graphDiv.layout || {{}}));
                let data = graphDiv.data;
                {patches_js}
                const tmp = document.createElement('div');
                tmp.style.cssText =
                    'position:fixed;left:-9999px;width:'
                    + ({dim_w}) + 'px;height:' + ({dim_h}) + 'px';
                document.body.appendChild(tmp);
                await Plotly.newPlot(tmp, data, layout);
                el._dcap_tmp = tmp;"""


_PLOTLY_CAPTURE = """\
                const target = el._dcap_tmp || graphDiv;
                try {
                    return await Plotly.toImage(target, opts);
                } finally {
                    if (el._dcap_tmp) {
                        document.body.removeChild(el._dcap_tmp);
                        delete el._dcap_tmp;
                    }
                }"""

_PLOTLY_CAPTURE_SIMPLE = """\
                return await Plotly.toImage(graphDiv, opts);"""

_HTML2CANVAS_CAPTURE = """\
                if (!window.html2canvas) {
                    console.error('dash-capture: html2canvas is not loaded. '
                        + 'Include it via app.scripts or external_scripts.');
                    return window.dash_clientside.no_update;
                }
                const canvas = await html2canvas(el, {
                    scale: opts.scale || 2,
                    useCORS: true,
                    logging: false
                });
                const mime = opts.format === 'jpg'
                    ? 'image/jpeg' : 'image/' + (opts.format || 'png');
                return canvas.toDataURL(mime, opts.quality || undefined);"""

_CANVAS_CAPTURE = """\
                const cvs = el.querySelector('canvas') || el;
                const mime = opts.format === 'jpg'
                    ? 'image/jpeg' : 'image/' + (opts.format || 'png');
                return cvs.toDataURL(mime, opts.quality || undefined);"""


# ---------------------------------------------------------------------------
# Built-in strategy factories
# ---------------------------------------------------------------------------


def plotly_strategy(
    strip_title: bool = False,
    strip_legend: bool = False,
    strip_annotations: bool = False,
    strip_axis_titles: bool = False,
    strip_colorbar: bool = False,
    strip_margin: bool = False,
    format: str = "png",
    _params: Mapping | None = None,
) -> CaptureStrategy:
    """``Plotly.toImage()`` strategy with optional element stripping.

    Parameters
    ----------
    strip_title, strip_legend, strip_annotations, strip_axis_titles, \
    strip_colorbar, strip_margin : bool
        Remove the corresponding element from the figure before capture.
    format : str
        Output format (default ``"png"``).

    Returns
    -------
    CaptureStrategy

    Examples
    --------
    >>> from dash_capture import plotly_strategy
    >>> strategy = plotly_strategy(strip_title=True, strip_legend=True)
    """
    patches = _build_strip_patches(
        strip_title,
        strip_legend,
        strip_annotations,
        strip_axis_titles,
        strip_colorbar,
        strip_margin,
    )
    preprocess = _build_plotly_preprocess(patches, _params or {})
    capture = _PLOTLY_CAPTURE if preprocess else _PLOTLY_CAPTURE_SIMPLE
    return CaptureStrategy(preprocess=preprocess, capture=capture, format=format)


def html2canvas_strategy(format: str = "png") -> CaptureStrategy:
    """``html2canvas`` strategy for capturing arbitrary DOM elements.

    Parameters
    ----------
    format : str
        Output format (default ``"png"``).

    Returns
    -------
    CaptureStrategy
    """
    return CaptureStrategy(capture=_HTML2CANVAS_CAPTURE, format=format)


def canvas_strategy(format: str = "png") -> CaptureStrategy:
    """Raw ``canvas.toDataURL()`` strategy for canvas-based components.

    Parameters
    ----------
    format : str
        Output format (default ``"png"``).

    Returns
    -------
    CaptureStrategy
    """
    return CaptureStrategy(capture=_CANVAS_CAPTURE, format=format)


# ---------------------------------------------------------------------------
# JS assembly — wraps the strategy into a Dash clientside callback function
# ---------------------------------------------------------------------------


def build_capture_js(
    element_id: str,
    strategy: CaptureStrategy,
    active_capture: list[str],
    params: Mapping,
    *,
    fixed_capture: dict[str, Any] | None = None,
    from_resolved: bool = False,
) -> str:
    """Assemble a strategy into a Dash clientside callback JS function."""
    if from_resolved:
        js_args = "resolved_data, fmt"
        js_build_opts = """if (resolved_data) {
                    Object.keys(resolved_data).forEach(function(k) {
                        var key = k.startsWith('capture_') ? k.slice(8) : k;
                        opts[key] = resolved_data[k];
                    });
                }"""
    else:
        js_args = ", ".join(["n_clicks", "n_intervals", "fmt", *active_capture])
        # Dynamic capture params — read from callback State args
        opt_lines: list[str] = [
            f"if ({p} != null) opts.{p[len('capture_') :]} = {p};"
            for p in active_capture
        ]
        # Fixed capture params — inlined as constants
        opt_lines += [
            f"opts.{p[len('capture_') :]} = {v!r};"
            for p, v in (fixed_capture or {}).items()
            if v is not None
        ]
        js_build_opts = "\n                ".join(opt_lines)

    # Element lookup — Plotly-aware (look for .js-plotly-plot inside container)
    # For non-Plotly strategies, graphDiv === el which is fine.
    # Escape element_id to prevent JS injection via crafted component IDs
    safe_id = element_id.replace("\\", "\\\\").replace("'", "\\'")

    guard = (
        "if (!resolved_data) { return window.dash_clientside.no_update; }"
        if from_resolved
        else "if (!n_clicks && !n_intervals) { return window.dash_clientside.no_update; }"
    )

    js_head = f"""
            async function({js_args}) {{
                {guard}
                const el = document.getElementById('{safe_id}');
                if (!el) return window.dash_clientside.no_update;
                const graphDiv =
                    el.querySelector('.js-plotly-plot') || el;
                const opts = {{format: fmt || '{strategy.format}'}};
                {js_build_opts}
        """

    body_parts = []
    if strategy.preprocess:
        body_parts.append(strategy.preprocess)
    body_parts.append(strategy.capture)

    body = "\n".join(body_parts)
    return js_head + body + "\n            }"
