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
    _rebuild: Callable[[Mapping], CaptureStrategy] | None = field(
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
        "opts.width != null ? opts.width : graphDiv.offsetWidth"
        if "capture_width" in params
        else "graphDiv.offsetWidth"
    )
    dim_h = (
        "opts.height != null ? opts.height : graphDiv.offsetHeight"
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


def build_reflow_preprocess(
    has_width: bool,
    has_height: bool,
    settle_frames: int = 2,
) -> str:
    """Build JS preprocess that live-resizes the element to opts.width/height.

    Public helper for custom capture strategies. Used by
    :func:`html2canvas_strategy` and :func:`multi_canvas_strategy`, and
    intended for third-party strategies that want the same target-size
    behaviour without duplicating the JS.

    Saves original inline ``width``/``height`` on ``el._dcap_saved`` so
    the capture JS's ``finally`` block can restore them. Settles for
    ``settle_frames`` rAF ticks so ResizeObservers (dygraphs, ECharts,
    DataTable column-width JS) have time to re-lay-out before capture.

    Note: we deliberately do NOT use ``visibility: hidden`` to suppress
    the resize flicker — visibility cascades to descendants and
    html2canvas skips ``visibility: hidden`` elements, which would
    drop all the text content from the captured image. A brief flicker
    is acceptable for a deliberate capture click; correct output is not
    optional.

    Parameters
    ----------
    has_width, has_height : bool
        Whether the renderer declared ``capture_width`` /
        ``capture_height``. Typically computed as
        ``"capture_width" in (_params or {})`` etc.
    settle_frames : int, default 2
        rAF ticks to await between resize and capture.

    Returns
    -------
    str
        JS source fragment, intended to be assigned to
        ``CaptureStrategy.preprocess``.
    """
    set_w = "if (opts.width != null) el.style.width = opts.width + 'px';"
    set_h = "if (opts.height != null) el.style.height = opts.height + 'px';"
    set_dims = "\n                ".join(
        x for x, on in [(set_w, has_width), (set_h, has_height)] if on
    )
    return f"""\
                if (!el._dcap_saved) {{
                    el._dcap_saved = {{
                        w: el.style.width,
                        h: el.style.height
                    }};
                }}
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
        preprocess = build_reflow_preprocess(has_w, has_h, settle_frames)
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
# Multi-canvas strategy — for charts that render to several stacked <canvas>
# ---------------------------------------------------------------------------
#
# Self-contained async IIFE. Takes ``(el, fmt, hideSelectors, debug)`` and
# returns a Promise<data-URI>. Designed for chart libraries (dygraphs,
# custom canvas widgets) that draw onto multiple stacked canvases rather
# than a single output canvas.
#
# Behaviour:
#   1. For each CSS selector in ``hideSelectors``, hide the matching
#      elements before capture (saved + restored after) so things like
#      range-selectors or in-chart UI don't appear in the export.
#   2. Allocate a destination canvas at offset(W,H) * devicePixelRatio
#      and scale the 2D context by DPR — output is sharp on retina.
#   3. For each visible source canvas under ``el``, blit it via the
#      9-arg drawImage, mapping its full backing buffer (cv.width ×
#      cv.height) into its CSS-pixel rect.
#   4. Rasterise the HTML overlay layer (titles, labels, legends,
#      annotations) via ``window.html2canvas`` at the same DPR and
#      composite it on top. ``ignoreElements`` skips ``<canvas>`` so we
#      don't double-paint them at html2canvas's lower fidelity. If
#      html2canvas isn't loaded the overlay step silently no-ops;
#      ``multi_canvas_strategy`` always queues the asset, so this only
#      happens for unusual setups (e.g. invoking the JS directly from
#      a host component's modebar before any strategy was constructed).
#   5. Restore any hidden elements.
#   6. Resolve with the data-URI.
#
# When ``debug`` is true, the IIFE logs dpr/dimensions/per-canvas rects
# and outlines each blit destination with a 1px red border.
MULTI_CANVAS_CAPTURE_JS = """\
(async function (el, fmt, hideSelectors, debug) {
    if (hideSelectors && hideSelectors.length) {
        el._dcap_hidden = [];
        hideSelectors.forEach(function (sel) {
            el.querySelectorAll(sel).forEach(function (item) {
                el._dcap_hidden.push({el: item, display: item.style.display});
                item.style.display = 'none';
            });
        });
    }
    var dpr = window.devicePixelRatio || 1;
    var canvases = el.querySelectorAll('canvas');
    var cssW = el.offsetWidth;
    var cssH = el.offsetHeight;
    var out = document.createElement('canvas');
    out.width = Math.round(cssW * dpr);
    out.height = Math.round(cssH * dpr);
    var ctx = out.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, cssW, cssH);
    var pr = el.getBoundingClientRect();
    if (debug) {
        console.group('[dash-capture multi-canvas] debug');
        console.log('target el:', el.id || el.tagName, el);
        console.log('devicePixelRatio:', dpr);
        console.log('el.offsetWidth/Height (CSS):', cssW, 'x', cssH);
        console.log('el.getBoundingClientRect():', pr);
        console.log('output canvas (device px):', out.width, 'x', out.height);
        console.log('found', canvases.length, 'canvas elements');
    }
    var drawn = 0;
    canvases.forEach(function (cv, i) {
        var skip = (cv.style.display === 'none' || cv.offsetParent === null);
        var r = cv.getBoundingClientRect();
        if (debug) {
            console.log(
                '  canvas[' + i + '] backing=' + cv.width + 'x' + cv.height +
                ' rect=' + Math.round(r.width) + 'x' + Math.round(r.height) +
                ' @ (' + Math.round(r.left - pr.left) + ',' +
                Math.round(r.top - pr.top) + ')' +
                (skip ? ' SKIPPED' : ''),
                cv
            );
        }
        if (skip) return;
        ctx.drawImage(
            cv,
            0, 0, cv.width, cv.height,
            r.left - pr.left, r.top - pr.top, r.width, r.height
        );
        if (debug) {
            ctx.save();
            ctx.strokeStyle = 'red';
            ctx.lineWidth = 1;
            ctx.strokeRect(
                r.left - pr.left + 0.5, r.top - pr.top + 0.5,
                r.width - 1, r.height - 1
            );
            ctx.restore();
        }
        drawn++;
    });
    if (debug) {
        console.log('drew', drawn, 'canvases onto output');
    }
    if (window.html2canvas) {
        try {
            var overlay = await window.html2canvas(el, {
                backgroundColor: null,
                scale: dpr,
                useCORS: true,
                logging: !!debug,
                ignoreElements: function (n) {
                    return n.tagName === 'CANVAS';
                }
            });
            ctx.save();
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.drawImage(overlay, 0, 0);
            ctx.restore();
            if (debug) {
                console.log(
                    'html2canvas overlay (device px):',
                    overlay.width, 'x', overlay.height
                );
            }
        } catch (e) {
            if (debug) console.warn('html2canvas overlay failed:', e);
        }
    } else if (debug) {
        console.warn(
            '[dash-capture multi-canvas] html2canvas not loaded; ' +
            'skipping HTML overlay (titles / labels / legends).'
        );
    }
    if (debug) console.groupEnd();
    if (el._dcap_hidden) {
        el._dcap_hidden.forEach(function (h) {
            h.el.style.display = h.display;
        });
        delete el._dcap_hidden;
    }
    return out.toDataURL('image/' + fmt);
})"""


def multi_canvas_strategy(
    *,
    hide_selectors: list[str] | None = None,
    format: str = "png",
    debug: bool = False,
    settle_frames: int = 2,
    _params: Mapping | None = None,
) -> CaptureStrategy:
    """Strategy that composites every visible ``<canvas>`` under the target.

    Designed for chart libraries (dygraphs, custom canvas widgets) where
    the chart renders to several stacked canvases — plot, axes, range
    selector — and the built-in :func:`canvas_strategy` (which captures
    only the first canvas) can't reproduce the full output. This strategy
    walks every visible canvas, blits each at its CSS-pixel rect onto a
    single white-backed canvas at devicePixelRatio scale, then overlays
    the HTML layer (titles, axis labels, legends, annotations) via
    ``html2canvas``.

    The capture JS is :data:`MULTI_CANVAS_CAPTURE_JS`. Call sites that
    invoke the JS directly (e.g. a host component's own download button)
    can import the constant and pass ``hideSelectors`` at call time.

    Parameters
    ----------
    hide_selectors :
        CSS selectors for elements to temporarily hide before capture
        (e.g. ``[".dygraph-rangesel-fgcanvas", ...]`` for dygraphs'
        range selector). Restored to their original ``display`` value
        after capture. ``None`` = hide nothing.
    format :
        Output image format. ``"png"``, ``"jpeg"``, ``"webp"``. SVG is
        not supported (canvases only emit raster).
    debug :
        Console-log dimensions and per-canvas blits; outline destination
        rects in red on the output.
    settle_frames :
        rAF ticks to await between live-resize and capture, when the
        renderer declares ``capture_width`` / ``capture_height``.
    _params :
        Renderer signature for capture_width / capture_height auto-wire,
        mirroring :func:`html2canvas_strategy`. Passed by ``capture_element``
        when wiring the strategy.

    Returns
    -------
    CaptureStrategy
    """
    # Queue html2canvas — needed for the overlay pass.
    from dash_capture._html2canvas import ensure_html2canvas

    ensure_html2canvas([])

    params = _params or {}
    has_w = "capture_width" in params
    has_h = "capture_height" in params
    preprocess: str | None = None
    if has_w or has_h:
        preprocess = build_reflow_preprocess(has_w, has_h, settle_frames)

    # JSON-serialise the selector list for inlining into the JS.
    import json

    selectors_js = json.dumps(list(hide_selectors or []))
    debug_js = "true" if debug else "false"

    # Wrap the IIFE call in try/finally so the live-resize preprocess can
    # be cleaned up safely (the finally block is a no-op when no preprocess
    # ran — el._dcap_saved is undefined).
    capture = (
        f"try {{ return await {MULTI_CANVAS_CAPTURE_JS}"
        f"(el, '{format}', {selectors_js}, {debug_js}); }} "
        "finally { if (el._dcap_saved) { "
        "el.style.width = el._dcap_saved.w; "
        "el.style.height = el._dcap_saved.h; "
        "delete el._dcap_saved; } }"
    )

    return CaptureStrategy(
        preprocess=preprocess,
        capture=capture,
        format=format,
        _rebuild=lambda p: multi_canvas_strategy(
            hide_selectors=hide_selectors,
            format=format,
            debug=debug,
            settle_frames=settle_frames,
            _params=p,
        ),
    )


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
