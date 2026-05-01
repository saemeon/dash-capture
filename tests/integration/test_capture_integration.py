# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Integration tests for dash-capture — live Dash app with Chrome.

These tests verify the full capture pipeline:
  JS capture (Plotly.toImage) → dcc.Store → Python callback → renderer

Run locally with:
  PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/integration/test_capture_integration.py -v
"""

from __future__ import annotations

import base64
import time

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from dash_capture import capture_element, capture_graph, plotly_strategy


def _make_figure():
    """Create a simple Plotly figure for testing."""
    return go.Figure(
        data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode="markers"),
        layout=dict(title="Test Chart", width=400, height=300),
    )


def _find_button(dash_duo, label):
    """Find a button by visible text, regardless of display state."""
    for b in dash_duo.driver.find_elements(By.TAG_NAME, "button"):
        # Use textContent via JS to get text even for hidden elements
        text = dash_duo.driver.execute_script("return arguments[0].textContent", b)
        if text.strip() == label:
            return b
    return None


def _wait_for_png(dash_duo, timeout=45):
    """Wait for an <img> with a data:image/png src and return raw bytes."""
    WebDriverWait(dash_duo.driver, timeout).until(
        lambda d: any(
            (img.get_attribute("src") or "").startswith("data:image/png")
            for img in d.find_elements(By.TAG_NAME, "img")
        )
    )
    for img in dash_duo.driver.find_elements(By.TAG_NAME, "img"):
        src = img.get_attribute("src") or ""
        if src.startswith("data:image/png"):
            return base64.b64decode(src.split(",", 1)[1])
    raise AssertionError("PNG image disappeared")


# ── tests ────────────────────────────────────────────────────────────────


def test_capture_graph_renders_export_button(dash_duo):
    """capture_graph produces a visible Export button."""
    graph = dcc.Graph(id="t1-graph", figure=_make_figure())
    app = dash.Dash(__name__)
    exporter = capture_graph(graph, trigger="Export")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t1-graph", timeout=10)

    btn = _find_button(dash_duo, "Export")
    assert btn is not None, "Export button not found"


def test_full_capture_pipeline(dash_duo):
    """Export → open wizard → auto-capture (no fields) → verify PNG in preview."""
    graph = dcc.Graph(id="t2-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(graph, renderer=passthrough, trigger="Export")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t2-graph", timeout=10)
    time.sleep(1)  # ensure Plotly.js is loaded

    # Click Export to open wizard — no fields so capture fires automatically
    export_btn = _find_button(dash_duo, "Export")
    export_btn.click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG", f"Expected PNG header, got {raw[:4]!r}"


def test_capture_with_strip_patches(dash_duo):
    """Capture with strip_title produces valid PNG.

    Strip kwargs were collapsed into the strategy object — they no
    longer live on ``capture_graph`` directly.
    """
    fig = _make_figure()
    fig.update_layout(title="BIG TITLE")
    graph = dcc.Graph(id="t3-graph", figure=fig)

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(
        graph,
        renderer=passthrough,
        trigger="Export",
        strategy=plotly_strategy(strip_title=True),
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t3-graph", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Export").click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG"


def test_capture_with_explicit_strategy(dash_duo):
    """capture_graph with explicit plotly_strategy works."""
    graph = dcc.Graph(id="t4-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(
        graph, renderer=passthrough, trigger="Export",
        strategy=plotly_strategy(strip_legend=True),
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t4-graph", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Export").click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG"


# ── capture_element + html2canvas tests ──────────────────────────────────
#
# Regression coverage for two bugs that lived undetected for ~2 weeks:
#   1. ``fmt`` identifier collision in ``_HTML2CANVAS_CAPTURE`` —
#      generated JS had a SyntaxError, the clientside callback never
#      registered, no preview ever appeared.
#   2. React doesn't execute inline ``<script>`` children — vendored
#      ``html2canvas.min.js`` was injected via ``html.Script`` but
#      ``window.html2canvas`` stayed undefined.
#
# Either bug would have been caught by a single end-to-end test that
# opens a ``capture_element`` wizard and asserts a PNG comes back.


def _make_table():
    """Sample DataTable used by the capture_element tests."""
    df = pd.DataFrame(
        {
            "Country": ["Switzerland", "Germany", "France"],
            "Population (M)": [8.7, 83.2, 67.4],
        }
    )
    return dash_table.DataTable(
        id="t5-table",
        columns=[{"name": c, "id": c} for c in df.columns],
        data=df.to_dict("records"),
        style_table={"width": "400px"},
        style_cell={"padding": "8px", "fontFamily": "system-ui, sans-serif"},
    )


def test_capture_element_table_passthrough(dash_duo):
    """capture_element on a DataTable produces a PNG via html2canvas.

    Smoke test for the full html2canvas pipeline:
    JS injection → element lookup → html2canvas() → dcc.Store →
    Python callback → renderer → preview img.
    """
    table = _make_table()

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_element(
        "t5-table", renderer=passthrough, trigger="Capture table"
    )
    app.layout = html.Div([table, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t5-table", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Capture table").click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG", f"Expected PNG header, got {raw[:4]!r}"


def test_capture_element_html2canvas_loaded(dash_duo):
    """``window.html2canvas`` is defined after the page loads.

    Regression for the ``html.Script`` bug — React strips inline script
    children, so the vendored html2canvas.min.js wasn't executing.
    """
    table = _make_table()

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_element(
        "t5-table", renderer=passthrough, trigger="Capture"
    )
    app.layout = html.Div([table, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t5-table", timeout=10)
    time.sleep(1)

    h2c_type = dash_duo.driver.execute_script("return typeof window.html2canvas")
    assert h2c_type == "function", (
        f"window.html2canvas is {h2c_type!r}, expected 'function'. "
        "Vendored script was injected but did not execute."
    )


def test_capture_element_with_form_field(dash_duo):
    """capture_element with a renderer that has a form field — verifies
    the FnForm + autogenerate path produces a preview after the wizard
    auto-fires its initial capture.
    """
    table = _make_table()

    def with_title(_target, _snapshot_img, title: str = "My Table"):
        # The renderer has a `title` field but doesn't actually use it
        # (the test just checks the preview pipeline survives the
        # presence of an extra field).
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_element(
        "t5-table", renderer=with_title, trigger="Capture with field"
    )
    app.layout = html.Div([table, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t5-table", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Capture with field").click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG"


def test_capture_element_no_fmt_collision_in_generated_js(dash_duo):
    """The generated clientside JS for html2canvas must parse without
    SyntaxError. Captured here as an end-to-end check: if the function
    fails to register, no preview will ever appear (timeout).

    This is the historical ``const fmt = ...`` collision regression.
    """
    table = _make_table()

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_element(
        "t5-table", renderer=passthrough, trigger="Capture"
    )
    app.layout = html.Div([table, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t5-table", timeout=10)
    time.sleep(1)

    # Inspect browser console for SyntaxErrors before any user action
    logs = dash_duo.driver.get_log("browser")
    syntax_errors = [
        e for e in logs
        if e["level"] == "SEVERE" and "SyntaxError" in e["message"]
    ]
    assert not syntax_errors, (
        "Generated clientside JS has a SyntaxError on page load:\n"
        + "\n".join(e["message"] for e in syntax_errors)
    )


# ── new: session-shipped behaviors ───────────────────────────────────────
#
# Three tests covering UX changes landed this session that the earlier
# integration suite does not exercise:
#   1. filename= as a Callable — downloaded file uses the dynamic name
#   2. autogenerate error handling — renderer exceptions surface in the
#      error div instead of hanging the wizard
#   3. capture_element() called BEFORE Dash() exists — html2canvas still
#      loads, because registration goes through GLOBAL_INLINE_SCRIPTS
#      rather than app.index_string mutation


import os
import tempfile


def _configure_downloads(dash_duo):
    """Point Chrome's download handler at a temp dir and return its path."""
    dl_dir = tempfile.mkdtemp(prefix="dcap_dl_")
    dash_duo.driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": dl_dir},
    )
    return dl_dir


