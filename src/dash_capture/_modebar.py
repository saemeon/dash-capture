# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Add custom buttons to Plotly modebars with Dash callback integration.

Generic mechanism — not capture-specific. Any button added via
:func:`add_modebar_button` returns a hidden bridge component whose
``n_clicks`` increments when the user clicks the injected modebar button.
Wire it to any Dash callback.

How it works:

1. A hidden ``html.Div`` (the *bridge*) with ``n_clicks=0`` is created.
2. A ``clientside_callback`` injects the button into the modebar DOM
   after the graph renders.
3. The injected button's ``onclick`` calls ``bridge.click()``, which
   Dash sees as an ``n_clicks`` increment.

Usage::

    from dash_capture import ModebarIcon, add_modebar_button

    bridge = add_modebar_button("my-graph", "my-btn", tooltip="Export")
    app.layout = html.Div([graph, bridge])

    @app.callback(Output(...), Input("my-btn", "n_clicks"))
    def on_click(n): ...
"""

from __future__ import annotations

from dataclasses import dataclass

import dash
from dash import Input, Output, html


@dataclass
class ModebarIcon:
    """SVG icon for a modebar button.

    For simple icons, provide ``path`` (a single SVG path).
    For complex icons (text + shapes), provide ``svg_content``
    (raw SVG inner markup).

    Parameters
    ----------
    path :
        SVG ``<path d="...">`` data. Ignored if ``svg_content`` is set.
    svg_content :
        Raw SVG inner markup (multiple paths, text, groups, etc.).
        When set, ``path`` and ``transform`` are ignored.
    width, height :
        ViewBox dimensions (default 1000×1000, matching Plotly's icons).
    transform :
        Optional SVG transform applied to the path.
    """

    path: str = ""
    svg_content: str = ""
    width: int = 1000
    height: int = 1000
    transform: str = ""

    def to_svg_inner(self) -> str:
        """Return the SVG inner markup for this icon."""
        if self.svg_content:
            return self.svg_content
        transform = f' transform="{self.transform}"' if self.transform else ""
        return f'<path fill="currentColor" d="{self.path}"{transform}/>'


_DEFAULT_LABEL = "\U0001f4f7"  # 📷


@dataclass
class ModebarButton:
    """Configuration for a modebar button.

    Pass as ``trigger`` to :func:`~dash_capture.capture_graph`, or use
    directly with :func:`add_modebar_button`::

        # With capture_graph
        capture_graph("my-graph", trigger=ModebarButton(tooltip="Export"))

        # Standalone
        bridge = add_modebar_button("my-graph", "btn-id",
                                     button=ModebarButton(icon=my_icon))
    """

    icon: ModebarIcon | None = None
    """SVG icon. When set, rendered as an SVG instead of a text label."""
    label: str = ""
    """Plain text/emoji label (e.g. ``"SNB📷"``). Defaults to 📷 when
    neither ``label`` nor ``icon`` is set."""
    tooltip: str = "Capture"
    """Hover tooltip text."""


def _build_inject_js(
    graph_id: str,
    bridge_id: str,
    tooltip: str,
    *,
    icon: ModebarIcon | None = None,
    label: str = "",
) -> str:
    """Build JS that injects a custom button into the Plotly modebar."""
    safe_gid = graph_id.replace("\\", "\\\\").replace("'", "\\'")
    safe_bid = bridge_id.replace("\\", "\\\\").replace("'", "\\'")

    effective_label = label or (None if icon else _DEFAULT_LABEL)
    if effective_label:
        safe_label = effective_label.replace("\\", "\\\\").replace("'", "\\'")
        inner_js = f"btn.textContent = '{safe_label}';"
        style_js = "btn.style.fontSize = '12px'; btn.style.lineHeight = '20px';"
    else:
        assert icon is not None  # guaranteed by effective_label logic
        svg_inner = icon.to_svg_inner().replace("'", "\\'").replace("\n", " ")
        inner_js = (
            f"var aspect = {icon.width} / {icon.height};"
            " var h = 20; var w = Math.round(h * aspect);"
            f" btn.innerHTML = '<svg viewBox=\"0 0 {icon.width} {icon.height}\"'"
            f" + ' width=\"' + w + '\" height=\"' + h + '\">'"
            f" + '{svg_inner}</svg>';"
        )
        style_js = ""

    return f"""
    function(figure) {{
        var gid = '{safe_gid}';
        var bid = '{safe_bid}';
        function inject() {{
            var el = document.getElementById(gid);
            if (!el) return;
            var groups = el.querySelectorAll('.modebar-group');
            if (!groups.length) return;
            var bar = groups[0].parentNode;
            if (bar.querySelector('[data-dcap-id="' + bid + '"]')) return;
            var newGroup = document.createElement('div');
            newGroup.className = 'modebar-group';
            var btn = document.createElement('a');
            btn.className = 'modebar-btn';
            btn.setAttribute('data-dcap-id', bid);
            btn.setAttribute('data-title', '{tooltip}');
            btn.style.cursor = 'pointer';
            {style_js}
            {inner_js}
            btn.onclick = function(e) {{
                e.preventDefault();
                document.getElementById(bid).click();
            }};
            newGroup.appendChild(btn);
            bar.appendChild(newGroup);
        }}
        var iv = setInterval(function() {{ inject();
            var el = document.getElementById(gid);
            if (el && el.querySelector('[data-dcap-id="' + bid + '"]')) clearInterval(iv);
        }}, 200);
        return window.dash_clientside.no_update;
    }}
    """


def add_modebar_button(
    graph_id: str,
    bridge_id: str,
    *,
    button: ModebarButton | None = None,
    icon: ModebarIcon | None = None,
    tooltip: str = "Capture",
) -> html.Div:
    """Add a custom button to a Plotly graph's modebar.

    Returns a hidden ``html.Div`` whose ``n_clicks`` increments when the
    user clicks the injected button. Wire it to any Dash callback::

        bridge = add_modebar_button("my-graph", "export-btn", tooltip="Export")
        app.layout = html.Div([graph, bridge])

        @app.callback(Output("result", "children"), Input("export-btn", "n_clicks"))
        def on_click(n):
            return f"Clicked {n} times"

    Parameters
    ----------
    graph_id :
        The ``id`` of the ``dcc.Graph`` component.
    bridge_id :
        Unique ID for the hidden bridge ``html.Div``. Use this ID as
        ``Input(bridge_id, "n_clicks")`` in your callback.
    button :
        A :class:`ModebarButton` with icon and tooltip.
        When provided, ``icon`` and ``tooltip`` kwargs are ignored.
    icon :
        SVG icon to display. When neither ``icon`` nor ``label`` is
        given, defaults to a 📷 emoji label.
    tooltip :
        Hover tooltip text for the button.

    Returns
    -------
    html.Div
        Hidden component — include in the layout.
    """
    label = ""
    if button is not None:
        icon = button.icon
        label = button.label
        tooltip = button.tooltip

    bridge = html.Div(id=bridge_id, n_clicks=0, style={"display": "none"})

    js = _build_inject_js(graph_id, bridge_id, tooltip, icon=icon, label=label)
    dash.clientside_callback(
        js,
        Output(bridge_id, "style"),  # dummy output
        Input(graph_id, "figure"),
    )

    return bridge
