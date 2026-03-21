# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""interact() — ipywidgets-style one-liner for Plotly Dash."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash import Input, Output, State, callback, dcc, html

from dash_fn_interact._forms import FnForm
from dash_fn_interact._renderers import register_renderer, to_component


def interact(
    fn: Callable | None = None,
    *,
    _manual: bool = False,
    _loading: bool = True,
    _render: Callable[[Any], Any] | None = None,
    **kwargs: Any,
) -> html.Div | Callable:
    """Build a self-contained interactive panel from a typed callable.

    The Dash equivalent of ``ipywidgets.interact()``.  Introspects *fn*'s
    signature, renders a form, and registers a callback that calls *fn* with
    the current field values whenever they change.

    ``interact`` can be used as a plain function call **or** as a decorator.
    This allows you to define a function and interact with it in a single shot.
    As the examples below show, ``interact`` also works with functions that
    have multiple arguments.

    Parameters
    ----------
    fn :
        Callable whose parameters define the form fields.  It is also called
        with the resolved ``**kwargs`` to produce the output shown below the
        form.  Return a Dash component, a ``plotly.graph_objects.Figure``, or
        any value (rendered via ``repr``).

        When omitted, ``interact`` returns a decorator — useful for the
        ``@interact(...)`` form with per-field shorthands.
    _manual :
        ``False`` (default) — callback fires on every field change (live
        update).  ``True`` — an *Apply* button is added; callback fires on
        click only.
    _loading :
        ``True`` (default) — wraps the output area in ``dcc.Loading`` so a
        spinner is shown while the callback runs.  Set to ``False`` to
        disable (e.g. for very fast functions where the flash is distracting).
    _render :
        Optional converter applied to the return value of *fn* before it is
        displayed.  Receives the raw Python result and must return a Dash
        component.  Use this when *fn* returns a type the built-in converter
        doesn't handle (e.g. a ``pandas.DataFrame``, a custom object)::

            interact(
                get_data,
                _render=lambda df: dash_table.DataTable(
                    data=df.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in df.columns],
                ),
            )

        When ``None`` (default), the built-in converter is used:
        ``go.Figure`` → ``dcc.Graph``, Dash components → as-is,
        anything else → ``html.Pre(repr(...))``.
    **kwargs :
        Per-field shorthands passed directly to :func:`FnForm` — same
        syntax as ``FnForm`` keyword arguments (``Field``, tuples,
        ``range``, lists, etc.).

    Returns
    -------
    html.Div
        Panel containing the form, an optional *Apply* button, and an output
        area.  Embed directly in ``app.layout``.
    Callable
        When *fn* is omitted, returns a decorator that accepts the function.

    Notes
    -----
    ``config_id`` is derived from ``fn.__name__``.  Calling ``interact()``
    twice with the same function will trigger a duplicate-ID warning — use
    :func:`FnForm` directly if you need two panels for the same function.

    Examples
    --------
    Plain function call::

        panel = interact(make_wave, amplitude=(0, 2, 0.01))
        app.layout = html.Div([panel])

    No-argument decorator — interact is applied when the function is defined::

        @interact
        def make_wave(amplitude: float = 1.0, freq: float = 1.0):
            ...

        app.layout = html.Div([make_wave])   # make_wave is now the panel

    Decorator with per-field shorthands::

        @interact(amplitude=(0, 2, 0.01), freq=(0.5, 10, 0.5))
        def make_wave(amplitude: float = 1.0, freq: float = 1.0):
            ...

        app.layout = html.Div([make_wave])

    Custom renderer for a DataFrame-returning function::

        import pandas as pd
        from dash import dash_table

        def get_data(n: int = 10) -> pd.DataFrame:
            return pd.DataFrame({"x": range(n), "y": range(n)})

        panel = interact(
            get_data,
            _render=lambda df: dash_table.DataTable(
                data=df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in df.columns],
            ),
        )
    """
    if fn is None:
        # Called as @interact(...) with kwargs — return a decorator
        def decorator(f: Callable) -> html.Div:
            return interact(
                f, _manual=_manual, _loading=_loading, _render=_render, **kwargs
            )

        return decorator

    config_id = fn.__name__
    output_id = f"_dft_interact_out_{config_id}"

    cfg: FnForm = FnForm(config_id, fn, **kwargs)

    _inner = html.Div(id=output_id, style={"marginTop": "16px"})
    output_div = dcc.Loading(_inner, type="circle") if _loading else _inner

    if _manual:
        btn_id = f"_dft_interact_btn_{config_id}"
        panel = html.Div(
            [
                cfg,
                html.Button(
                    "Apply",
                    id=btn_id,
                    n_clicks=0,
                    style={
                        "marginTop": "8px",
                        "padding": "6px 16px",
                        "cursor": "pointer",
                    },
                ),
                output_div,
            ]
        )

        @callback(
            Output(output_id, "children"),
            Input(btn_id, "n_clicks"),
            *cfg.states,
            prevent_initial_call=True,
        )
        def _on_apply(_n: int, *values: Any) -> Any:
            try:
                result = fn(**cfg.build_kwargs(values))
            except Exception as exc:
                return html.Pre(
                    f"Error: {exc}",
                    style={"color": "#d9534f", "fontFamily": "monospace"},
                )
            return to_component(result, _render)

    else:
        cfg_states: list[State] = object.__getattribute__(cfg, "states")
        inputs = [Input(s.component_id, s.component_property) for s in cfg_states]
        panel = html.Div([cfg, output_div])

        @callback(Output(output_id, "children"), *inputs)
        def _on_change(*values: Any) -> Any:
            try:
                result = fn(**cfg.build_kwargs(values))
            except Exception as exc:
                return html.Pre(
                    f"Error: {exc}",
                    style={"color": "#d9534f", "fontFamily": "monospace"},
                )
            return to_component(result, _render)

    return panel
