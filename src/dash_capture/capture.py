# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Public capture APIs: ``capture_graph``, ``capture_element``, ``capture_binding``."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import dash
from dash import Input, Output, dcc, html
from dash_fn_form import Field, FieldHook, FnForm, FromComponent

from dash_capture._ids import _new_id
from dash_capture._modebar import ModebarButton, ModebarIcon, add_modebar_button
from dash_capture._wizard_callbacks import wire_wizard
from dash_capture.strategies import (
    _HTML2CANVAS_CAPTURE,
    CaptureStrategy,
    build_capture_js,
    html2canvas_strategy,
    plotly_strategy,
)


class FromPlotly(FromComponent):
    """Pre-populate a form field from the live Plotly figure.

    Parameters
    ----------
    path : str
        Dot-separated path into the figure dict, e.g. ``"layout.title.text"``.
    graph : dcc.Graph
        The graph component whose figure to read from.

    Examples
    --------
    >>> from dash import dcc
    >>> from dash_capture import FromPlotly, capture_graph
    >>> graph = dcc.Graph(id="my-graph", figure=fig)
    >>> capture_graph(
    ...     graph,
    ...     field_specs={"title": FromPlotly("layout.title.text", graph)},
    ... )
    """

    def __init__(self, path: str, graph: dcc.Graph):
        super().__init__(graph, "figure")
        self.path = path

    def get_default(self, *state_values: Any) -> Any:
        figure = state_values[0] if state_values else {}
        return _get_nested(figure, self.path)


def _get_nested(data: Any, path: str) -> Any:
    for key in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(key)
        if data is None:
            return None
    return data


def _default_renderer(_target, _snapshot_img):
    """Default capture renderer: write captured bytes straight to the target.

    Used by :func:`capture_graph` and :func:`capture_element` when
    ``renderer`` is ``None``.  Has no extra parameters, so the wizard
    collapses to just *Generate* + *Download*.  No third-party
    dependencies — always works.
    """
    _target.write(_snapshot_img())


@dataclass
class CaptureBinding:
    """Low-level capture wiring: JS capture → ``dcc.Store``.

    Attributes
    ----------
    store : dcc.Store
        Component to place in your layout.
    store_id : str
        The store's component ID.
    element_id : str
        The captured element's DOM ID.
    """

    store: dcc.Store
    store_id: str
    element_id: str


@dataclass
class WizardAction:
    """Custom action button for the capture wizard.

    Placed alongside the built-in Download and Copy buttons.  The
    *callback* receives the captured data-URI and any extra-field values.

    Parameters
    ----------
    label : str
        Button text shown in the wizard (e.g. ``"Add to Report"``).
    callback : callable
        ``callback(data_uri: str, **extra_fields) -> Any``.
        Return value is currently ignored.
    icon : str, optional
        Reserved for future icon support.
    """

    label: str
    callback: Callable
    icon: str | None = None


def capture_binding(
    element: str | Any,
    strategy: CaptureStrategy | None = None,
    trigger: Input | None = None,
) -> CaptureBinding:
    """Create a low-level capture binding without wizard or form.

    Parameters
    ----------
    element : str or Dash component
        A Dash component with an ``id``, or a string ID.
    strategy : CaptureStrategy, optional
        Defaults to ``plotly_strategy()``.
    trigger : Input, optional
        Dash ``Input`` that triggers the capture.

    Returns
    -------
    CaptureBinding
    """
    el_id = element if isinstance(element, str) else cast(Any, element).id

    if strategy is None:
        strategy = plotly_strategy()

    uid = _new_id(el_id)
    store_id = f"_dcap_store_{uid}"
    store = dcc.Store(id=store_id)

    if trigger is not None:
        capture_js = build_capture_js(el_id, strategy, [], {})
        dash.clientside_callback(
            capture_js,
            Output(store_id, "data"),
            trigger,
            Input(f"_dcap_dummy_{uid}", "n_intervals"),
            prevent_initial_call=True,
        )

    return CaptureBinding(store=store, store_id=store_id, element_id=el_id)


