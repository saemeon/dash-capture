# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Public capture APIs: ``capture_graph``, ``capture_element``, ``capture_binding``."""

from __future__ import annotations

import contextlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import dash
from dash import Input, Output, dcc, html
from dash_fn_form import Field, FieldHook, FnForm, FromComponent

from dash_capture._ids import _new_id
from dash_capture._modebar import ModebarButton, ModebarIcon, add_modebar_button
from dash_capture._wizard import wire_wizard
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


def _resolve_show_format(show_format: bool | None, has_snapshot: bool) -> bool:
    """Resolve the ``show_format`` argument to a concrete bool.

    ``None`` means "auto": show the format dropdown iff the renderer
    actually produces an image (``has_snapshot=True``). Renderers that
    only consume ``_fig_data`` (no screenshot) get the dropdown hidden
    because the format selector is meaningless when no image is
    produced. Explicit ``True`` / ``False`` always overrides the auto
    behavior so users can force the dropdown either way.
    """
    if show_format is None:
        return has_snapshot
    return show_format


# ---------------------------------------------------------------------------
# Renderer protocol — magic param names
# ---------------------------------------------------------------------------

#: Underscore-prefixed parameter names a renderer is allowed to declare.
#: Anything else starting with ``_`` is rejected as a typo at wizard
#: construction time by :func:`_validate_renderer_signature`.
_KNOWN_MAGIC_PARAMS = frozenset({"_target", "_snapshot_img", "_fig_data"})


@dataclass(frozen=True, slots=True)
class _RendererMeta:
    """Pre-computed classification of a renderer's parameters.

    Built lazily by :func:`_renderer_meta` at wizard-construction time
    and cached on the renderer's ``__dcap_meta__`` attribute so that
    subsequent ``capture_graph`` / ``capture_element`` calls skip the
    ``inspect.signature`` + validation pass.
    """

    has_snapshot: bool
    has_fig_data: bool
    active_capture: tuple[str, ...]
    fields: tuple[str, ...]


def _classify_params(fn: Callable) -> _RendererMeta:
    """Walk a renderer's signature and classify each parameter.

    Returns a populated ``_RendererMeta``. Does not validate magic
    names — validation is a separate pass in
    :func:`_validate_renderer_signature`.
    """
    params = inspect.signature(fn).parameters
    has_snapshot = "_snapshot_img" in params
    has_fig_data = "_fig_data" in params
    active_capture = tuple(p for p in params if p.startswith("capture_"))
    magic_set = {"_target", "_snapshot_img", "_fig_data", *active_capture}
    fields = tuple(p for p in params if p not in magic_set)
    return _RendererMeta(
        has_snapshot=has_snapshot,
        has_fig_data=has_fig_data,
        active_capture=active_capture,
        fields=fields,
    )


def _validate_renderer_signature(fn: Callable) -> None:
    """Raise ``ValueError`` if ``fn``'s signature has an invalid magic param.

    Rules:

    * A ``_target`` parameter must be present.
    * Every underscore-prefixed parameter must be a known magic name
      (``_target``, ``_snapshot_img``, ``_fig_data``). Typos raise
      with a ``difflib``-based "did you mean ...?" hint.

    Called by :func:`_renderer_meta` at wizard-construction time, so
    every renderer is validated when it's first used.
    """
    import difflib

    params = inspect.signature(fn).parameters
    name = getattr(fn, "__name__", "<renderer>")

    if "_target" not in params:
        raise ValueError(
            f"Renderer {name!r} must declare a ``_target`` parameter "
            f"(file-like object the renderer writes its output to). "
            f"Got parameters: {list(params)}"
        )

    underscore = [p for p in params if p.startswith("_")]
    unknown = [p for p in underscore if p not in _KNOWN_MAGIC_PARAMS]
    if unknown:
        suggestions: list[str] = []
        for typo in unknown:
            close = difflib.get_close_matches(typo, _KNOWN_MAGIC_PARAMS, n=1)
            if close:
                suggestions.append(f"{typo} → {close[0]}")
        msg = (
            f"Renderer {name!r} has unknown magic parameter(s): {unknown}. "
            f"Allowed magic names: {sorted(_KNOWN_MAGIC_PARAMS)}."
        )
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        raise ValueError(msg)


