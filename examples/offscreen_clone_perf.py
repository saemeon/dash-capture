# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Demo: html2canvas offscreen-clone perf fix.

Spins up a Dash app with:
  - A small dash_table.DataTable (the capture target — small enough that
    capturing *it alone* should be near-instant).
  - ~15,000 dummy DOM nodes elsewhere on the page (bulk).

Without the offscreen-clone preprocess, html2canvas would clone
``document.documentElement`` and walk all 15k nodes for every capture —
multi-second cost. With the preprocess, html2canvas only sees the
target subtree inside an offscreen wrapper, and capture is sub-second.

Run:
    uv run python dash-capture/examples/offscreen_clone_perf.py

Then open http://127.0.0.1:8050, click "Capture table", and watch the
"last capture: Nms" status line. Expect ~100-400ms even with 15k extra
nodes on the page.
"""

from __future__ import annotations

import dash
import pandas as pd
from dash import Input, Output, State, dash_table, dcc, html

from dash_capture import capture_element

BULK_NODES = 40_000

df = pd.DataFrame(
    {
        "Country": ["Switzerland", "Germany", "France", "Italy", "Spain"],
        "Population (M)": [8.7, 83.2, 67.4, 59.0, 47.6],
        "GDP/cap ($k)": [93.5, 51.2, 44.5, 38.2, 30.1],
    }
)

table = dash_table.DataTable(
    id="perf-table",
    columns=[{"name": c, "id": c} for c in df.columns],
    data=df.to_dict("records"),
    style_table={"width": "520px"},
    style_cell={"padding": "8px", "fontFamily": "system-ui, sans-serif"},
    style_header={"fontWeight": "bold", "background": "#eef"},
)


def passthrough(_target, _snapshot_img):
    _target.write(_snapshot_img())


app = dash.Dash(__name__)

# Inject the html2canvas capture wizard with a visible trigger button.
exporter = capture_element("perf-table", renderer=passthrough, trigger="Capture table")

# Build ~15k throwaway nodes. Variety of tagNames so style resolution
# actually has to walk them (a flat list of identical <span>s would be
# too easy on html2canvas's per-node style copy).
bulk_children = []
for i in range(BULK_NODES):
    tag = ("span", "i", "b", "em", "code")[i % 5]
    bulk_children.append(
        getattr(html, tag.capitalize())(
            f"n{i} ",
            className=f"bulk-node bulk-{i % 17}",
            **{"data-idx": str(i)},
        )
    )

app.layout = html.Div(
    style={"padding": "24px", "fontFamily": "system-ui, sans-serif"},
    children=[
        html.H1("html2canvas offscreen-clone perf demo"),
        html.P(
            f"This page has {BULK_NODES:,} extra DOM nodes injected at "
            "the bottom. Without the offscreen-clone preprocess, every "
            'capture would walk all of them. Click "Capture table" '
            "below — the status line shows how long the JS round-trip "
            "took."
        ),
        html.Div(
            style={
                "padding": "16px",
                "border": "1px solid #ccc",
                "borderRadius": "6px",
                "marginBottom": "16px",
                "background": "white",
            },
            children=[table, exporter],
        ),
        html.Div(id="perf-status", style={"marginBottom": "16px"}),
        dcc.Store(id="perf-prev-png"),
        html.Hr(),
        html.H3(f"Bulk filler ({BULK_NODES:,} nodes):"),
        html.Div(
            id="perf-bulk",
            style={
                "maxHeight": "300px",
                "overflow": "auto",
                "fontSize": "11px",
                "color": "#888",
                "lineHeight": "1.4",
            },
            children=bulk_children,
        ),
    ],
)

# Clientside callback: time how long it takes the capture-snapshot store to
# fill after we click the trigger. Uses the wizard's "snapshot store" by
# polling for an <img src="data:image/png..."> appearing in the wizard.
# Simpler than reaching into dash-capture's internal store IDs.
app.clientside_callback(
    """
    function(prev_src) {
        if (!prev_src) {
            window._dcap_perf = {clickTime: null, lastMs: null};
        }
        // Listen for trigger clicks once.
        if (!window._dcap_perf_wired) {
            window._dcap_perf_wired = true;
            document.addEventListener('click', function(e) {
                var btn = e.target.closest('button');
                if (btn && btn.textContent.trim() === 'Capture table') {
                    window._dcap_perf = window._dcap_perf || {};
                    window._dcap_perf.clickTime = performance.now();
                    window._dcap_perf.lastMs = null;
                }
            }, true);
            // MutationObserver on the body: when a new <img data:image/png>
            // shows up after the click, record the delta.
            var obs = new MutationObserver(function() {
                if (!window._dcap_perf || !window._dcap_perf.clickTime) return;
                var imgs = document.querySelectorAll('img[src^="data:image/png"]');
                if (!imgs.length) return;
                var ms = performance.now() - window._dcap_perf.clickTime;
                window._dcap_perf.lastMs = Math.round(ms);
                window._dcap_perf.clickTime = null;
            });
            obs.observe(document.body, {subtree: true, childList: true,
                attributes: true, attributeFilter: ['src']});
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("perf-prev-png", "data"),
    Input("perf-prev-png", "data"),
)

# Tick the status div every 500ms so it picks up the latest measurement
# from window._dcap_perf.lastMs (set by the MutationObserver above).
app.layout.children.insert(-1, dcc.Interval(id="perf-tick", interval=500))
app.clientside_callback(
    """
    function(n) {
        var p = window._dcap_perf || {};
        if (p.lastMs == null) {
            return 'last capture: (click the button above)';
        }
        var s = 'last capture: ' + p.lastMs + ' ms';
        if (p.lastMs < 1000) s += '  ✅  fast';
        else if (p.lastMs < 5000) s += '  ⚠️  slowish';
        else s += '  ❌  slow (offscreen-clone may be off)';
        return s;
    }
    """,
    Output("perf-status", "children"),
    Input("perf-tick", "n_intervals"),
)


if __name__ == "__main__":
    app.run(debug=True)