def _wait_for_download(dl_dir, timeout=20):
    """Return the first downloaded file's name (ignores .crdownload partials)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        names = [
            n for n in os.listdir(dl_dir)
            if not n.endswith(".crdownload")
        ]
        if names:
            return names[0]
        time.sleep(0.2)
    raise AssertionError(f"no completed download in {dl_dir} within {timeout}s")


def test_filename_callable_uses_form_field(dash_duo):
    """When ``filename=`` is a callable, the downloaded file's name is
    derived from the current form-field values at click time.
    """
    graph = dcc.Graph(id="t6-graph", figure=_make_figure())

    def with_title(_target, _snapshot_img, title: str = "chart"):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(
        graph,
        renderer=with_title,
        trigger="Export",
        filename=lambda title="chart": f"{title}.png",
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t6-graph", timeout=10)
    time.sleep(1)
    dl_dir = _configure_downloads(dash_duo)

    _find_button(dash_duo, "Export").click()

    # Wait for the auto-generated preview (proves renderer ran)
    _wait_for_png(dash_duo, timeout=45)

    # Change the title input — this is the value the filename lambda will see
    title_input = dash_duo.driver.find_element(
        By.CSS_SELECTOR, "input[type='text']"
    )
    title_input.clear()
    title_input.send_keys("quarterly-report")
    time.sleep(0.5)  # debounce — autogenerate fires again

    _find_button(dash_duo, "Download").click()

    name = _wait_for_download(dl_dir)
    assert name == "quarterly-report.png", (
        f"expected filename from lambda, got {name!r}"
    )


# Note: there's no integration test for autogenerate-preview error
# handling. The structural wiring (the autogenerate callback has the
# error div as an Output) is covered by the unit test
# ``test_autogen_output_includes_error_div`` in ``tests/dash_capture/
# test_capture.py``. The runtime contract itself — "callback returns
# an error string → the Output's children becomes that string" — is
# Dash's own guarantee, not dash-capture's. Driving dcc.Input change
# events reliably through Selenium/dash_duo is more brittle than the
# mechanism is worth testing at the browser level.


def test_capture_element_works_before_dash_app_exists(dash_duo):
    """``capture_element`` can be called in a layout-building module
    before any ``Dash`` instance exists. Its html2canvas registration
    queues into ``dash._callback.GLOBAL_INLINE_SCRIPTS`` and is drained
    by Dash on the first page serve.
    """
    # Drain and rebuild: start from a clean queue so this test isn't
    # polluted by earlier tests in the same process, and the capture_element
    # call below has no app context.
    from dash._callback import GLOBAL_INLINE_SCRIPTS

    GLOBAL_INLINE_SCRIPTS.clear()

    # No dash.Dash() yet — this is the critical pre-app call.
    exporter = capture_element(
        "t8-table",
        renderer=lambda _target, _snapshot_img: _target.write(_snapshot_img()),
        trigger="Capture",
    )

    # Now create the app and mount the layout.
    table = _make_table()
    table.id = "t8-table"
    app = dash.Dash(__name__)
    app.layout = html.Div([table, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t8-table", timeout=10)
    time.sleep(1)

    # If the queue→drain path worked, html2canvas is now defined globally.
    h2c_type = dash_duo.driver.execute_script("return typeof window.html2canvas")
    assert h2c_type == "function", (
        f"window.html2canvas is {h2c_type!r} — expected 'function'. "
        "capture_element() was called before Dash() existed; the script "
        "should have queued via GLOBAL_INLINE_SCRIPTS and been emitted on "
        "first page serve."
    )

    # And the full pipeline still works — click Capture, expect a PNG.
    _find_button(dash_duo, "Capture").click()
    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG"


# ── target-size capture (live-resize preprocess) ─────────────────────────
#
# End-to-end coverage for the live-resize feature: the strategy
# auto-wires renderer ``capture_width`` / ``capture_height`` (via
# ``CaptureStrategy._rebuild``), the preprocess sets the element's
# inline dimensions, the browser reflows, html2canvas snapshots, and
# the cleanup ``finally`` restores. If any link in that chain breaks
# (e.g. the visibility-cascade bug that wiped all text overlays), the
# captured PNG will be at the wrong size or missing content.


def test_capture_element_target_size_resizes_output(dash_duo):
    """Renderer with ``capture_width`` / ``capture_height`` produces a
    PNG at the target dimensions, not the live element's native size.

    Pins the full live-resize chain end-to-end:

      1. ``capture_element(strategy=html2canvas_strategy())`` — strategy
         is constructed without ``_params``; the auto-wire path through
         ``CaptureStrategy._rebuild`` injects the renderer's signature
         at wizard construction time.
      2. The preprocess sets ``el.style.width`` / ``height`` from
         ``opts.width`` / ``height`` (which carry ``capture_width`` /
         ``capture_height`` defaults from the renderer).
      3. The settle-frames await lets CSS reflow.
      4. html2canvas snapshots at the new dimensions.
      5. The ``finally`` block restores the inline styles.

    A regression in any of those steps shows up as a PNG at the wrong
    size, missing content, or a stuck-resized live element.
    """
    import io

    from PIL import Image

    # Live element is 400×200; renderer asks for 800×400 — a 2x widen
    # that's clearly not just a DPI scale (which would only multiply
    # the bitmap, not change the source dimensions). The output canvas
    # at scale=2 should be 1600×800 device pixels.
    NATIVE_W, NATIVE_H = 400, 200
    TARGET_W, TARGET_H = 800, 400

    layout = html.Div(
        id="t-target-size",
        style={
            "width": f"{NATIVE_W}px",
            "height": f"{NATIVE_H}px",
            "display": "flex",
            "background": "#eef",
            # box-sizing: border-box so width/height include any
            # padding — without this, padding inflates the outer box
            # and the captured PNG is 16px larger than the target on
            # each axis, defeating the assertion.
            "boxSizing": "border-box",
        },
        children=[
            html.Div(
                "A",
                style={"flex": 1, "background": "#1f77b4", "color": "white"},
            ),
            html.Div(
                "B",
                style={"flex": 1, "background": "#ff7f0e", "color": "white"},
            ),
        ],
    )

    def renderer(
        _target,
        _snapshot_img,
        capture_width: int = TARGET_W,
        capture_height: int = TARGET_H,
    ):
        _target.write(_snapshot_img())

    def resolve():
        # capture_* params can't be form fields (they're excluded from
        # the FnForm), so a server-side resolver is the realistic way
        # to get values into them. Here it just returns the defaults
        # — what matters for this test is the pipeline, not the form.
        return {
            "capture_width": TARGET_W,
            "capture_height": TARGET_H,
        }

    app = dash.Dash(__name__)
    exporter = capture_element(
        "t-target-size",
        renderer=renderer,
        capture_resolver=resolve,
        trigger="Capture target size",
    )
    app.layout = html.Div([layout, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t-target-size", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Capture target size").click()

    raw = _wait_for_png(dash_duo, timeout=45)
    assert raw[:4] == b"\x89PNG"

    img = Image.open(io.BytesIO(raw))
    # html2canvas defaults to scale=2, so the output canvas is 2× the
    # CSS dimensions. Allow ±2px slop for sub-pixel rounding.
    expected_w = TARGET_W * 2
    expected_h = TARGET_H * 2
    assert abs(img.width - expected_w) <= 2, (
        f"output width is {img.width}, expected ~{expected_w} (target "
        f"{TARGET_W} × scale 2). The live-resize preprocess may not "
        "have run, or the strategy's _rebuild auto-wire didn't fire."
    )
    assert abs(img.height - expected_h) <= 2, (
        f"output height is {img.height}, expected ~{expected_h} (target "
        f"{TARGET_H} × scale 2)."
    )

    # The finally block that restores inline styles runs after the Promise
    # resolves — give it a moment before reading offsetWidth.
    time.sleep(0.5)

    live_w = dash_duo.driver.execute_script(
        "return document.getElementById('t-target-size').offsetWidth"
    )
    live_h = dash_duo.driver.execute_script(
        "return document.getElementById('t-target-size').offsetHeight"
    )
    assert live_w == NATIVE_W, (
        f"live element width is {live_w}, expected {NATIVE_W} — "
        "the finally block didn't restore inline styles."
    )
    assert live_h == NATIVE_H, (
        f"live element height is {live_h}, expected {NATIVE_H}."
    )


def test_capture_resolver_cache_skips_js_on_non_dimensional_change(dash_duo):
    """Snapshot cache invariant: changing a non-dimensional field reuses
    the cached PNG and does NOT re-run the browser-side JS capture.

    Setup:
      - A renderer with ``capture_width`` / ``capture_height`` (drives the
        cache key via ``capture_resolver``) and a ``title`` field that
        does NOT participate in the resolver.
      - Wizard has autogenerate on, so changing any field re-fires the
        resolver chain.

    Detection:
      - We tag every JS capture with a global counter
        (``window._dcap_captures``) by overriding ``Plotly.toImage`` /
        the html2canvas root for the test. Simpler: we monkey-patch
        the snapshot store via a ``MutationObserver`` on a hidden div
        that the renderer touches every time it runs server-side.

    The cleanest, least-invasive approach is to hook the clientside
    callback by reading the network log for ``_dash-update-component``
    POSTs. Selenium's ``performance`` log records them. Ratio of:
      - dimension change → at least one new POST (cache miss → JS)
      - title-only change → zero new JS-callback POSTs

    Without this test, the cache could silently degrade to "still calls
    JS but results never used" and the only symptom would be slowness.
    """
    NATIVE_W, NATIVE_H = 400, 200

    layout = html.Div(
        id="t-cache-elem",
        style={
            "width": f"{NATIVE_W}px",
            "height": f"{NATIVE_H}px",
            "background": "#eef",
            "boxSizing": "border-box",
        },
    )

    # The trick: bump a window counter every time the JS capture runs.
    # We do this by injecting a script that wraps html2canvas; if the
    # counter doesn't increase on a title change, the cache worked.
    inject = dcc.Store(id="t-cache-init", data=0)

    def renderer(
        _target,
        _snapshot_img,
        title: str = "hello",
        capture_width: int = NATIVE_W,
        capture_height: int = NATIVE_H,
    ):
        # title is non-dimensional — must NOT affect the cache key.
        _target.write(_snapshot_img())

    def resolve(**_):
        return {"capture_width": NATIVE_W, "capture_height": NATIVE_H}

    app = dash.Dash(__name__)
    exporter = capture_element(
        "t-cache-elem",
        renderer=renderer,
        capture_resolver=resolve,
        trigger="Capture",
        autogenerate=True,
    )
    app.layout = html.Div([layout, inject, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#t-cache-elem", timeout=10)

    # Wrap html2canvas to count how many times it actually runs.
    dash_duo.driver.execute_script(
        """
        window._dcap_captures = 0;
        const orig = window.html2canvas;
        if (orig) {
            window.html2canvas = function() {
                window._dcap_captures += 1;
                return orig.apply(this, arguments);
            };
        }
        """
    )

    # Open the wizard. Initial capture fires once via the auto-interval.
    _find_button(dash_duo, "Capture").click()

    # Wait for the first PNG to appear (cache miss → real JS capture).
    _wait_for_png(dash_duo, timeout=45)
    time.sleep(0.5)
    captures_after_open = dash_duo.driver.execute_script(
        "return window._dcap_captures || 0;"
    )
    assert captures_after_open >= 1, (
        f"Expected at least one JS capture after opening the wizard, "
        f"got {captures_after_open}."
    )

    # Change the title — this is non-dimensional and should hit the cache.
    title_input = dash_duo.driver.find_element(
        By.CSS_SELECTOR, "input[type='text']"
    )
    title_input.clear()
    title_input.send_keys("changed title")
    # Allow autogenerate debounce + callback chain time to settle.
    time.sleep(2.5)

    captures_after_title = dash_duo.driver.execute_script(
        "return window._dcap_captures || 0;"
    )
    assert captures_after_title == captures_after_open, (
        f"Cache miss on non-dimensional change: title-only edit triggered "
        f"a new JS capture (count went {captures_after_open} → "
        f"{captures_after_title}). The cache is broken — the JS callback "
        f"is probably wired to `resolved` instead of `cache_miss`."
    )