def _renderer_meta(fn: Callable) -> _RendererMeta:
    """Return cached meta for ``fn``, computing and caching on first call.

    Validates the signature via :func:`_validate_renderer_signature` so
    typos in magic parameter names raise at wizard construction rather
    than producing a silently-broken wizard at runtime. The result is
    cached on ``fn.__dcap_meta__`` so subsequent calls are free.
    """
    cached = getattr(fn, "__dcap_meta__", None)
    if isinstance(cached, _RendererMeta):
        return cached
    _validate_renderer_signature(fn)
    meta = _classify_params(fn)
    # Some callables (e.g. bound methods on slotted classes) reject
    # attribute assignment; validation still runs, just not cached.
    with contextlib.suppress(AttributeError, TypeError):
        setattr(fn, "__dcap_meta__", meta)  # noqa: B010
    return meta


class _NullFnForm(html.Div):
    """Stand-in for ``FnForm`` when the renderer has zero user fields.

    The default :func:`capture_graph` / :func:`capture_element` call
    uses :func:`_default_renderer`, which has no form fields. Constructing
    a real :class:`FnForm` for that case is wasted work — it pulls in
    dash-fn-form's field-generation machinery, registers populate /
    restore callbacks, and produces an empty UI.

    This stub implements just the surface area that
    :func:`wire_wizard` and :func:`build_modal_body` need:

    * Inherits from :class:`dash.html.Div` so it can be placed
      directly in the wizard layout tree.
    * ``self.states = []`` — empty list drives the existing
      "no fields" branches in :func:`wire_wizard`
      (``if config.states ...`` already short-circuits the
      autogenerate-on-field-change callback).
    * No-op ``register_populate_callback`` /
      ``register_restore_callback`` — there are no fields to
      populate or reset.
    * ``build_kwargs`` returns ``{}`` — the renderer is called with
      no extra kwargs.

    Renderers with fields still go through the full FnForm path.
    """

    def __init__(self, config_id: str):
        super().__init__(id=config_id, children=[])
        self.states: list = []

    def register_populate_callback(self, _open_input) -> None:
        pass

    def register_restore_callback(self, _restore_input) -> None:
        pass

    def build_kwargs(self, _values) -> dict:
        return {}


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


@dataclass
class WizardConfig:
    """Bundle of arguments threaded through ``_make_wizard`` /
    ``wire_wizard``.

    Constructed by :func:`capture_graph` / :func:`capture_element` after
    they resolve their public defaults. Replaces the previous 16-argument
    positional / keyword threading that duplicated the arg list across
    three call sites — adding a new option now requires touching only
    this dataclass plus the public function signatures, instead of
    threading it through internal helpers.

    Internal API: not exported, not meant for users to construct
    directly. Used as the single argument carried through the wizard
    pipeline.
    """

    element_id: str
    renderer: Callable
    strategy: CaptureStrategy
    trigger: str | Any
    filename: str | Callable[..., str]
    preprocess: str | None = None
    autogenerate: bool = True
    persist: bool = True
    styles: dict | None = None
    class_names: dict | None = None
    field_specs: dict[str, Field | FieldHook] | None = None
    field_components: Any = "dcc"
    capture_resolver: Callable | None = None
    show_format: bool | None = None
    wizard_header: str | Any = "Capture"
    actions: list[WizardAction] | None = None


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


