# dash-capture

Browser-side capture pipeline for Dash components. Captures Plotly figures
and arbitrary DOM elements from the browser, delivers the result to Python
for post-processing, and provides download / clipboard export — no headless
browser required.

## High-level flow

```
user clicks trigger  →  JS captures element (Plotly.toImage / html2canvas)
                    →  base64 PNG flows into a dcc.Store (client-side)
                    →  Python renderer receives _snapshot_img() / _fig_data
                    →  renderer writes bytes to _target buffer
                    →  preview + download + clipboard, all from that buffer
```

The renderer is an ordinary Python function. Its type-hinted parameters
become auto-generated form fields in the wizard (via `dash_fn_form`).

## Module map

| File | Responsibility |
|---|---|
| [capture.py](src/dash_capture/capture.py) | Public API: `capture_graph`, `capture_element`, `capture_binding`, `renderer`, `WizardAction`, `FromPlotly`. Orchestrates everything. |
| [strategies.py](src/dash_capture/strategies.py) | `CaptureStrategy` protocol + `plotly_strategy` / `html2canvas_strategy` / `canvas_strategy`. Each strategy produces the JS that actually captures pixels in the browser. |
| [_wizard.py](src/dash_capture/_wizard.py) | Generic modal wizard (trigger button + overlay + dialog + close). Independent of capture concerns. |
| [_wizard_layout.py](src/dash_capture/_wizard_layout.py) | Pure DOM construction for the wizard body (config fields \| preview \| generate/download/copy row). |
| [_wizard_callbacks.py](src/dash_capture/_wizard_callbacks.py) | All wizard callback registration. One `_register_*` function per callback, assembled by `wire_wizard`. |
| [_modebar.py](src/dash_capture/_modebar.py) | Plotly-modebar button injection (see "Modebar injection" below — the fragile bit). |
| [_dropdown.py](src/dash_capture/_dropdown.py) | Generic dropdown (used for the wizard's `···` overflow menu). |
| [_html2canvas.py](src/dash_capture/_html2canvas.py) | Injects the vendored `html2canvas.min.js` into `index_string` when an html2canvas-based strategy is used. |
| [_ids.py](src/dash_capture/_ids.py) | `_new_id(prefix)` — random-suffixed unique component IDs. |
| [pil.py](src/dash_capture/pil.py) | Built-in PIL renderers (`bordered`, `titled`, `watermarked`). Optional `[pil]` extra. |
| [assets/html2canvas.min.js](src/dash_capture/assets/html2canvas.min.js) | Vendored html2canvas, loaded only when a strategy needs it. |

## Capture data flow

There are two flow variants selected by the renderer's signature:

- **has_snapshot** — renderer takes `_snapshot_img`. JS captures pixels →
  base64 PNG → `snapshot_store` → preview callback calls renderer with a
  `_snapshot_img()` closure that returns the bytes.
- **has_fig_data** only — renderer takes `_fig_data` but not `_snapshot_img`.
  No browser-side capture; renderer gets the raw figure dict server-side and
  produces bytes (usually via matplotlib or similar).

`capture_resolver` is a server-side hook that transforms form values into
capture-opts (`capture_width`, `capture_height`, …) before the JS runs.
When used, the flow is two-step: server resolves → `resolved_store` →
JS captures with the resolved opts.

## Public API conventions

- `capture_graph(graph_id, renderer=..., trigger=..., ...)` — wizard for
  `dcc.Graph`. Default strategy is `plotly_strategy`.
- `capture_element(element_id, renderer=..., ...)` — wizard for any DOM
  element. Default strategy is `html2canvas_strategy`.
- `capture_binding(...)` — low-level: no wizard, just a JS-capture →
  `dcc.Store` binding.
- `@renderer` — decorator that validates magic-parameter names
  (`_target`, `_snapshot_img`, `_fig_data`) **at definition time**. Strongly
  recommended for custom renderers — a typo like `_snaphot_img` would
  silently break the wizard at runtime without it.

## ID scheme

Every wizard/binding gets a random `uid` (`secrets.token_hex(4)`) via
`_new_id`. All internal component IDs are `_dcap_<slot>_<uid>` (e.g.
`_dcap_wiz_close_<uid>`). This avoids collisions when multiple apps share a
process (common in tests).

## Modebar injection (the fragile part)

`capture_graph` accepts `trigger="modebar"` (the default) or a
`ModebarButton` / `ModebarIcon`. The implementation lives in
[_modebar.py](src/dash_capture/_modebar.py) and is the single most fragile
piece of the package — document it well before touching.

### Architecture

```
ModebarButton / ModebarIcon  ──►  add_modebar_button(graph_id, bridge_id, button)
                                          │
                                          ├── returns html.Div(id=bridge_id, n_clicks=0)   ← the "bridge"
                                          └── registers clientside_callback that
                                              injects a <a class="modebar-btn"> into
                                              the Plotly modebar whose onclick calls
                                              document.getElementById(bridge_id).click()

wizard opens on  Input(bridge_id, "n_clicks")
```

The `(graph_id, bridge_id, button) → html.Div` seam is the only contact
point between `_modebar.py` and the rest. Everything downstream only cares
that the bridge's `n_clicks` fires. So the injection mechanism can be
swapped without touching [capture.py](src/dash_capture/capture.py) (only
call site: line ~491) or the wizard machinery.

### Why DOM injection at all

Plotly's native API for this is `config.modeBarButtonsToAdd: [{name, icon, click}]`
— but `click` must be a JS function, and Dash serializes component props
as JSON, so a Python-defined handler can't be passed through. Every Dash
project that wants a custom modebar button ends up with some variant of
this bridge pattern.

### Current mechanism: `plotly_afterplot`

The clientside callback is triggered on `Input(graph_id, "figure")`. It:

1. Locates the real plotly div: `outer.querySelector('.js-plotly-plot')`
   (the outer `<div id=graph_id>` is a Dash wrapper; the plotly event
   system lives on the inner `.js-plotly-plot` — both are stable public
   contracts).
2. Retries briefly via `setTimeout` until `gd.on` is a function (plotly has
   initialized the div).
3. Registers `gd.on('plotly_afterplot', inject)` — plotly's documented
   "render complete, modebar is built" event. Fires after every
   `newPlot` / `react` / `relayout` / `restyle` / responsive resize.
4. Also calls `inject()` once immediately, in case `afterplot` already
   fired before we subscribed.
5. Guards against duplicate listeners via `gd._dcapAttached[bridge_id]` —
   stores `gd.on` (the bound function reference) as the identity.
   `Plotly.purge` reassigns `gd.on` on re-init, so the guard auto-invalidates
   and we re-subscribe cleanly.

`inject()` itself is idempotent: re-queries `.modebar-group`, returns
early if a button with our `data-dcap-id` is already present, otherwise
appends a new `modebar-group` with our button.

### Known-bad trigger (for regression testing)

The exact code path that broke the old injector:

```js
var gd = document.querySelectorAll('.js-plotly-plot')[0];
Plotly.relayout(gd, 'modebar.orientation', 'v');
```

A modebar-specific relayout forces plotly's `manageModeBar()` to rebuild
the modebar from its own config registry — which doesn't include our
injected button, so it gets wiped. The old setInterval-based injector
had already self-terminated and never re-fired. The current
`plotly_afterplot` listener catches it and re-injects.

### History / alternatives considered

Earlier the injector used `setInterval` that self-terminated once the
button was found. That broke whenever plotly rebuilt the modebar without
the `figure` prop changing — confirmed trigger: any `Plotly.relayout`
on a modebar-specific config. A MutationObserver on the graph subtree
was tried as an intermediate fix but still raced with plotly's own
rebuilds.

The current `plotly_afterplot` approach is the officially-intended plotly
integration point for "render is done." It's the smallest possible
footprint that's still robust.

### Diagnostic block (paste in browser console when triaging)

```js
// Snapshot state of a given graph (index 0 = first .js-plotly-plot on page)
var gd = document.querySelectorAll('.js-plotly-plot')[0];
console.log({
    plotlyAlive: typeof gd.on === 'function' && !!gd._ev,
    modebarInDOM: !!gd.querySelector('.modebar'),
    modebarGroups: gd.querySelectorAll('.modebar-group').length,
    ourIcon: !!gd.querySelector('[data-dcap-id]'),
    allModebarBtns: Array.from(gd.querySelectorAll('.modebar-btn'))
        .map(b => b.getAttribute('data-title')),
    dcapAttached: gd._dcapAttached,
});
```

Symptom ladder:

| Observation | Likely cause |
|---|---|
| `plotlyAlive: true, ourIcon: false` | Modebar was rebuilt by `manageModeBar`; afterplot handler didn't re-inject → our bug to fix. |
| `plotlyAlive: false, dcapAttached` non-empty | Plotly was purged and not re-inited; `gd.on`-identity guard will recover on next figure update or manual re-init. |
| `ourIcon: true` but visually missing | Modebar opacity-fade on hover-leave. Not a bug — just hover the graph. |
| Error `dc[namespace][function_name] is not a function` | Stale browser session: server was restarted while tab was open; callback hashes don't match. Hard-refresh the tab. |

To reproduce the old setInterval bug on the old code:
`Plotly.relayout(gd, 'modebar.orientation', 'v')`.

A fully-native alternative exists — a custom Dash component (React wrapper
around `dcc.Graph`) that could pass a real `click` function into plotly's
`modeBarButtonsToAdd`. That would let plotly own the button's lifecycle
entirely, but requires a JS build toolchain this package doesn't currently
have. A monkey-patch of `Plotly.react` was also considered and rejected:
it replaces plotly globals for every graph in the app to smuggle function
handlers across the serialization boundary — more "fighting the system"
than using the public event.

## Wizard state

`_wizard.py` stores open/closed state in a `dcc.Store` (`data=False`). The
toggle is "last-button-wins": triggered by open → True, triggered by close
→ False. Visibility maps `store.data` onto `modal.style.display`.

A `dcc.Interval` with `max_intervals=1, interval=500, disabled=True` is
armed on wizard-open (see `_register_arm_interval`). It fires once, 500ms
after the wizard opens, which auto-generates the initial preview capture.
This is why the first preview appears on its own without clicking Generate.

**Re-open arming is via `max_intervals` bump, not `n_intervals` reset.**
The obvious-looking implementation — reset `n_intervals` to 0 on each
open — is wrong: it produces a 1→0 Input change that fires every
callback listening on `Input(interval_id, "n_intervals")` (the JS
capture chain in `_register_capture_direct`, the resolver chain in
`_register_capture_resolved`) *before* the interval ticks, then the
interval ticks 0→1 and fires them again — two captures per re-open.
Instead, `arm_interval` writes `max_intervals = n_intervals + 1` on
open, leaving `n_intervals` untouched. The next interval tick advances
N→N+1 and fires the chain exactly once. On close it returns
`dash.no_update` for both Outputs so the disabled→True transition
stays silent for downstream callbacks. Pinned by
`TestRegisterArmInterval` (unit) + the `test_regression_fixes.py` A1/A3
selenium pair.

Note: [_register_autogenerate_preview](src/dash_capture/_wizard_callbacks.py#L256-L298)
has no try/except around the renderer call, unlike its
`_register_preview_from_snapshot` and `_register_preview_from_figdata`
siblings. If autogenerate is on and the renderer raises on some field
combination, that callback will error server-side. Candidate for
symmetric error handling if "wizard won't close" issues ever resurface.

## Testing

- Unit tests: `uv run pytest tests/` (196 tests, fast).
- Integration tests (Selenium/Chrome, skipped on CI): `uv run pytest .tests/integration/`.
- Smoke test: `tests/test_smoke.py` — imports every public symbol.
- No tests exercise the modebar injector JS directly. If you touch
  [_modebar.py](src/dash_capture/_modebar.py), spin up
  [examples/modebar_demo.py](examples/modebar_demo.py) and verify in a
  real browser — ideally after backgrounding the tab for a few minutes.

## Example to reach for

- `examples/capture_demo.py` — full showcase of form field types, all
  `@renderer` variants, strategies, error display.
- `examples/corpframe_demo.py` — capture + corporate-frame export pipeline.
- `examples/mpl_renderer.py` — custom matplotlib-based renderer.
- `examples/table_capture_demo.py` — `capture_element` against a `dash_table.DataTable`.
- `examples/modebar_demo.py` — minimal repro harness for modebar-button
  behavior (default emoji + custom SVG icon variants).
- `examples/hbar_labels_repro.py` — disappearing-y-label repro for
  horizontal bar charts across capture sizes; used to attribute
  "Mode A vs Mode B" in the Plotly auto-tick discussion (see
  "Future improvements" below).

## Future improvements

Not blocking anything today, parked here so the context survives the
next time someone asks.

- **Offscreen-clone always, when `capture_width`/`capture_height` are
  present.** Today the offscreen-clone preprocess in
  [_build_plotly_preprocess](src/dash_capture/strategies.py) only
  runs when there are strip patches; without patches, `Plotly.toImage`
  is called directly on the live graph. That inherits the live DOM's
  tick decisions, which is fine most of the time but can't recover
  from edge cases where live and target dimensions differ enough that
  fresh layout would matter. Proposed change: also return a preprocess
  (offscreen clone + `Plotly.newPlot` at target dimensions) when
  ``"capture_width" in params or "capture_height" in params``, even
  with no strip patches. Cost: +100–200ms per capture. See
  `examples/hbar_labels_repro.py` for the test case.

- **More capture configuration hooks.** `capture_graph` currently
  exposes `strategy`, `preprocess`, `capture_resolver`, `actions`,
  `field_specs`, etc., but some concerns are still tightly wired:
  - Categorical-axis tick behavior (the hbar-labels case). If a user
    wants "always show every category label during capture regardless
    of target size", they have to mutate their figure. A future option
    could let a downstream composer (e.g. SNBGraph) inject
    `tickmode="linear"` on categorical axes *only inside the capture
    clone* — keeping the live figure unchanged while guaranteeing
    corporate-export fidelity. Shape TBD; likely a
    ``layout_override: Callable[[dict], dict]`` hook applied to the
    cloned layout in the offscreen-clone preprocess.
  - Font / margin / background-color overrides at capture time that
    don't bleed into the live chart, driven by the same hook above.
  - A hook for fully replacing the preprocess layout ("here's the
    figure I actually want to capture, regardless of what's on
    screen"). This is already achievable via a custom `strategy` +
    `preprocess` JS string, but the JS-string API is footgun-prone.
    A Python-side hook that constructs the modified layout as a dict
    would be friendlier.

  Status: not needed in production yet. The `hbar_labels_repro.py`
  example documents the "Mode A vs Mode B" distinction so future-you
  can quickly tell whether a reported label issue is fixable in
  dash-capture (Mode A, would benefit from the offscreen-clone
  change) or inherent to Plotly's auto-tick at small sizes (Mode B,
  needs a `layout_override` hook or figure-side fix).