def _make_wizard(
    element_id: str,
    renderer: Callable,
    strategy: CaptureStrategy,
    preprocess: str | None,
    trigger: str | Any,
    filename: str,
    autogenerate: bool,
    persist: bool,
    styles: dict | None,
    class_names: dict | None,
    field_specs: dict[str, Field | FieldHook] | None,
    field_components: Any,
    capture_resolver: Callable | None = None,
    show_format: bool = True,
    wizard_header: str | Any = "Capture",
    actions: list[WizardAction] | None = None,
) -> html.Div:
    """Shared implementation for ``capture_graph`` and ``capture_element``."""
    if preprocess is not None:
        strategy = CaptureStrategy(preprocess=preprocess, capture=strategy.capture)

    params = inspect.signature(renderer).parameters
    has_snapshot = "_snapshot_img" in params
    has_fig_data = "_fig_data" in params
    active_capture = [name for name in params if name.startswith("capture_")]
    exclude = ["_target", "_snapshot_img", "_fig_data", *active_capture]

    if persist:
        merged_specs: dict[str, Field | FieldHook] = {}
        for name in params:
            if name in exclude:
                continue
            merged_specs[name] = Field(persist=True)
        if field_specs:
            merged_specs.update(field_specs)
        field_specs = merged_specs

    _styles = styles or {}
    _class_names = class_names or {}

    uid = _new_id(element_id)
    id_keys = [
        "cfg",
        "wiz",
        "preview",
        "generate",
        "download",
        "copy",
        "error",
        "interval",
        "restore",
        "menu",
        "autogen",
        "snapshot",
        "format",
    ]
    if capture_resolver is not None:
        id_keys.append("resolved")
    ids = {k: f"_dcap_{k}_{uid}" for k in id_keys}

    config = FnForm(
        ids["cfg"],
        renderer,
        _styles=_styles,
        _class_names=_class_names,
        _field_specs=field_specs,
        _show_docstring=False,
        _exclude=exclude,
        _field_components=field_components,
    )

    # Modebar trigger
    modebar_bridge = None
    if trigger == "modebar" or isinstance(trigger, ModebarButton | ModebarIcon):
        if isinstance(trigger, ModebarButton):
            mb = trigger
        elif isinstance(trigger, ModebarIcon):
            mb = ModebarButton(icon=trigger)
        else:
            mb = ModebarButton()
        bridge_id = f"_dcap_modebar_{uid}"
        modebar_bridge = add_modebar_button(element_id, bridge_id, button=mb)
        trigger = modebar_bridge

    wizard_div = wire_wizard(
        element_id=element_id,
        strategy=strategy,
        renderer=renderer,
        config=config,
        has_snapshot=has_snapshot,
        has_fig_data=has_fig_data,
        active_capture=active_capture,
        params=params,
        ids=ids,
        trigger=trigger,
        filename=filename,
        autogenerate=autogenerate,
        styles=_styles,
        class_names=_class_names,
        field_specs=field_specs,
        capture_resolver=capture_resolver,
        show_format=show_format,
        wizard_header=wizard_header,
        actions=actions or [],
    )

    if modebar_bridge is not None:
        return html.Div([modebar_bridge, wizard_div])
    return wizard_div