def _make_wizard(cfg: WizardConfig) -> html.Div:
    """Shared implementation for ``capture_graph`` and ``capture_element``.

    Takes a fully-resolved :class:`WizardConfig` and produces the
    rendered ``html.Div`` wizard. Steps:

    1. Apply ``preprocess`` to the strategy (if any).
    2. Validate and classify the renderer via :func:`_renderer_meta`
       (cached on ``fn.__dcap_meta__`` after the first call).
    3. Resolve ``show_format`` (auto → True/False based on has_snapshot).
    4. Merge ``field_specs`` with persistence defaults if requested.
    5. Mint per-wizard component IDs.
    6. Build the form config — :class:`_NullFnForm` short-circuit when
       there are no fields, otherwise a real :class:`FnForm`.
    7. If ``trigger == "modebar"``, build the modebar bridge.
    8. Hand off to :func:`wire_wizard` for layout + callback registration.
    9. Inject vendored ``html2canvas.min.js`` if the strategy uses it.
    """
    strategy = cfg.strategy

    # Validate + classify the renderer (cached on fn.__dcap_meta__
    # after the first call, so repeat capture_graph()s are free).
    meta = _renderer_meta(cfg.renderer)
    has_snapshot = meta.has_snapshot
    has_fig_data = meta.has_fig_data
    active_capture = list(meta.active_capture)
    exclude = ["_target", "_snapshot_img", "_fig_data", *active_capture]

    # ``params`` is still needed by ``wire_wizard`` (it's threaded into
    # ``build_capture_js`` for ``capture_*`` parameter routing).
    params = inspect.signature(cfg.renderer).parameters

    # Auto-wire renderer params into strategies that consume them
    # (plotly_strategy, html2canvas_strategy, dygraph_strategy). This
    # lets users write ``capture_element(strategy=dygraph_strategy())``
    # without manually passing ``_params=...``. The ``_rebuild`` closure
    # is set by the strategy factory; instances constructed by hand
    # via ``CaptureStrategy(...)`` skip this path.
    if strategy._rebuild is not None:
        strategy = strategy._rebuild(params)

    if cfg.preprocess is not None:
        strategy = CaptureStrategy(preprocess=cfg.preprocess, capture=strategy.capture)

    # Auto-disable the format dropdown for fig-data-only renderers — the
    # selector is meaningless when no image is produced.
    show_format = _resolve_show_format(cfg.show_format, has_snapshot)

    field_specs = cfg.field_specs
    if cfg.persist:
        merged_specs: dict[str, Field | FieldHook] = {
            name: Field(persist=True) for name in meta.fields
        }
        if field_specs:
            merged_specs.update(field_specs)
        field_specs = merged_specs

    styles = cfg.styles or {}
    class_names = cfg.class_names or {}

    uid = _new_id(cfg.element_id)
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
    if cfg.capture_resolver is not None:
        id_keys.append("resolved")
        id_keys.append("snapshot_cache")
        id_keys.append("cache_miss")
    ids = {k: f"_dcap_{k}_{uid}" for k in id_keys}

    # Short-circuit: when the renderer has zero user-visible fields and
    # the caller hasn't supplied custom field_specs, skip FnForm entirely
    # and use the lightweight _NullFnForm stub. This is the hot path for
    # the default passthrough wizard (capture_graph() / capture_element()
    # with no renderer override) and avoids invoking dash-fn-form's
    # field-generation machinery.
    config: html.Div
    if not meta.fields and not field_specs:
        config = _NullFnForm(ids["cfg"])
    else:
        config = FnForm(
            ids["cfg"],
            cfg.renderer,
            _styles=styles,
            _class_names=class_names,
            _field_specs=field_specs,
            _show_docstring=False,
            _exclude=exclude,
            _field_components=cfg.field_components,
        )

    # Modebar trigger — wire up a bridge button if the user opted into the
    # Plotly modebar entry-point, or if the user passed a custom trigger
    # implementing the bridge protocol (any object with ``.bridge`` and
    # ``.open_input`` attributes — e.g. dygraphs' ``DyModebarButton``).
    # Otherwise the trigger flows through as-is.
    trigger = cfg.trigger
    modebar_bridge = None
    if trigger == "modebar" or isinstance(trigger, ModebarButton | ModebarIcon):
        if isinstance(trigger, ModebarButton):
            mb = trigger
        elif isinstance(trigger, ModebarIcon):
            mb = ModebarButton(icon=trigger)
        else:
            mb = ModebarButton()
        bridge_id = f"_dcap_modebar_{uid}"
        modebar_bridge = add_modebar_button(cfg.element_id, bridge_id, button=mb)
        trigger = modebar_bridge
    elif hasattr(trigger, "bridge") and hasattr(trigger, "open_input"):
        # Bridge protocol: object owns its bridge component AND its open
        # Input. Used by chart libraries that want to inject a button into
        # their own modebar without dash-capture knowing about their DOM.
        modebar_bridge = trigger.bridge
        trigger = trigger.bridge

    wizard_div = wire_wizard(
        cfg=cfg,
        strategy=strategy,
        config=config,
        has_snapshot=has_snapshot,
        has_fig_data=has_fig_data,
        active_capture=active_capture,
        params=params,
        ids=ids,
        trigger=trigger,
        styles=styles,
        class_names=class_names,
        field_specs=field_specs,
        show_format=show_format,
    )

    if modebar_bridge is not None:
        wizard_div = html.Div(cast(list, [modebar_bridge, wizard_div]))

    # Inject vendored html2canvas.min.js into the app's index_string when
    # the strategy needs it. Driven by the strategy itself (not by which
    # public function was called), so capture_graph users who pass
    # ``strategy=html2canvas_strategy()`` get the script too. Previously
    # this lived in ``capture_element`` only — capture_graph + html2canvas
    # silently failed because the JS was never injected.
    if getattr(strategy, "capture", "") == _HTML2CANVAS_CAPTURE:
        from dash_capture._html2canvas import ensure_html2canvas

        return html.Div(ensure_html2canvas([wizard_div]))

    return wizard_div


