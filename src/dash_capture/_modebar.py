# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Inject custom buttons into Plotly modebars with Dash callback integration."""

from __future__ import annotations

import dash
from dash import Input, Output, html

from dash_capture._icons import SvgIcon
from dash_capture._trigger import CaptureButton

_DEFAULT_LABEL = "\U0001f4f7"  # 📷


def _build_inject_js(
    graph_id: str,
    bridge_id: str,
    tooltip: str,
    *,
    icon: SvgIcon | None = None,
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
    button: CaptureButton | None = None,
    icon: SvgIcon | None = None,
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
    button : CaptureButton, optional
        Button configuration. When provided, *icon* and *tooltip*
        kwargs are ignored.
    icon : SvgIcon, optional
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
