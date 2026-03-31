# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Wizard modal body layout — pure HTML construction, no callbacks."""

from __future__ import annotations

from typing import Any

from dash import dcc, html


def build_modal_body(
    config_div: Any,
    generate_id: str,
    download_id: str,
    preview_id: str,
    copy_id: str,
    error_id: str,
    interval_id: str,
    snapshot_store_id: str,
    format_id: str,
    has_fields: bool,
    styles: dict,
    class_names: dict,
    resolved_store_id: str | None = None,
    show_format: bool = True,
) -> html.Div:
    """Build the wizard modal body: config fields, preview, and action buttons."""
    gen_style = dict(styles.get("button") or {})
    if not has_fields:
        gen_style["display"] = "none"

    fmt_style = {"display": "flex", "alignItems": "center", "gap": "6px"}
    if not show_format:
        fmt_style["display"] = "none"
    format_selector = html.Div(
        style=fmt_style,
        children=[
            html.Label("Format:", style={"fontSize": "12px", "color": "#888"}),
            dcc.Dropdown(
                id=format_id,
                options=[
                    {"label": "PNG", "value": "png"},
                    {"label": "JPEG", "value": "jpeg"},
                    {"label": "WebP", "value": "webp"},
                    {"label": "SVG", "value": "svg"},
                ],
                value="png",
                clearable=False,
                style={"width": "100px", "fontSize": "12px"},
                persistence=True,
                persistence_type="session",
            ),
        ],
    )

    generate_btn = html.Button(
        "Generate",
        id=generate_id,
        style=gen_style,
        className=class_names.get("button", ""),
    )

    return html.Div(
        style={"display": "flex", "flexDirection": "column", "gap": "12px"},
        children=[
            # Top: config | preview
            html.Div(
                style={"display": "flex", "gap": "24px"},
                children=[
                    html.Div(
                        style={
                            "display": "flex",
                            "flexDirection": "column",
                            "gap": "8px",
                            "minWidth": "160px",
                        },
                        children=[config_div, format_selector],
                    ),
                    html.Div(
                        style={
                            "position": "relative",
                            "minWidth": "300px",
                            "minHeight": "200px",
                        },
                        children=[
                            dcc.Loading(
                                type="circle",
                                children=[
                                    html.Img(id=preview_id, style={"maxWidth": "400px"})
                                ],
                            ),
                            html.Div(
                                id=error_id,
                                style={
                                    "color": "red",
                                    "fontSize": "13px",
                                    "marginTop": "8px",
                                },
                            ),
                        ],
                    ),
                ],
            ),
            # Bottom: generate | download + copy
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                },
                children=[
                    generate_btn,
                    html.Div(
                        style={"display": "flex", "gap": "6px"},
                        children=[
                            html.Button(
                                "Download",
                                id=f"{download_id}_btn",
                                style=styles.get("button"),
                                className=class_names.get("button", ""),
                            ),
                            html.Button(
                                "Copy",
                                id=copy_id,
                                style=styles.get("button"),
                                className=class_names.get("button", ""),
                            ),
                            dcc.Download(id=download_id),
                        ],
                    ),
                ],
            ),
            # Hidden infra
            dcc.Interval(
                id=interval_id,
                interval=500,
                n_intervals=0,
                max_intervals=1,
                disabled=True,
            ),
            dcc.Store(id=snapshot_store_id),
            *([] if resolved_store_id is None else [dcc.Store(id=resolved_store_id)]),
        ],
    )