def capture_graph(
    graph: str | dcc.Graph,
    renderer: Callable | None = None,
    trigger: str | Any = "modebar",
    strategy: CaptureStrategy | None = None,
    preprocess: str | None = None,
    filename: str | Callable[..., str] = "figure.png",
    autogenerate: bool = True,
    persist: bool = True,
    styles: dict | None = None,
    class_names: dict | None = None,
    field_specs: dict[str, Field | FieldHook] | None = None,
    field_components: Any = "dcc",
    capture_resolver: Callable | None = None,
    show_format: bool | None = None,
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
        with no extra fields and no third-party dependencies.

        Magic parameter names (``_target`` / ``_snapshot_img`` /
        ``_fig_data``) are validated when the wizard is constructed,
        so a typo like ``_snaphot_img`` raises :class:`ValueError`
        with a ``difflib``-based "did you mean ...?" hint. Built-in
        PIL renderers (``bordered`` / ``titled`` / ``watermarked``)
        are available in :mod:`dash_capture.pil` (requires the
        ``[pil]`` extra).
    trigger : str, Dash component, or ModebarButton
        String label, custom component, ``"modebar"``, or :class:`ModebarButton`.
    strategy : CaptureStrategy, optional
        Capture strategy. Defaults to :func:`~dash_capture.plotly_strategy`.
        Pass ``plotly_strategy(strip_title=True, strip_legend=True, ...)``
        to strip Plotly decorations before capture.
    preprocess : str, optional
        Custom JS preprocess code (browser-side, security-sensitive).
    filename : str or callable
        Download filename. A string is used verbatim (with the format
        extension patched in for non-PNG downloads). A callable
        receives the renderer's form-field values as keyword
        arguments and returns the filename, allowing dynamic names
        driven by wizard inputs. Default ``"figure.png"``.
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
    show_format : bool, optional
        Show the format dropdown. Default ``None`` means auto: shown
        when the renderer takes ``_snapshot_img`` (image output),
        hidden for ``_fig_data``-only renderers (no image, format is
        meaningless). Pass ``True`` / ``False`` to override.
    actions : list[WizardAction], optional
        Additional action buttons shown alongside Download and Copy.

    Returns
    -------
    html.Div

    Notes
    -----
    **Composition with ``dcc.Loading``.** The returned wizard has
    internal callbacks targeting the preview ``<img>``, snapshot
    ``dcc.Store``, and error div. If you place the wizard (or a
    component that bundles it with the captured graph) inside a
    ``dcc.Loading`` wrapper, those internal callbacks will also trigger
    the loading spinner on every capture click. To scope the spinner to
    only the graph's own updates, use Dash's ``target_components=``
    parameter (Dash 2.14+)::

        dcc.Loading(
            graph,
            target_components={"my-graph": "figure"},
        )

    This limits the spinner to updates of ``graph.figure`` specifically,
    ignoring the wizard's internal callbacks.

    Examples
    --------
    Default — passthrough, no fields, just Generate + Download::

        >>> from dash_capture import capture_graph
        >>> wizard = capture_graph("my-graph", trigger="Export")

    With strip patches via the strategy::

        >>> from dash_capture import capture_graph, plotly_strategy
        >>> wizard = capture_graph(
        ...     "my-graph",
        ...     strategy=plotly_strategy(strip_title=True, strip_legend=True),
        ... )

    With a built-in PIL renderer::

        >>> from dash_capture import capture_graph
        >>> from dash_capture.pil import titled
        >>> wizard = capture_graph("my-graph", renderer=titled)

    With a custom renderer::

        >>> from dash_capture import capture_graph
        >>>
        >>> def my_renderer(_target, _snapshot_img, dpi: int = 150):
        ...     _target.write(_snapshot_img())
        >>>
        >>> wizard = capture_graph("my-graph", renderer=my_renderer)
    """
    if renderer is None:
        renderer = _default_renderer

    graph_id = graph if isinstance(graph, str) else cast(Any, graph).id

    if strategy is None:
        # _params auto-wired in _make_wizard via strategy._rebuild
        strategy = plotly_strategy()

    return _make_wizard(
        WizardConfig(
            element_id=graph_id,
            renderer=renderer,
            strategy=strategy,
            trigger=trigger,
            filename=filename,
            preprocess=preprocess,
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
    )


def capture_element(
    component: str | Any,
    renderer: Callable | None = None,
    trigger: str | Any = "Capture",
    strategy: CaptureStrategy | None = None,
    preprocess: str | None = None,
    filename: str | Callable[..., str] = "capture.png",
    autogenerate: bool = True,
    persist: bool = True,
    styles: dict | None = None,
    class_names: dict | None = None,
    field_specs: dict[str, Field | FieldHook] | None = None,
    field_components: Any = "dcc",
    capture_resolver: Callable | None = None,
    show_format: bool | None = None,
    wizard_header: str | Any = "Capture",
    actions: list[WizardAction] | None = None,
) -> html.Div:
    """Capture wizard for any Dash component (html2canvas by default).

    Captures arbitrary DOM elements via the bundled
    ``html2canvas.min.js``, which is auto-injected into the app's
    ``index_string``. Works with ``dash_table.DataTable``, ``html.Div``,
    custom widgets, etc. — anything with an ``id``.

    Parameters
    ----------
    component : str or Dash component
        Any Dash component with an ``id``, or a string ID.
    renderer : callable, optional
        See :func:`capture_graph` for the protocol. Defaults to a
        passthrough that writes the captured bytes unchanged. Built-in
        PIL renderers (``bordered`` / ``titled`` / ``watermarked``)
        from :mod:`dash_capture.pil` work for both graphs and elements.
    trigger : str or Dash component
        String label or custom component with ``n_clicks``.
    strategy : CaptureStrategy, optional
        Defaults to :func:`~dash_capture.html2canvas_strategy`. Pass
        :func:`~dash_capture.canvas_strategy` for raw ``<canvas>``
        elements, or :func:`~dash_capture.plotly_strategy` to capture
        a Plotly graph through this entry point.
    preprocess : str, optional
        Custom JS preprocess code.
    filename : str or callable
        Download filename. See :func:`capture_graph` — a callable
        receives form-field values and returns the filename.
        Default ``"capture.png"``.
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
    show_format : bool, optional
        Show the format dropdown. Default ``None`` means auto: shown
        when the renderer takes ``_snapshot_img``, hidden for
        ``_fig_data``-only renderers. See :func:`capture_graph`.

    Returns
    -------
    html.Div

    Notes
    -----
    See :func:`capture_graph` for composition notes — in particular
    the interaction with ``dcc.Loading`` and the
    ``target_components=`` escape hatch.

    Examples
    --------
    Default — capture a DataTable to PNG::

        >>> from dash_capture import capture_element
        >>> wizard = capture_element("my-data-table", trigger="Screenshot")

    With a built-in PIL renderer::

        >>> from dash_capture import capture_element
        >>> from dash_capture.pil import titled
        >>> wizard = capture_element("my-data-table", renderer=titled)
    """
    if renderer is None:
        renderer = _default_renderer

    comp_id = component if isinstance(component, str) else cast(Any, component).id

    if strategy is None:
        # _params auto-wired in _make_wizard via strategy._rebuild
        strategy = html2canvas_strategy()

    return _make_wizard(
        WizardConfig(
            element_id=comp_id,
            renderer=renderer,
            strategy=strategy,
            trigger=trigger,
            filename=filename,
            preprocess=preprocess,
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
    )
