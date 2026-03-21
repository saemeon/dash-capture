# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""interact() — ipywidgets-style one-liner for Plotly Dash."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dash import Input, Output, State, callback, dcc, html

from dash_fn_interact._config_builder import Config, build_config


def interact(
    fn: Callable,
    *,
    _manual: bool = False,
    **kwargs: Any,
) -> html.Div:
    """Build a self-contained interactive panel from a typed callable.

    The Dash equivalent of ``ipywidgets.interact()``.  Introspects *fn*'s
    signature, renders a form, and registers a callback that calls *fn* with
    the current field values whenever they change.

    Parameters
    ----------
    fn :
        Callable whose parameters define the form fields.  It is also called
        with the resolved ``**kwargs`` to produce the output shown below the
        form.  Return a Dash component, a ``plotly.graph_objects.Figure``, or
        any value (rendered via ``repr``).
    _manual :
        ``False`` (default) — callback fires on every field change (live
        update).  ``True`` — an *Apply* button is added; callback fires on
        click only.
    **kwargs :
        Per-field shorthands passed directly to :func:`build_config` — same
        syntax as ``build_config`` keyword arguments (``Field``, tuples,
        ``range``, lists, etc.).

    Returns
    -------
    html.Div
        Panel containing the form, an optional *Apply* button, and an output
        area.  Embed directly in ``app.layout``.

    Notes
    -----
    ``config_id`` is derived from ``fn.__name__``.  Calling ``interact()``
    twice with the same function will trigger a duplicate-ID warning — use
    :func:`build_config` directly if you need two panels for the same function.

    Example::

        import dash
        from dash import html
        from dash_fn_interact import interact

        app = dash.Dash(__name__)

        def make_wave(amplitude: float = 1.0, freq: float = 1.0):
            import plotly.graph_objects as go
            import numpy as np
            t = np.linspace(0, 1, 300)
            y = amplitude * np.sin(2 * np.pi * freq * t)
            return go.Figure(go.Scatter(x=t, y=y))

        panel = interact(make_wave, amplitude=(0, 2, 0.01), freq=(0.5, 10, 0.5))
        app.layout = html.Div([panel])

        if __name__ == "__main__":
            app.run(debug=True)
    """
    config_id = fn.__name__
    output_id = f"_dft_interact_out_{config_id}"

    cfg: Config = build_config(config_id, fn, **kwargs)

    output_div = html.Div(id=output_id, style={"marginTop": "16px"})

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
            return _render(fn, cfg.build_kwargs(values))

    else:
        cfg_states: list[State] = object.__getattribute__(cfg, "states")
        inputs = [Input(s.component_id, s.component_property) for s in cfg_states]
        panel = html.Div([cfg, output_div])

        @callback(Output(output_id, "children"), *inputs)
        def _on_change(*values: Any) -> Any:
            return _render(fn, cfg.build_kwargs(values))

    return panel


def _render(fn: Callable, kwargs: dict) -> Any:
    """Call fn(**kwargs) and convert the result to Dash-renderable children."""
    try:
        result = fn(**kwargs)
    except Exception as exc:
        return html.Pre(
            f"Error: {exc}",
            style={"color": "#d9534f", "fontFamily": "monospace"},
        )

    if result is None:
        return None

    # Plotly Figure → dcc.Graph
    try:
        import plotly.graph_objects as go  # noqa: PLC0415

        if isinstance(result, go.Figure):
            return dcc.Graph(figure=result)
    except ImportError:
        pass

    # Dash component → as-is
    if hasattr(result, "_type"):
        return result

    # Anything else → repr
    return html.Pre(
        repr(result),
        style={"fontFamily": "monospace", "whiteSpace": "pre-wrap"},
    )