def capture_graph(
    graph: str | dcc.Graph,
    renderer: Callable | None = None,
    trigger: str | Any = "modebar",
    strategy: CaptureStrategy | None = None,
    preprocess: str | None = None,
    filename: str = "figure.png",
    autogenerate: bool = True,
    persist: bool = True,
    styles: dict | None = None,
    class_names: dict | None = None,
    field_specs: dict[str, Field | FieldHook] | None = None,
    field_components: Any = "dcc",
    capture_resolver: Callable | None = None,
    show_format: bool = True,
    wizard_header: str | Any = "Capture",
    actions: list[WizardAction] | None = None,
) -> html.Div:
    """Capture wizard for a ``dcc.Graph``.

    Opens a wizard modal with live preview, auto-generated form fields
    from the renderer's type hints, and download/copy buttons.

    Parameters
    ----------
    graph : str or dcc.Graph
        The graph component or its string ``id``.
    renderer : callable, optional
        Function with ``(_target, _snapshot_img, **fields)`` signature.
        Defaults to a passthrough that writes the captured bytes
        unchanged — the wizard then shows just *Generate* + *Download*
        with no extra fields.
    trigger : str, Dash component, or ModebarButton
        String label, custom component, ``"modebar"``, or :class:`ModebarButton`.
    strategy : CaptureStrategy, optional
        Capture strategy. Defaults to ``plotly_strategy()``. Use
        ``plotly_strategy(strip_title=True, ...)`` to strip elements.
    preprocess : str, optional
        Custom JS preprocess code (browser-side, security-sensitive).
    filename : str
        Download filename (default ``"figure.png"``).
    autogenerate : bool
        Regenerate preview on field changes (default ``True``).
    persist : bool
        Persist field values across sessions (default ``True``).
    styles, class_names : dict, optional
        CSS overrides keyed by component.
    field_specs : dict, optional
        Per-field :class:`~dash_fn_form.Field` overrides.
    field_components : str or callable
        Component factory: ``"dcc"``, ``"dmc"``, ``"dbc"``, or callable.
    capture_resolver : callable, optional
        Server-side function receiving form values as kwargs, returning
        ``capture_*`` options (e.g. ``{"capture_width": 520}``).
    show_format : bool
        Show the format dropdown (default ``True``).
    actions : list[WizardAction], optional
        Additional action buttons shown alongside Download and Copy.

    Returns
    -------
    html.Div

    Examples
    --------
    >>> from dash_capture import capture_graph, plotly_strategy
    >>> wizard = capture_graph("my-graph", trigger="Export")
    >>> # With strip patches:
    >>> wizard = capture_graph(
    ...     "my-graph",
    ...     strategy=plotly_strategy(strip_title=True, strip_legend=True),
    ... )
    """
    if renderer is None:
        renderer = _default_renderer

    graph_id = graph if isinstance(graph, str) else cast(Any, graph).id

    if strategy is None:
        params = inspect.signature(renderer).parameters
        strategy = plotly_strategy(_params=params)

    return _make_wizard(
        graph_id,
        renderer,
        strategy,
        preprocess,
        trigger,
        filename,
        autogenerate,
        persist,
        styles,
        class_names,
        field_specs,
        field_components,
        capture_resolver=capture_resolver,
        show_format=show_format,
        wizard_header=wizard_header,
        actions=actions,
    )


def capture_element(
    component: str | Any,
    renderer: Callable | None = None,
    trigger: str | Any = "Capture",
    strategy: CaptureStrategy | None = None,
    preprocess: str | None = None,
    filename: str = "capture.png",
    autogenerate: bool = True,
    persist: bool = True,
    styles: dict | None = None,
    class_names: dict | None = None,
    field_specs: dict[str, Field | FieldHook] | None = None,
    field_components: Any = "dcc",
    capture_resolver: Callable | None = None,
    show_format: bool = True,
    wizard_header: str | Any = "Capture",
    actions: list[WizardAction] | None = None,
) -> html.Div:
    """Capture wizard for any Dash component (html2canvas by default).

    Parameters
    ----------
    component : str or Dash component
        Any Dash component with an ``id``, or a string ID.
    renderer : callable, optional
        See :func:`capture_graph` for the protocol.  Defaults to a
        passthrough that writes the captured bytes unchanged.
    trigger : str or Dash component
        String label or custom component with ``n_clicks``.
    strategy : CaptureStrategy, optional
        Defaults to ``html2canvas_strategy()``.
    preprocess : str, optional
        Custom JS preprocess code.
    filename : str
        Download filename (default ``"capture.png"``).
    autogenerate : bool
        Regenerate preview on field changes (default ``True``).
    persist : bool
        Persist field values across sessions (default ``True``).
    styles, class_names : dict, optional
        CSS overrides keyed by component.
    field_specs : dict, optional
        Per-field :class:`~dash_fn_form.Field` overrides.
    field_components : str or callable
        Component factory.
    capture_resolver : callable, optional
        See :func:`capture_graph`.
    show_format : bool
        Show the format dropdown (default ``True``).

    Returns
    -------
    html.Div

    Examples
    --------
    >>> from dash_capture import capture_element
    >>> wizard = capture_element("my-div", trigger="Screenshot")
    """
    if renderer is None:
        renderer = _default_renderer

    comp_id = component if isinstance(component, str) else cast(Any, component).id

    if strategy is None:
        strategy = html2canvas_strategy()

    wizard = _make_wizard(
        comp_id,
        renderer,
        strategy,
        preprocess,
        trigger,
        filename,
        autogenerate,
        persist,
        styles,
        class_names,
        field_specs,
        field_components,
        capture_resolver=capture_resolver,
        show_format=show_format,
        wizard_header=wizard_header,
        actions=actions,
    )

    if getattr(strategy, "capture", "") == _HTML2CANVAS_CAPTURE:
        from dash_capture._html2canvas import ensure_html2canvas

        return html.Div(ensure_html2canvas([wizard]))

    return wizard
