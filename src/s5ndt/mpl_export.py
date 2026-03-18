# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

from __future__ import annotations

import base64
import inspect
import io
import types
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Literal, Union, get_args, get_origin, get_type_hints

import dash
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

plt.switch_backend("agg")


@dataclass
class _Field:
    name: str
    type: str  # "str"|"bool"|"date"|"datetime"|"int"|"float"|"list"|"tuple"|"literal"
    default: Any
    args: tuple = ()       # element types for list/tuple, values for literal
    optional: bool = False  # True when annotation is Optional[T] / T | None


def _snapshot_renderer(fig_data: dict, suptitle: str = "", title: str = ""):
    plotly_fig = go.Figure(fig_data)
    img_bytes = plotly_fig.to_image(format="png")
    img = plt.imread(io.BytesIO(img_bytes))
    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.axis("off")
    if title:
        ax.set_title(title)
    if suptitle:
        fig.suptitle(suptitle)
    return fig


def mpl_export_button(
    graph_id: str,
    renderer: Callable = _snapshot_renderer,
) -> html.Div:
    """Add a matplotlib export wizard button for a dcc.Graph.

    Parameters
    ----------
    graph_id :
        The ``id`` of the ``dcc.Graph`` component in the layout.
    renderer :
        Callable ``(fig_data, **kwargs) -> matplotlib.figure.Figure``.
        Parameters after ``fig_data`` are introspected to build the wizard fields.
        Defaults to :func:`_snapshot_renderer`.

    Returns
    -------
    html.Div
        A component containing the trigger button and the self-contained modal.
        Place it anywhere in the layout.
    """
    modal_id = f"_s5ndt_modal_{graph_id}"
    store_id = f"_s5ndt_store_{graph_id}"
    close_id = f"_s5ndt_close_{graph_id}"
    generate_id = f"_s5ndt_generate_{graph_id}"
    download_id = f"_s5ndt_download_{graph_id}"
    preview_id = f"_s5ndt_preview_{graph_id}"
    trigger_id = f"_s5ndt_trigger_{graph_id}"

    fields = _get_fields(renderer)
    field_states = _build_states(graph_id, fields)

    modal = html.Div(
        id=modal_id,
        style={"display": "none"},
        children=[
            # overlay (purely decorative, does not capture clicks)
            html.Div(
                style={
                    "position": "fixed",
                    "inset": "0",
                    "background": "rgba(0,0,0,0.4)",
                    "zIndex": 1000,
                    "pointerEvents": "none",
                }
            ),
            # dialog
            html.Div(
                style={
                    "position": "fixed",
                    "top": "50%",
                    "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "background": "white",
                    "padding": "24px",
                    "zIndex": 1001,
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "16px",
                    "minWidth": "600px",
                },
                children=[
                    # header
                    html.Div(
                        style={"display": "flex", "justifyContent": "space-between"},
                        children=[
                            html.Strong("Export as matplotlib figure"),
                            html.Button("✕", id=close_id),
                        ],
                    ),
                    # body: two columns
                    html.Div(
                        style={"display": "flex", "gap": "24px"},
                        children=[
                            # left: dynamic input fields
                            html.Div(
                                style={
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "gap": "8px",
                                    "minWidth": "160px",
                                },
                                children=[
                                    *[_build_field(graph_id, f) for f in fields],
                                    html.Button("Generate", id=generate_id),
                                ],
                            ),
                            # right: preview
                            html.Div(
                                children=[
                                    html.Img(
                                        id=preview_id, style={"maxWidth": "400px"}
                                    ),
                                ]
                            ),
                        ],
                    ),
                    # footer
                    dcc.Download(id=download_id),
                    html.Button("Download PNG", id=f"{download_id}_btn"),
                ],
            ),
        ],
    )

    store = dcc.Store(id=store_id, data=False)

    # --- callbacks ---

    @dash.callback(
        Output(store_id, "data"),
        Input(trigger_id, "n_clicks"),
        Input(close_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_store(open_clicks, close_clicks):
        return dash.ctx.triggered_id == trigger_id

    @dash.callback(
        Output(modal_id, "style"),
        Input(store_id, "data"),
    )
    def update_modal_visibility(is_open):
        return {"display": "block"} if is_open else {"display": "none"}

    @dash.callback(
        Output(preview_id, "src"),
        Input(generate_id, "n_clicks"),
        State(graph_id, "figure"),
        *field_states,
        prevent_initial_call=True,
    )
    def generate_preview(n_clicks, figure, *field_values):
        kwargs = _build_kwargs(fields, field_values)
        fig = renderer(figure, **kwargs)
        return _fig_to_src(fig)

    @dash.callback(
        Output(download_id, "data"),
        Input(f"{download_id}_btn", "n_clicks"),
        State(graph_id, "figure"),
        *field_states,
        prevent_initial_call=True,
    )
    def download_figure(n_clicks, figure, *field_values):
        kwargs = _build_kwargs(fields, field_values)
        fig = renderer(figure, **kwargs)
        return dcc.send_bytes(_fig_to_bytes(fig), "figure.png")

    return html.Div([html.Button("Export", id=trigger_id), store, modal])


# --- helpers ---


def _field_id(graph_id: str, field: _Field) -> str:
    return f"_s5ndt_field_{graph_id}_{field.name}"


def _time_field_id(graph_id: str, field: _Field) -> str:
    return f"_s5ndt_field_{graph_id}_{field.name}_time"


def _build_states(graph_id: str, fields: list[_Field]) -> list[State]:
    """Build the State list for callbacks. datetime emits two States (date + time)."""
    states = []
    for f in fields:
        if f.type == "datetime":
            states.append(State(_field_id(graph_id, f), "date"))
            states.append(State(_time_field_id(graph_id, f), "value"))
        elif f.type == "date":
            states.append(State(_field_id(graph_id, f), "date"))
        else:
            states.append(State(_field_id(graph_id, f), "value"))
    return states


def _infer_type(annotation: Any, default: Any) -> tuple[str, tuple, bool]:
    """Return (field_type, args, optional) from a parameter annotation + default."""
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[T] == Union[T, None]  |  T | None (Python 3.10+)
    if origin is Union or isinstance(annotation, types.UnionType):
        all_args = args if origin is Union else get_args(annotation)
        non_none = [a for a in all_args if a is not type(None)]
        if len(non_none) == 1:
            field_type, inner_args, _ = _infer_type(non_none[0], default)
            return field_type, inner_args, True
        return "str", (), False

    if annotation is bool or isinstance(default, bool):
        return "bool", (), False
    # datetime must be checked before date (datetime is a subclass of date)
    if annotation is datetime or isinstance(default, datetime):
        return "datetime", (), False
    if annotation is date or isinstance(default, date):
        return "date", (), False
    if annotation is int or (isinstance(default, int) and not isinstance(default, bool)):
        return "int", (), False
    if annotation is float or isinstance(default, float):
        return "float", (), False
    if origin is list:
        return "list", args, False
    if origin is tuple:
        return "tuple", args, False
    if origin is Literal:
        return "literal", args, False
    return "str", (), False


def _get_fields(renderer: Callable) -> list[_Field]:
    """Introspect renderer signature to build field descriptors.

    Skips the first parameter (fig_data). Uses get_type_hints for resolved
    annotations, infers type and optional from annotation + default value.
    """
    try:
        hints = get_type_hints(renderer)
    except Exception:
        hints = {}

    fields = []
    params = list(inspect.signature(renderer).parameters.values())[1:]  # skip fig_data
    for param in params:
        annotation = hints.get(param.name, param.annotation)
        default = param.default if param.default is not inspect.Parameter.empty else None
        field_type, args, optional = _infer_type(annotation, default)
        fields.append(_Field(
            name=param.name,
            type=field_type,
            default=default,
            args=args,
            optional=optional,
        ))

    return fields


def _build_field(graph_id: str, field: _Field) -> html.Div:
    """Build a labeled input component for a single field."""
    fid = _field_id(graph_id, field)
    label = html.Label(field.name.replace("_", " ").title())

    if field.type == "bool":
        component = dcc.Checklist(
            id=fid,
            options=[{"label": "", "value": field.name}],
            value=[field.name] if field.default else [],
        )
    elif field.type == "date":
        component = dcc.DatePickerSingle(
            id=fid,
            date=field.default.isoformat() if isinstance(field.default, date) else None,
        )
    elif field.type == "datetime":
        default_date = field.default.date().isoformat() if isinstance(field.default, datetime) else None
        default_time = field.default.strftime("%H:%M") if isinstance(field.default, datetime) else None
        component = html.Div(
            style={"display": "flex", "gap": "8px", "alignItems": "center"},
            children=[
                dcc.DatePickerSingle(id=fid, date=default_date),
                dcc.Input(
                    id=_time_field_id(graph_id, field),
                    type="text",
                    placeholder="HH:MM",
                    value=default_time,
                    debounce=True,
                    style={"width": "70px"},
                ),
            ],
        )
    elif field.type in ("int", "float"):
        component = dcc.Input(
            id=fid,
            type="number",
            step=1 if field.type == "int" else "any",
            value=field.default,
        )
    elif field.type in ("list", "tuple"):
        if field.type == "tuple":
            placeholder = ", ".join(t.__name__ for t in field.args)
        else:
            elem = field.args[0].__name__ if field.args else "value"
            placeholder = f"{elem}, ..."
        component = dcc.Input(
            id=fid,
            type="text",
            value=", ".join(str(v) for v in field.default) if field.default else "",
            placeholder=placeholder,
        )
    elif field.type == "literal":
        component = dcc.Dropdown(
            id=fid,
            options=list(field.args),
            value=field.default if field.default in field.args else field.args[0],
        )
    else:
        component = dcc.Input(
            id=fid,
            type="text",
            value=str(field.default) if field.default is not None else "",
            placeholder="",
        )

    return html.Div([label, component])


def _coerce(field: _Field, value: Any) -> Any:
    """Coerce a raw widget value to the field's Python type."""
    if field.type == "bool":
        return bool(value)  # checklist: [] -> False, [...] -> True

    empty = value is None or value == "" or value == []
    if empty:
        return None if field.optional else field.default

    if field.type == "date":
        return date.fromisoformat(value)
    if field.type == "int":
        return int(value)
    if field.type == "float":
        return float(value)
    if field.type == "list":
        elem_type = field.args[0] if field.args else str
        return [elem_type(x.strip()) for x in value.split(",")]
    if field.type == "tuple":
        parts = [x.strip() for x in value.split(",")]
        if field.args:
            return tuple(t(v) for t, v in zip(field.args, parts))
        return tuple(parts)
    if field.type == "literal":
        return value
    return value or ""


def _build_kwargs(fields: list[_Field], values: tuple) -> dict:
    """Consume values with an iterator — datetime fields consume two (date + time)."""
    it = iter(values)
    kwargs = {}
    for field in fields:
        if field.type == "datetime":
            date_val = next(it)
            time_val = next(it)
            if date_val is None:
                kwargs[field.name] = None if field.optional else field.default
            else:
                kwargs[field.name] = datetime.fromisoformat(
                    f"{date_val}T{time_val or '00:00'}"
                )
        else:
            kwargs[field.name] = _coerce(field, next(it))
    return kwargs


def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _fig_to_src(fig) -> str:
    encoded = base64.b64encode(_fig_to_bytes(fig)).decode("utf-8")
    return f"data:image/png;base64,{encoded}"
