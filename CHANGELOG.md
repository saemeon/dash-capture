# Changelog

All notable changes to **dash-capture** are documented here.

The format is loosely based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor and patch bumps may both contain new features; we try
to keep breakages out of patch releases).

## Unreleased

### Added

- New public API **`multi_canvas_strategy(...)`** — a generic
  ``CaptureStrategy`` that walks every visible ``<canvas>`` under the
  target element, blits each at its CSS-pixel rect onto a single
  white-backed canvas at devicePixelRatio scale, and overlays the HTML
  layer (titles, axis labels, legends) via ``html2canvas``. Designed
  for chart libraries (dygraphs, custom canvas widgets) where the
  built-in [`canvas_strategy`](#canvas_strategy) is insufficient
  because it captures only the first canvas.
- New public API **`build_reflow_preprocess(has_width, has_height,
  settle_frames=2)`** — extracted from the html2canvas strategy. Use
  it from custom strategies that want the same target-size
  ``capture_width`` / ``capture_height`` live-resize behaviour without
  duplicating the JS.
- New public constant **`MULTI_CANVAS_CAPTURE_JS`** — the raw
  async-IIFE source string used by ``multi_canvas_strategy``. Exposed
  for callers that need to invoke the JS outside a ``CaptureStrategy``
  (e.g. a chart library's own download button). Signature:
  ``(el, fmt, hideSelectors, debug)``.
- **Bridge protocol** for custom triggers: ``capture_element(trigger=...)``
  now accepts any object exposing ``.bridge`` (a hidden Dash component
  with ``n_clicks``) and ``.open_input`` (an ``Input`` for the wizard
  to listen on). Used by ``dygraphs.dash.DyModebarButton`` to inject
  custom buttons into the dygraphs modebar with the same UX as the
  existing plotly ``ModebarButton``. Concrete implementations stay in
  the chart library; dash-capture only knows the protocol.

### Fixed

- **Snapshot caching is now correct.** When ``capture_resolver`` was
  in use, the cache was effectively a no-op — the JS capture re-fired
  on every form change because both the cache-check callback and the
  JS callback shared the same trigger. Reworked the wiring so the JS
  capture only fires on actual cache misses (via a new internal
  ``cache_miss`` store), and split-output 500 errors caused by missing
  ``allow_duplicate=True`` on the snapshot-cache store are gone.
- **Cache-poisoning regression fix.** When the user revisited a prior
  set of capture dimensions (e.g. resize 1200×600 → 800×400 → 1200×600),
  the cache-update callback would file the cached hit's snapshot under
  the previous miss's key, corrupting that entry. Cache-check now
  explicitly clears the ``cache_miss`` store on hits so the
  cache-update callback bails cleanly.
- **Wizard close no longer triggers a phantom JS capture.** The
  ``arm_interval`` callback used to reset ``n_intervals=0`` on close,
  which propagated through ``Input(interval_id, "n_intervals")`` and
  woke up the entire capture chain — visible as a flicker on the live
  element every time the wizard closed. Now ``n_intervals`` is reset
  only on open.

### Tests

- Added ``TestCaptureResolverPath`` (4 tests) covering: construction
  smoke for both ``capture_element`` and ``capture_graph`` with a
  resolver, an architectural-invariant test that asserts the JS capture
  callback is wired to ``cache_miss`` and not ``resolved``, and a
  direct unit test of the cache-check function asserting it returns
  ``(snapshot, None)`` on hits (the cache-poisoning fix).
- Added an integration test
  (``test_capture_resolver_cache_skips_js_on_non_dimensional_change``)
  that wraps ``html2canvas`` with a counter and asserts non-dimensional
  field changes don't increment it.

### Internal

- ``_build_html2canvas_reflow_preprocess`` was renamed to the public
  ``build_reflow_preprocess`` and exported. The old underscore-prefixed
  name was a private helper, so this is not a public-API break.
