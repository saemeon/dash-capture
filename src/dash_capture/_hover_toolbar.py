# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Hover-toolbar wrapper for arbitrary Dash elements.

Wraps any Dash component via :func:`dash_wrap.wrap`, preserving full
callback-identity transparency (proxy props auto-detected), and adds a
floating toolbar that appears on mouse hover.

The required CSS is injected into ``<head>`` once via a
``clientside_callback`` on a sentinel ``dcc.Store`` inside the wrapper.
No assets file, no ``index_string`` patching.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from typing import TypeVar
from urllib.parse import quote

import dash
from dash import Input, Output, dcc, html
from dash.development.base_component import Component
from dash_wrap import wrap

from dash_capture._modebar import ModebarIcon

T = TypeVar("T", bound=Component)

_CSS_ID = "dcap-hover-toolbar-css"
_CSS = ".dcap-hover-wrapper:hover .dcap-hover-toolbar { opacity: 1 !important; }"


def hover_toolbar(
    inner: T,
    buttons: Sequence[html.Button],
    *,
    display: str = "inline-block",
) -> T:
    """Wrap *inner* with a CSS hover-revealed toolbar.

    Uses :func:`dash_wrap.wrap` internally, so the returned object is
    fully callback-transparent — its type, ``id``, and proxy props are
    identical to *inner* from Dash's perspective. Callers can pass the
    return value wherever the original component is expected.

    The toolbar is revealed on ``:hover`` via a ``<style>`` tag injected
    into ``<head>`` once per page (idempotent across multiple wrappers).

    Parameters
    ----------
    inner : T
        Any Dash component with an ``id``.
    buttons : sequence of html.Button
        Toolbar buttons. Each must have a unique ``id`` and ``n_clicks``.
    display : str
        CSS ``display`` for the outer wrapper (default ``"inline-block"``).
        Pass ``"block"`` for full-width elements.

    Returns
    -------
    T
        A ``dash-wrap`` wrapper whose declared and runtime type matches
        *inner*. Callbacks written against *inner* keep working unchanged.

    Examples
    --------
    >>> from dash_capture import hover_toolbar, icon_button, ModebarIcon, capture_element
    >>> icon = ModebarIcon(path="M350 100 H650 V450 ...")
    >>> btn = icon_button(icon, "cap-btn", tooltip="Export")
    >>> table = dash_table.DataTable(id="my-table", ...)
    >>> wrapped = hover_toolbar(table, [btn])   # type: DataTable
    >>> wizard = capture_element("my-table", trigger=btn)
    """
    sentinel_id = f"_dcap-hover-css-{secrets.token_hex(4)}"

    dash.clientside_callback(
        f"""
        function() {{
            if (!document.getElementById('{_CSS_ID}')) {{
                var s = document.createElement('style');
                s.id = '{_CSS_ID}';
                s.textContent = '{_CSS}';
                document.head.appendChild(s);
            }}
            return window.dash_clientside.no_update;
        }}
        """,
        Output(sentinel_id, "data"),
        Input(sentinel_id, "data"),
    )

    toolbar = html.Div(
        className="dcap-hover-toolbar",
        children=list(buttons),
        style={
            "position": "absolute",
            "top": "6px",
            "right": "6px",
            "display": "flex",
            "gap": "4px",
            "opacity": "0",
            "transition": "opacity 0.15s",
            "zIndex": "10",
            "pointerEvents": "none",
        },
    )

    return wrap(
        inner,
        children=[dcc.Store(id=sentinel_id, data=0), inner, toolbar],
        className="dcap-hover-wrapper",
        style={"position": "relative", "display": display},
    )


def icon_button(
    icon: ModebarIcon,
    button_id: str,
    *,
    tooltip: str = "",
    height: int = 20,
) -> html.Button:
    """Render a :class:`~dash_capture.ModebarIcon` as a standalone Dash button.

    Mirrors the sizing used by the Plotly modebar injector: height is
    fixed, width computed from the icon's viewBox aspect ratio. The SVG
    is embedded as a data URI on ``html.Img`` — works on any Dash version.

    Parameters
    ----------
    icon : ModebarIcon
        The icon definition to render.
    button_id : str
        ``id`` of the resulting ``html.Button``.
    tooltip : str
        ``title`` attribute (hover tooltip).
    height : int
        Icon height in pixels (default 20, matching the Plotly modebar).

    Examples
    --------
    >>> from dash_capture import ModebarIcon, icon_button
    >>> icon = ModebarIcon(path="M500 0 L1000 1000 L0 1000 Z")
    >>> btn = icon_button(icon, "my-btn", tooltip="Export")
    """
    width = round(height * icon.width / icon.height)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {icon.width} {icon.height}" '
        f'width="{width}" height="{height}">'
        f"{icon.to_svg_inner()}</svg>"
    )
    return html.Button(
        id=button_id,
        n_clicks=0,
        title=tooltip,
        children=html.Img(
            src="data:image/svg+xml;utf8," + quote(svg),
            height=height,
            style={"display": "block"},
        ),
        style={
            "background": "rgba(255,255,255,0.85)",
            "border": "1px solid #ccc",
            "borderRadius": "4px",
            "padding": "4px 6px",
            "cursor": "pointer",
            "pointerEvents": "auto",
        },
    )
