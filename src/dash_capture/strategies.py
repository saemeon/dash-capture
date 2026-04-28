# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Capture strategies: browser-side preprocess and capture JS fragments.

Built-in strategies: ``plotly_strategy``, ``html2canvas_strategy``,
``canvas_strategy``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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
    _rebuild : callable or None
        Internal hook used by :func:`capture_graph` / :func:`capture_element`
        to wire renderer-declared ``capture_*`` parameters into a strategy
        the user has already constructed. Strategy factories that consume
        ``_params`` (``plotly_strategy``, ``html2canvas_strategy``,
        ``dygraph_strategy``) set this to a closure that re-runs the
        factory with ``_params`` injected. ``None`` means "don't rewire."
        Users should not set this directly.

    Notes
    -----
    Both ``preprocess`` and ``capture`` execute as JavaScript in the
    browser. Never pass untrusted user input into these fields.
    """

    preprocess: str | None = None
    capture: str = ""
    format: str = "png"
    _rebuild: Callable[[Mapping], "CaptureStrategy"] | None = field(
        default=None, repr=False, compare=False
    )


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
                try {
                    const canvas = await html2canvas(el, {
                        scale: opts.scale || 2,
                        useCORS: true,
                        logging: false
                    });
                    const mime = opts.format === 'jpg'
                        ? 'image/jpeg' : 'image/' + (opts.format || 'png');
                    return canvas.toDataURL(mime, opts.quality || undefined);
                } finally {
                    if (el._dcap_saved) {
                        el.style.width = el._dcap_saved.w;
                        el.style.height = el._dcap_saved.h;
                        delete el._dcap_saved;
                    }
                }"""

_CANVAS_CAPTURE = """\
                const cvs = el.querySelector('canvas') || el;
                const mime = opts.format === 'jpg'
                    ? 'image/jpeg' : 'image/' + (opts.format || 'png');
                return cvs.toDataURL(mime, opts.quality || undefined);"""


def _build_html2canvas_reflow_preprocess(
    has_width: bool,
    has_height: bool,
    settle_frames: int,
) -> str:
    """Build JS preprocess that live-resizes the element to opts.width/height.

    Saves original inline ``width``/``height`` on ``el._dcap_saved`` so
    the capture JS's ``finally`` block can restore them. Settles for
    ``settle_frames`` rAF ticks so ResizeObservers (dygraphs, ECharts,
    DataTable column-width JS) have time to re-lay-out before
    html2canvas snapshots.

    Note: we deliberately do NOT use ``visibility: hidden`` to suppress
    the resize flicker — visibility cascades to descendants and
    html2canvas skips ``visibility: hidden`` elements, which would
    drop all the text content from the captured image. A brief flicker
    is acceptable for a deliberate capture click; correct output is not
    optional.
    """
    set_w = "if (opts.width != null) el.style.width = opts.width + 'px';"
    set_h = "if (opts.height != null) el.style.height = opts.height + 'px';"
    set_dims = "\n                ".join(
        x for x, on in [(set_w, has_width), (set_h, has_height)] if on
    )
    return f"""\
                el._dcap_saved = {{
                    w: el.style.width,
                    h: el.style.height
                }};
                {set_dims}
                for (let i = 0; i < {settle_frames}; i++) {{
                    await new Promise(r => requestAnimationFrame(r));
                }}"""


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
        Advanced — defaults are all ``False``.
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
    return CaptureStrategy(
        preprocess=preprocess,
        capture=capture,
        format=format,
        _rebuild=lambda p: plotly_strategy(
            strip_title=strip_title,
            strip_legend=strip_legend,
            strip_annotations=strip_annotations,
            strip_axis_titles=strip_axis_titles,
            strip_colorbar=strip_colorbar,
            strip_margin=strip_margin,
            format=format,
            _params=p,
        ),
    )


def html2canvas_strategy(
    format: str = "png",
    settle_frames: int = 2,
    _params: Mapping | None = None,
) -> CaptureStrategy:
    """``html2canvas`` strategy for capturing arbitrary DOM elements.

    When the renderer declares ``capture_width`` and/or ``capture_height``
    parameters, the strategy emits a live-resize preprocess: the element
    is temporarily resized to the target dimensions, the browser is given
    a few ``requestAnimationFrame`` ticks to settle (so ``ResizeObserver``
    listeners and any JS-driven layout — dygraphs redraws,
    ``dash_table.DataTable`` column-width recompute, etc. — can react),
    html2canvas snapshots, and original inline styles are restored in a
    ``finally`` block. This mirrors how :func:`plotly_strategy` already
    consumes ``capture_width``/``capture_height``.

    Parameters
    ----------
    format : str
        Output format (default ``"png"``).
    settle_frames : int
        Number of ``requestAnimationFrame`` ticks to await between
        resizing the element and capturing. Default ``2`` covers most
        ResizeObserver-driven components; bump higher for components
        that animate layout changes.

    Returns
    -------
    CaptureStrategy

    Notes
    -----
    Live-resize is visible to the user as a brief flicker — the chart
    or layout reflows in place before the screenshot is taken, then
    snaps back. This is intentional: any "hide during capture"
    mechanism (``visibility: hidden``, ``opacity: 0``) cascades to
    descendants, and html2canvas skips hidden elements, which would
    silently drop all text from the captured image. The flicker is
    the price of correctness.

    Live-resize also triggers any user-installed ``ResizeObserver``
    callbacks and may flush Dash resize-driven callbacks during the
    capture window. For deliberate "Capture" button clicks this is
    almost always benign, but be aware if your app has expensive
    resize handlers.
    """
    params = _params or {}
    has_w = "capture_width" in params
    has_h = "capture_height" in params
    preprocess: str | None = None
    if has_w or has_h:
        preprocess = _build_html2canvas_reflow_preprocess(
            has_w, has_h, settle_frames
        )
    return CaptureStrategy(
        preprocess=preprocess,
        capture=_HTML2CANVAS_CAPTURE,
        format=format,
        _rebuild=lambda p: html2canvas_strategy(
            format=format, settle_frames=settle_frames, _params=p
        ),
    )


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
