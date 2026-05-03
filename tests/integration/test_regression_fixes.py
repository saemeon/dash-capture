# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Integration tests for regressions fixed in `_wizard.py`.

Each test pins a specific bug at the *behavior* level — the unit tests in
``tests/dash_capture/test_wizard.py`` cover the wiring side of the same
fixes. Both layers matter: the unit tests are fast and run on every CI
build; the selenium tests catch what static wiring assertions can't (e.g.
"clicking Open twice in a row only triggers one capture").

Run locally with:

    PATH="/opt/homebrew/bin:$PATH" \\
        uv run pytest tests/integration/test_regression_fixes.py -v
"""

from __future__ import annotations

import base64
import struct
import time

import dash
import plotly.graph_objects as go
from dash import dcc, html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from dash_capture import capture_graph

# ── shared helpers (mirrored from test_capture_integration.py) ───────────


def _make_figure():
    return go.Figure(
        data=go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode="markers"),
        layout={"title": "Test Chart", "width": 400, "height": 300},
    )


def _find_button(dash_duo, label):
    """Find a button by its rendered text, ignoring display state."""
    for b in dash_duo.driver.find_elements(By.TAG_NAME, "button"):
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


def _instrument_plotly_capture_counter(dash_duo):
    """Wrap ``Plotly.toImage`` so each call bumps ``window._dcap_captures``.

    Lets a test count how many real browser-side captures actually
    fired — the only reliable way to prove no spurious captures
    happened (Dash's own callback log doesn't separate "fired and
    bailed at guard" from "fired and ran the JS").
    """
    dash_duo.driver.execute_script(
        """
        if (!window._dcap_orig_to_image && window.Plotly) {
            window._dcap_captures = 0;
            window._dcap_orig_to_image = window.Plotly.toImage;
            window.Plotly.toImage = function() {
                window._dcap_captures += 1;
                return window._dcap_orig_to_image.apply(this, arguments);
            };
        }
        """
    )


def _capture_count(dash_duo) -> int:
    return int(dash_duo.driver.execute_script("return window._dcap_captures || 0;"))


# ── A1 — re-open fires capture exactly once ──────────────────────────────


def test_wizard_reopen_fires_capture_once(dash_duo):
    """Re-opening the wizard must fire exactly one capture.

    The bug this pins: ``_register_arm_interval`` previously reset
    ``n_intervals=0`` on open, which on re-open caused a 1→0 Input
    transition that fired downstream callbacks immediately *and* the
    interval ticked 0→1 right after — two fires per re-open. The fix
    bumps ``max_intervals`` instead, allowing exactly one more tick.
    """
    graph = dcc.Graph(id="rg-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(graph, renderer=passthrough, trigger="Open")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#rg-graph", timeout=10)
    time.sleep(1)  # give Plotly time to bind
    _instrument_plotly_capture_counter(dash_duo)

    # First open → expect exactly 1 capture.
    open_btn = _find_button(dash_duo, "Open")
    open_btn.click()
    _wait_for_png(dash_duo, timeout=45)
    time.sleep(0.5)
    after_first_open = _capture_count(dash_duo)
    assert after_first_open == 1, (
        f"First open must produce exactly 1 capture, got {after_first_open}."
    )

    # Close the wizard (✕ button).
    close_btn = _find_button(dash_duo, "✕")
    assert close_btn is not None, "Close button (✕) missing."
    close_btn.click()
    time.sleep(0.5)

    # Re-open → expect exactly 1 *additional* capture.
    open_btn.click()
    # Wait until the count actually increments — without this, a fast
    # machine could hit the assert before the new capture lands.
    WebDriverWait(dash_duo.driver, 30).until(
        lambda _d: _capture_count(dash_duo) > after_first_open
    )
    time.sleep(1.0)  # let any *spurious* second fire arrive too

    after_reopen = _capture_count(dash_duo)
    assert after_reopen == after_first_open + 1, (
        f"Re-open must add exactly 1 capture (total {after_first_open + 1}), "
        f"got {after_reopen}. Double-fire regression — check that "
        f"_register_arm_interval bumps max_intervals (not resets n_intervals)."
    )


# ── A2 — capture_width with no spec / no resolver opens cleanly ──────────


def test_capture_width_no_spec_no_resolver_opens_clean(dash_duo):
    """Declaring ``capture_width: int`` with no field_specs and no
    capture_resolver must open the wizard without errors.

    The bug this pins: ``capture_*`` params are excluded from
    auto-generated form fields, so the previous code's State lookup hit
    ``ID not found in layout`` at first open. The fix skips the param
    entirely when there's no spec — strategy uses current browser size.
    """
    fig = _make_figure()
    graph = dcc.Graph(id="ns-graph", figure=fig)

    def renderer_with_capture_width(
        _target,
        _snapshot_img,
        capture_width: int = 400,
        capture_height: int = 300,
    ):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(
        graph,
        renderer=renderer_with_capture_width,
        trigger="Open",
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#ns-graph", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Open").click()
    raw = _wait_for_png(dash_duo, timeout=45)

    # No errors should appear in the browser console.
    severe = [e for e in dash_duo.get_logs() if e.get("level") in ("SEVERE",)]
    assert not severe, f"Browser console produced severe errors:\n{severe}"

    # And the capture must have produced a valid PNG.
    assert raw[:4] == b"\x89PNG", f"Expected PNG header, got {raw[:4]!r}"


# ── A3 — closing the wizard does not trigger a capture ───────────────────


def test_close_does_not_trigger_capture(dash_duo):
    """Closing the wizard must not start a new JS capture.

    The bug this pins: an earlier implementation reset
    ``n_intervals``/``max_intervals`` on close, which fired downstream
    callbacks listening on the interval — the JS capture would briefly
    resize the live element on close and flicker the page. The current
    code returns ``dash.no_update`` for both Outputs on close.
    """
    graph = dcc.Graph(id="cl-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(graph, renderer=passthrough, trigger="Open")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#cl-graph", timeout=10)
    time.sleep(1)
    _instrument_plotly_capture_counter(dash_duo)

    # Open + wait for the auto-capture (count → 1).
    _find_button(dash_duo, "Open").click()
    _wait_for_png(dash_duo, timeout=45)
    time.sleep(0.5)
    pre_close = _capture_count(dash_duo)
    assert pre_close == 1, f"Expected exactly 1 capture before close, got {pre_close}."

    # Close.
    _find_button(dash_duo, "✕").click()
    # Wait significantly longer than the interval period so any
    # close-driven tick would have landed by now.
    time.sleep(1.5)

    post_close = _capture_count(dash_duo)
    assert post_close == pre_close, (
        f"Closing the wizard triggered an extra capture "
        f"({pre_close} → {post_close}). Check that arm_interval returns "
        f"dash.no_update for max_intervals on close."
    )


# ── B (Tier 1) — image structural assertions ─────────────────────────────


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Read width/height from a PNG IHDR chunk (bytes 16-23)."""
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    # IHDR chunk starts at byte 8: 4 byte length, 4 byte type, then
    # 4 byte width + 4 byte height (big-endian).
    width, height = struct.unpack(">II", png_bytes[16:24])
    return width, height


def test_png_output_has_valid_signature(dash_duo):
    """The default capture path must produce a real PNG (magic bytes)."""
    graph = dcc.Graph(id="sig-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(graph, renderer=passthrough, trigger="Open")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#sig-graph", timeout=10)
    time.sleep(1)
    _find_button(dash_duo, "Open").click()
    raw = _wait_for_png(dash_duo, timeout=45)

    assert raw[:8] == b"\x89PNG\r\n\x1a\n", (
        f"Output is not a valid PNG. First 8 bytes: {raw[:8]!r}"
    )


def test_png_dimensions_honor_capture_size(dash_duo):
    """When ``capture_width`` / ``capture_height`` are fixed, the output
    PNG has those exact pixel dimensions.

    Catches: strategy ignoring capture_* opts, or Plotly defaulting back
    to its layout dimensions.
    """
    from dash_fn_form._spec import fixed

    target_w, target_h = 600, 350

    fig = _make_figure()
    # Make the live figure intentionally a different size than the
    # capture target so we can see the override took effect.
    fig.update_layout(width=400, height=300)
    graph = dcc.Graph(id="dim-graph", figure=fig)

    def renderer(
        _target,
        _snapshot_img,
        capture_width: int = target_w,
        capture_height: int = target_h,
    ):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(
        graph,
        renderer=renderer,
        trigger="Open",
        field_specs={
            "capture_width": fixed(target_w),
            "capture_height": fixed(target_h),
        },
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#dim-graph", timeout=10)
    time.sleep(1)
    _find_button(dash_duo, "Open").click()
    raw = _wait_for_png(dash_duo, timeout=45)

    width, height = _png_dimensions(raw)
    assert (width, height) == (target_w, target_h), (
        f"Captured PNG dimensions {width}x{height} do not match "
        f"requested {target_w}x{target_h}."
    )


# Note: a strip_legend size-comparison test was considered (running two
# apps side-by-side and asserting strip_legend reduces file size) but
# dropped — running two ``dash_duo.start_server`` calls per test is not
# supported by the dash-testing fixture. A future test could split this
# across two parametrized cases sharing a baseline via a fixture.


# ── C — additional behavioral tests ──────────────────────────────────────


def _severe_logs(dash_duo) -> list:
    """All SEVERE-level browser console entries.

    Filters out the noisy ``Could not establish connection. Receiving
    end does not exist.`` line that browser extensions
    (e.g. Zotero) inject; it's environmental, not from our code.
    """
    return [
        e
        for e in dash_duo.driver.get_log("browser")
        if e["level"] == "SEVERE"
        and "Could not establish connection" not in e["message"]
    ]


def test_console_clean_on_basic_capture_graph_flow(dash_duo):
    """Open + auto-capture + close on a vanilla ``capture_graph`` produces
    no SEVERE browser console errors. Smoke-tests the JS pipeline against
    ReferenceErrors, ID-not-found errors, and SyntaxErrors all in one
    cheap flow.
    """
    graph = dcc.Graph(id="cc-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(graph, renderer=passthrough, trigger="Open")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#cc-graph", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Open").click()
    _wait_for_png(dash_duo, timeout=45)
    _find_button(dash_duo, "✕").click()
    time.sleep(0.5)

    severe = _severe_logs(dash_duo)
    assert not severe, (
        "Basic capture_graph flow produced severe browser console errors:\n"
        + "\n".join(e["message"] for e in severe)
    )


def test_console_clean_on_capture_width_no_spec_flow(dash_duo):
    """Same as above, but with the ``capture_*``-with-no-spec path. This
    is the flow that previously produced ``ID not found in layout`` —
    the test pins that the silent-skip fix really is silent.
    """
    graph = dcc.Graph(id="ccn-graph", figure=_make_figure())

    def renderer(_target, _snapshot_img, capture_width: int = 400):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exporter = capture_graph(graph, renderer=renderer, trigger="Open")
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#ccn-graph", timeout=10)
    time.sleep(1)

    _find_button(dash_duo, "Open").click()
    _wait_for_png(dash_duo, timeout=45)
    _find_button(dash_duo, "✕").click()
    time.sleep(0.5)

    severe = _severe_logs(dash_duo)
    assert not severe, (
        "capture_width-with-no-spec flow produced severe browser console "
        "errors:\n" + "\n".join(e["message"] for e in severe)
    )


def test_manual_generate_after_auto_fire_adds_exactly_one_capture(dash_duo):
    """Auto-fire (interval) → click Generate → wait. The total capture
    count must be exactly 2: one from the interval, one from Generate.

    The bug class this guards: any wiring change that causes Generate
    clicks to retrigger the interval (or vice versa) — same family as
    the original double-fire on re-open.
    """
    graph = dcc.Graph(id="mg-graph", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)

    # A renderer with at least one form field so the Generate button is
    # visible (it's hidden when there are no fields).
    def renderer_with_field(_target, _snapshot_img, title: str = "x"):
        _target.write(_snapshot_img())

    # autogenerate=False keeps the Generate button enabled. With the
    # default (autogenerate=True), Generate is disabled and field changes
    # trigger captures instead — a different code path.
    exporter = capture_graph(
        graph,
        renderer=renderer_with_field,
        trigger="Open",
        autogenerate=False,
    )
    app.layout = html.Div([graph, exporter])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#mg-graph", timeout=10)
    time.sleep(1)
    _instrument_plotly_capture_counter(dash_duo)

    _find_button(dash_duo, "Open").click()
    # Wait for the auto-capture (count → 1).
    WebDriverWait(dash_duo.driver, 30).until(lambda _d: _capture_count(dash_duo) >= 1)
    after_auto = _capture_count(dash_duo)
    assert after_auto == 1, f"Auto-fire produced {after_auto} captures, want 1."

    # Click Generate (count → 2).
    _find_button(dash_duo, "Generate").click()
    WebDriverWait(dash_duo.driver, 30).until(lambda _d: _capture_count(dash_duo) >= 2)
    # Wait long enough for any spurious follow-up tick to land.
    time.sleep(1.5)

    final = _capture_count(dash_duo)
    assert final == 2, (
        f"Manual Generate after auto-fire should produce exactly 2 captures "
        f"total, got {final}. A higher count means clicking Generate "
        f"re-triggered the interval (or another input)."
    )


def test_two_wizards_on_one_page_do_not_cross_fire(dash_duo):
    """Two ``capture_graph`` instances on one page must be isolated:
    opening wizard A fires only A's capture, never B's.

    The bug class this guards: a wiring mistake that uses a non-unique
    component ID or a shared store, causing B's clientside callback to
    listen to A's open store. The current code mints fresh UIDs via
    ``_new_id`` per wizard.
    """
    graph_a = dcc.Graph(id="dual-A", figure=_make_figure())
    graph_b = dcc.Graph(id="dual-B", figure=_make_figure())

    def passthrough(_target, _snapshot_img):
        _target.write(_snapshot_img())

    app = dash.Dash(__name__)
    exp_a = capture_graph(graph_a, renderer=passthrough, trigger="OpenA")
    exp_b = capture_graph(graph_b, renderer=passthrough, trigger="OpenB")
    app.layout = html.Div([graph_a, exp_a, graph_b, exp_b])

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#dual-A", timeout=10)
    dash_duo.wait_for_element("#dual-B", timeout=10)
    time.sleep(1)

    # Tag each capture with which graphDiv it ran against by wrapping
    # Plotly.toImage with a counter PER element id. Plotly.toImage
    # receives the graphDiv as its first arg.
    dash_duo.driver.execute_script(
        """
        window._dcap_per_graph = {};
        const orig = window.Plotly.toImage;
        window.Plotly.toImage = function(gd, opts) {
            const id = gd && gd.parentElement ? gd.parentElement.id : '?';
            window._dcap_per_graph[id] = (window._dcap_per_graph[id] || 0) + 1;
            return orig.apply(this, arguments);
        };
        """
    )

    # Open ONLY wizard A.
    _find_button(dash_duo, "OpenA").click()
    _wait_for_png(dash_duo, timeout=45)
    time.sleep(1.0)  # let any cross-firing settle

    counts = dash_duo.driver.execute_script("return window._dcap_per_graph || {};")
    a_count = counts.get("dual-A", 0)
    b_count = counts.get("dual-B", 0)
    assert a_count >= 1, f"Wizard A opened but no capture on graph A. counts={counts}"
    assert b_count == 0, (
        f"Opening wizard A spuriously triggered a capture on graph B. "
        f"counts={counts} — wizards are not isolated."
    )
