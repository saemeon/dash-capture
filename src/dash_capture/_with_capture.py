# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Instance-based capture entry point: :func:`with_capture`.

Combines :func:`hover_toolbar`, :func:`icon_button`, and
:func:`capture_graph` / :func:`capture_element` into a single call that
returns a callback-transparent wrapper containing the element, toolbar,
and wizard. The user places one object in the layout.
"""

from __future__ import annotations

from typing import Any, TypeVar

from dash import dcc
from dash.development.base_component import Component

from dash_capture._hover_toolbar import hover_toolbar
from dash_capture._icons import SvgIcon, icon_button
from dash_capture._ids import _new_id

T = TypeVar("T", bound=Component)


def with_capture(
    inner: T,
    icon: SvgIcon,
    *,
    tooltip: str = "Export",
    display: str = "inline-block",
    # forwarded to capture_graph / capture_element
    renderer: Any = None,
    strategy: Any = None,
    preprocess: str | None = None,
    filename: str | Any = "capture.png",
    autogenerate: bool = True,
    persist: bool = True,
    styles: dict | None = None,
    class_names: dict | None = None,
    field_specs: dict | None = None,
    field_components: Any = "dcc",
    capture_resolver: Any = None,
    show_format: bool | None = None,
    wizard_header: str | Any = "Capture",
    actions: list | None = None,
) -> T:
    """Wrap *inner* with a capture wizard bundled inside a hover toolbar.

    Instance-based counterpart to :func:`capture_element` and
    :func:`capture_graph`. Takes the component directly (not a string id)
    and returns a :func:`dash_wrap.wrap` wrapper whose type, ``id``, and
    proxy props match *inner* — a drop-in replacement in the layout.

    Auto-detects strategy: ``plotly_strategy`` for ``dcc.Graph``,
    ``html2canvas_strategy`` for everything else.

    Parameters
    ----------
    inner : T
        Any Dash component with an ``id``.
    icon : SvgIcon
        SVG icon for the toolbar button.
    tooltip : str
        Button tooltip (default ``"Export"``).
    display : str
        CSS ``display`` for the outer wrapper (default ``"inline-block"``).
        Pass ``"block"`` for full-width elements.
    renderer, strategy, preprocess, filename, autogenerate, persist,
    styles, class_names, field_specs, field_components, capture_resolver,
    show_format, wizard_header, actions
        Forwarded verbatim to :func:`capture_graph` (for ``dcc.Graph``)
        or :func:`capture_element` (for everything else).

    Returns
    -------
    T
        A ``dash-wrap`` wrapper containing *inner*, the hover toolbar,
        and the capture wizard. Callbacks written against *inner* keep
        working unchanged.

    Examples
    --------
    One-liner — table with hover export button::

        >>> from dash_capture import with_capture, SvgIcon
        >>> icon = SvgIcon(path="M350 100 H650 V450 H800 L500 750 ...")
        >>> table = dash_table.DataTable(id="my-table", ...)
        >>> app.layout = html.Div([with_capture(table, icon, filename="table.png")])

    With a custom renderer::

        >>> from dash_capture.pil import titled
        >>> app.layout = html.Div([with_capture(table, icon, renderer=titled)])

    Full-width element::

        >>> app.layout = html.Div([with_capture(my_div, icon, display="block")])
    """
    # late import to avoid circular dependency (capture.py imports strategies,
    # which are independent — but capture imports from this package's public API)
    from dash_wrap import wrap

    from dash_capture.capture import capture_element, capture_graph

    btn = icon_button(icon, _new_id("with-cap-btn"), tooltip=tooltip)

    capture_kwargs: dict[str, Any] = dict(
        renderer=renderer,
        trigger=btn,
        strategy=strategy,
        preprocess=preprocess,
        filename=filename,
        autogenerate=autogenerate,
        persist=persist,
        styles=styles,
        class_names=class_names,
        field_specs=field_specs,
        field_components=field_components,
        capture_resolver=capture_resolver,
        show_format=show_format,
        wizard_header=wizard_header,
        actions=actions,
    )

    wizard = (
        capture_graph(inner, **capture_kwargs)
        if isinstance(inner, dcc.Graph)
        else capture_element(inner, **capture_kwargs)
    )

    # hover_toolbar wraps inner (element + toolbar).
    # outer wrap adds wizard as a sibling — nested wraps walk the __wrapped__
    # chain so id and proxy props resolve to the original inner component.
    with_toolbar = hover_toolbar(inner, [btn], display=display)
    return wrap(with_toolbar, children=[with_toolbar, wizard])
