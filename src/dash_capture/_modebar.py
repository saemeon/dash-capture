# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Inject custom buttons into Plotly modebars with Dash callback integration."""

from __future__ import annotations

from dataclasses import dataclass

import dash
from dash import Input, Output, html


@dataclass
class ModebarIcon:
    """SVG icon definition for a modebar button.

    Parameters
    ----------
    path : str
        SVG ``<path d="...">`` data. Ignored if *svg_content* is set.
    svg_content : str
        Raw SVG inner markup for complex icons (multiple paths, text, etc.).
    width, height : int
        ViewBox dimensions (default 1000 x 1000, matching Plotly icons).
    transform : str
        Optional SVG transform applied to the path.

    Examples
    --------
    >>> from dash_capture import ModebarIcon
    >>> icon = ModebarIcon(path="M500 0 L1000 1000 L0 1000 Z")
    """

    path: str = ""
    svg_content: str = ""
    width: int = 1000
    height: int = 1000
    transform: str = ""

    def to_svg_inner(self) -> str:
        """Return SVG inner markup."""
        if self.svg_content:
            return self.svg_content
        transform = f' transform="{self.transform}"' if self.transform else ""
        return f'<path fill="currentColor" d="{self.path}"{transform}/>'


_DEFAULT_LABEL = "\U0001f4f7"  # 📷


@dataclass
class ModebarButton:
    """Configuration for a modebar button.

    Parameters
    ----------
    icon : ModebarIcon, optional
        SVG icon. When set, rendered as SVG instead of a text label.
    label : str
        Text/emoji label. Defaults to a camera emoji when neither
        *label* nor *icon* is set.
    tooltip : str
        Hover tooltip text (default ``"Capture"``).

    Examples
    --------
    >>> from dash_capture import ModebarButton, capture_graph
    >>> capture_graph("my-graph", trigger=ModebarButton(tooltip="Export"))
    """

    icon: ModebarIcon | None = None
    label: str = ""
    tooltip: str = "Capture"


def _build_inject_js(
    graph_id: str,
    bridge_id: str,
    tooltip: str,
    *,
    icon: ModebarIcon | None = None,
    label: str = "",
) -> str:
    """Build JS that injects a button into the Plotly modebar."""
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
            var outer = document.getElementById(gid);
            if (!outer) return;
            var groups = outer.querySelectorAll('.modebar-group');
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
        var tries = 0;
        function attach() {{
            var outer = document.getElementById(gid);
            var gd = outer && outer.querySelector('.js-plotly-plot');
            if (!gd || typeof gd.on !== 'function') {{
                if (tries++ < 100) setTimeout(attach, 100);
                return;
            }}
            if (!gd._dcapAttached) gd._dcapAttached = {{}};
            if (gd._dcapAttached[bid] !== gd.on) {{
                gd._dcapAttached[bid] = gd.on;
                gd.on('plotly_afterplot', inject);
            }}
            inject();
        }}
        attach();
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

    Returns a hidden bridge ``html.Div`` whose ``n_clicks`` increments
    when the injected button is clicked.

    Parameters
    ----------
    graph_id : str
        The ``id`` of the ``dcc.Graph`` component.
    bridge_id : str
        Unique ID for the hidden bridge component. Use as
        ``Input(bridge_id, "n_clicks")`` in your callback.
    button : ModebarButton, optional
        Button configuration. When provided, *icon* and *tooltip*
        kwargs are ignored.
    icon : ModebarIcon, optional
        SVG icon to display.
    tooltip : str
        Hover tooltip text (default ``"Capture"``).

    Returns
    -------
    html.Div
        Hidden bridge component -- include in the layout.

    Examples
    --------
    >>> from dash_capture import add_modebar_button
    >>> bridge = add_modebar_button("my-graph", "export-btn", tooltip="Export")
    >>> app.layout = html.Div([graph, bridge])
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
