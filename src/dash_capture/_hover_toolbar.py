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
from typing import Any, TypeVar

import dash
from dash import Input, Output, dcc, html
from dash.development.base_component import Component
from dash_wrap import wrap

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
    >>> from dash_capture import hover_toolbar, icon_button, SvgIcon, capture_element
    >>> icon = SvgIcon(path="M350 100 H650 V450 ...")
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
