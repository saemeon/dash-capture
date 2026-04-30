# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Wizard modal — layout, dropdown overlay, and callback wiring.

This module used to be three files: ``_wizard.py`` (build_wizard shell),
``_wizard_layout.py`` (build_modal_body DOM), ``_wizard_callbacks.py``
(callback registrations + wire_wizard assembly) plus ``_dropdown.py``
(the overflow-menu dropdown). They were merged because they were only
ever used together and the split added navigation overhead without
benefit.

Public entry points:

* :func:`wire_wizard` — the main assembly, called by ``_make_wizard``
  in ``capture.py``.
* :func:`build_wizard` — modal shell (trigger + overlay + dialog).
* :func:`build_modal_body` — the body DOM (config / preview / actions).
* :func:`build_dropdown` — the overflow ``···`` menu.

The ``_register_*`` functions are all private; they register one
clientside or server callback each and are assembled by
:func:`wire_wizard`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import dash
from dash import Input, Output, State, dcc, html
from dash_fn_form import FnForm, field_id
from dash_fn_form._spec import _FieldFixed

from dash_capture.strategies import CaptureStrategy, build_capture_js

if TYPE_CHECKING:
    # Avoid runtime circular import: capture.py imports wire_wizard from
    # this module, and this module needs WizardConfig only as a type hint.
    from dash_capture.capture import WizardConfig


# ---------------------------------------------------------------------------
# Snapshot cache helpers — memoization by capture options
# ---------------------------------------------------------------------------


def _hash_capture_options(opts: dict) -> str:
    """Hash capture options dict to create a cache key.

    Used to detect when resolved capture options (capture_width, capture_height,
    etc) haven't changed, allowing us to reuse the cached snapshot from the
    browser instead of recapturing.

    Args:
        opts: dict from capture_resolver (e.g. {"capture_width": 800})

    Returns:
        40-char hex string (SHA1 hash)
    """
    normalized = json.dumps(opts, sort_keys=True, default=str)
    return hashlib.sha1(normalized.encode()).hexdigest()


def _check_snapshot_cache(cache_dict: dict, cache_key: str) -> str | None:
    """Check if a snapshot is cached for this capture options hash.

    Args:
        cache_dict: The cache store data (dict mapping hash -> snapshot_b64)
        cache_key: SHA1 hash of capture options

    Returns:
        Cached snapshot data (base64 PNG) if present, None otherwise.
    """
    if not cache_dict:
        return None
    return cache_dict.get(cache_key)


# ---------------------------------------------------------------------------
# Helpers — renderer invocation, data URI handling, arg unpacking
# ---------------------------------------------------------------------------


def _make_snapshot_fn(img_b64: str) -> Callable[[], bytes]:
    def _snapshot_img() -> bytes:
        b64 = img_b64.split(",", 1)[1]
        return base64.b64decode(b64)

    return _snapshot_img


def _call_renderer(
    renderer: Callable,
    has_fig_data: bool,
    has_snapshot: bool,
    fig_data: dict,
    img_b64: str,
    kwargs: dict,
) -> bytes:
    buf = io.BytesIO()
    call_kwargs = dict(kwargs)
    if has_fig_data:
        call_kwargs["_fig_data"] = fig_data
    if has_snapshot:
        call_kwargs["_snapshot_img"] = _make_snapshot_fn(img_b64)
    renderer(buf, **call_kwargs)
    buf.seek(0)
    return buf.read()


def _to_src(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


def _unpack_args(has_fig_data: bool, args: tuple) -> tuple[dict, tuple]:
    """Split callback args into (fig_data, field_values)."""
    if has_fig_data:
        fig_data, *field_values = args
        return fig_data, tuple(field_values)
    return {}, args


def _resolve_download_name(
    filename: str | Callable[..., str],
    fmt: str | None,
    field_kwargs: dict,
) -> str:
    """Resolve the final download filename.

    Callable filenames are invoked with ``field_kwargs`` as keyword
    arguments. A raised exception falls back to ``"capture.png"`` so
    the download still works rather than failing silently. The format
    extension is then patched in for non-PNG formats.
    """
    if callable(filename):
        try:
            dl_name = cast(Callable[..., str], filename)(**field_kwargs)
        except Exception:
            dl_name = "capture.png"
    else:
        dl_name = filename
    if fmt and fmt != "png":
        stem = dl_name.rsplit(".", 1)[0] if "." in dl_name else dl_name
        ext = "jpg" if fmt == "jpeg" else fmt
        dl_name = f"{stem}.{ext}"
    return dl_name


# ---------------------------------------------------------------------------
# Wizard modal shell
# ---------------------------------------------------------------------------


@dataclass
class Wizard:
    """Return value of :func:`build_wizard`."""

    div: html.Div
    open_input: Input


_DEFAULT_DIALOG_STYLE = {
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
}


def build_wizard(
    wizard_id: str,
    body: Any,
    trigger: str | Any = "Open",
    title: str | Any = "",
    header_actions: Any = None,
    dialog_style: dict | None = None,
    dialog_class_name: str = "",
    title_style: dict | None = None,
    close_style: dict | None = None,
) -> Wizard:
    """Wrap *body* in a modal wizard popup with open/close logic."""
    default_trigger_id = f"_dcap_wiz_trigger_{wizard_id}"
    close_id = f"_dcap_wiz_close_{wizard_id}"
    store_id = f"_dcap_wiz_store_{wizard_id}"
    modal_id = f"_dcap_wiz_modal_{wizard_id}"
    open_input = Input(store_id, "data")

    if isinstance(trigger, str):
        trigger_component = html.Button(trigger, id=default_trigger_id)
    else:
        if not hasattr(trigger, "id") or not trigger.id:
            raise ValueError("Custom trigger component must have an 'id' attribute.")
        trigger_component = trigger
    trigger_listen_id = cast(Any, trigger_component).id

    modal = html.Div(
        id=modal_id,
        style={"display": "none"},
        children=[
            # overlay — blocks interaction with underlying UI while open
            html.Div(
                style={
                    "position": "fixed",
                    "inset": "0",
                    "background": "rgba(0,0,0,0.4)",
                    "zIndex": 1000,
                }
            ),
            # dialog
            html.Div(
                style={**_DEFAULT_DIALOG_STYLE, **(dialog_style or {})},
                className=dialog_class_name,
                children=[
                    html.Div(
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                        },
                        children=[
                            html.Strong(title, style=title_style)
                            if isinstance(title, str)
                            else title,
                            html.Div(
                                style={
                                    "display": "flex",
                                    "gap": "4px",
                                    "alignItems": "center",
                                },
                                children=[
                                    *(
                                        [header_actions]
                                        if header_actions is not None
                                        else []
                                    ),
                                    html.Button("✕", id=close_id, style=close_style),
                                ],
                            ),
                        ],
                    ),
                    body,
                ],
            ),
        ],
    )

    store = dcc.Store(id=store_id, data=False)

    @dash.callback(
        Output(store_id, "data"),
        Input(trigger_listen_id, "n_clicks"),
        Input(close_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_store(open_clicks, close_clicks):
        return dash.ctx.triggered_id == trigger_listen_id

    @dash.callback(
        Output(modal_id, "style"),
        open_input,
    )
    def update_visibility(is_open):
        return {"display": "block"} if is_open else {"display": "none"}

    # When the trigger is a custom component, the user places it in the layout
    # themselves. Return only the store + modal so there's no duplicate render.
    children = (
        [store, modal]
        if not isinstance(trigger, str)
        else [trigger_component, store, modal]
    )
    return Wizard(
        div=html.Div(children),
        open_input=open_input,
    )


# ---------------------------------------------------------------------------
# Modal body layout (pure DOM, no callbacks)
# ---------------------------------------------------------------------------


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
    snapshot_cache_store_id: str | None = None,
    cache_miss_store_id: str | None = None,
    show_format: bool = True,
    action_button_ids: list[tuple[str, str]] | None = None,
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
                            *[
                                html.Button(
                                    label,
                                    id=btn_id,
                                    style=styles.get("button"),
                                    className=class_names.get("button", ""),
                                )
                                for btn_id, label in (action_button_ids or [])
                            ],
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
            *([] if snapshot_cache_store_id is None else [dcc.Store(id=snapshot_cache_store_id, data={})]),
            *([] if cache_miss_store_id is None else [dcc.Store(id=cache_miss_store_id)]),
        ],
    )


# ---------------------------------------------------------------------------
# Overflow-menu dropdown (used for the wizard's ``···`` menu)
# ---------------------------------------------------------------------------


def build_dropdown(
    dropdown_id: str,
    children: Any,
    trigger_label: str = "···",
    close_inputs: list[Input] | None = None,
    styles: dict | None = None,
    class_names: dict | None = None,
) -> html.Div:
    """A generic toggle dropdown anchored to a trigger button.

    Parameters
    ----------
    dropdown_id :
        Unique namespace for component IDs.
    children :
        Content rendered inside the dropdown panel.
    trigger_label :
        Label for the trigger button. Defaults to ``"···"``.
    close_inputs :
        Additional :class:`dash.Input` objects that close the dropdown
        (e.g. a reset button click).
    styles :
        Dict mapping slot names to CSS-property dicts. Slots:
        ``"button"`` → trigger button, ``"panel"`` → dropdown panel
        (inherits theming keys from ``"dialog"`` if present).
    class_names :
        Dict mapping the same slot names to CSS class name strings.

    Returns
    -------
    html.Div
        Self-contained component; place it anywhere in the layout.
    """
    trigger_id = f"_dcap_dd_trigger_{dropdown_id}"
    panel_id = f"_dcap_dd_panel_{dropdown_id}"
    overlay_id = f"_dcap_dd_overlay_{dropdown_id}"

    _styles = styles or {}
    _class_names = class_names or {}

    # Inherit safe theming properties from "dialog" (background, color,
    # borderRadius, boxShadow, border) then let "panel" override further.
    # Layout-only keys (minWidth, padding, gap, …) are intentionally excluded
    # to avoid bleeding modal layout onto a small context menu.
    _theme_keys = {"background", "color", "borderRadius", "boxShadow", "border"}
    _dialog_theme = {
        k: v for k, v in (_styles.get("dialog") or {}).items() if k in _theme_keys
    }
    _panel_base = {
        "position": "absolute",
        "right": "0",
        "background": "white",
        "border": "1px solid #ccc",
        "zIndex": 100,
        "whiteSpace": "nowrap",
        **_dialog_theme,
        **(_styles.get("panel") or {}),
    }
    _panel_hidden = {"display": "none", **_panel_base}
    _panel_visible = {"display": "block", **_panel_base}

    _overlay_hidden = {
        "display": "none",
        "position": "fixed",
        "inset": "0",
        "zIndex": 99,
    }
    _overlay_visible = {**_overlay_hidden, "display": "block"}

    extra_close = close_inputs or []

    @dash.callback(
        Output(panel_id, "style"),
        Output(overlay_id, "style"),
        Input(trigger_id, "n_clicks"),
        Input(overlay_id, "n_clicks"),
        *extra_close,
        State(panel_id, "style"),
        prevent_initial_call=True,
    )
    def _toggle(*args):
        current_style = args[-1]
        if dash.ctx.triggered_id == trigger_id:
            already_open = current_style and current_style.get("display") == "block"
            if already_open:
                return _panel_hidden, _overlay_hidden
            return _panel_visible, _overlay_visible
        return _panel_hidden, _overlay_hidden

    return html.Div(
        style={"position": "relative", "display": "inline-block"},
        children=[
            html.Button(
                trigger_label,
                id=trigger_id,
                style=_styles.get("button"),
                className=_class_names.get("button", ""),
            ),
            html.Div(id=overlay_id, n_clicks=0, style=_overlay_hidden),
            html.Div(
                id=panel_id,
                style=_panel_hidden,
                className=_class_names.get("panel", ""),
                children=children,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Callback registration (one function per named callback)
# ---------------------------------------------------------------------------


def _register_autogenerate_toggle(generate_id: str, autogenerate_id: str) -> None:
    """Disable Generate button when autogenerate is on."""
    dash.clientside_callback(
        "function(v) { return v != null && v.length > 0; }",
        Output(generate_id, "disabled"),
        Input(autogenerate_id, "value"),
    )


def _register_arm_interval(interval_id: str, open_input: Input) -> None:
    """Arm the capture interval when the wizard opens."""

    @dash.callback(
        Output(interval_id, "disabled"),
        Output(interval_id, "n_intervals"),
        open_input,
        prevent_initial_call=True,
    )
    def arm_interval(is_open):
        return (not is_open, 0)


def _register_capture_resolved(
    *,
    element_id: str,
    strategy: CaptureStrategy,
    params: Mapping,
    config: FnForm,
    resolved_store_id: str,
    snapshot_store_id: str,
    snapshot_cache_store_id: str,
    cache_miss_store_id: str,
    generate_id: str,
    interval_id: str,
    autogenerate_id: str,
    format_id: str,
    capture_resolver: Callable,
) -> None:
    """Wire the two-step flow with snapshot caching.

    The resolver computes capture options (capture_width, capture_height, etc)
    from form fields. We hash these options and check a cache:

    - Cache HIT: reuse old snapshot, skip JS capture (fast!)
    - Cache MISS: trigger JS capture, store result in cache

    This way, changing non-dimensional fields (title, colors) reuses the
    cached snapshot instead of recapturing the live graph.

    Cache is cleared when wizard closes (live graph might have been zoomed/panned).
    """
    _resolve_inputs = [
        Input(s.component_id, s.component_property) for s in config.states
    ]

    # --- Callback 1: Compute capture options ---
    @dash.callback(
        Output(resolved_store_id, "data"),
        Input(generate_id, "n_clicks"),
        Input(interval_id, "n_intervals"),
        *_resolve_inputs,
        State(autogenerate_id, "value"),
        State(snapshot_store_id, "data"),
        prevent_initial_call=True,
    )
    def resolve_capture(n_clicks, n_intervals, *args):
        """Compute capture options from form fields via the resolver.

        Args:
            n_clicks: Generate button clicks
            n_intervals: Initial capture interval (fires once after wizard opens)
            *args: field_values... autogen snapshot

        Returns:
            dict with capture_width, capture_height, etc, or no_update
        """
        *field_values, autogen, snapshot = args
        is_generate = dash.ctx.triggered_id in (generate_id, interval_id)

        # Only proceed if user clicked Generate/interval fired, or autogen is on
        # and we have a previous snapshot (autogen on field change)
        if not is_generate and (not autogen or not snapshot):
            return dash.no_update

        # Compute capture options via user's resolver function.
        # Example: capture_resolver(title="foo", figsize=10) → {"capture_width": 800}
        kwargs = config.build_kwargs(tuple(field_values))
        return capture_resolver(**kwargs)

    # --- Callback 2: Check cache; route to snapshot (hit) or cache_miss (miss) ---
    # The two outputs are mutually exclusive — exactly one gets written per fire.
    # This is the lever that makes the cache actually save work: on a hit we
    # write to snapshot_store (preview re-renders, no JS), and crucially we do
    # NOT write to cache_miss_store, so the JS clientside callback below stays
    # idle. On a miss we write capture_opts to cache_miss_store, which triggers
    # the JS capture exactly once.
    @dash.callback(
        Output(snapshot_store_id, "data", allow_duplicate=True),
        Output(cache_miss_store_id, "data"),
        Input(resolved_store_id, "data"),
        State(snapshot_cache_store_id, "data"),
        prevent_initial_call=True,
    )
    def cache_check_and_apply(capture_opts, cache_dict):
        """Decide hit/miss and route accordingly.

        Returns:
            (snapshot, miss_payload)

            On HIT we write the cached snapshot AND explicitly clear
            cache_miss_store to ``None``. Clearing matters because
            cache_update (Callback 4) reads cache_miss_store as State to
            recover the cache key for the snapshot it sees. If we left
            stale opts in cache_miss_store from the previous miss, a hit
            would cause cache_update to file the cached snapshot under
            the WRONG key — a cache-poisoning bug.

            The clientside JS callback (Callback 3) listens on
            cache_miss_store but already guards against falsy data, so
            writing ``None`` triggers it but it bails immediately.
        """
        if not capture_opts:
            return dash.no_update, dash.no_update

        cache_key = _hash_capture_options(capture_opts)
        cached_snapshot = _check_snapshot_cache(cache_dict or {}, cache_key)

        if cached_snapshot is not None:
            # Hit: feed cached snapshot to snapshot_store AND clear
            # cache_miss_store so cache_update doesn't poison the cache.
            return cached_snapshot, None

        # Miss: forward capture_opts to cache_miss_store; the JS callback
        # listens on it and will run the actual browser-side capture.
        return dash.no_update, capture_opts

    # --- Callback 3: JS capture, fired only on cache miss ---
    # Note the Input is cache_miss_store, NOT resolved_store. This is what
    # makes the cache actually skip the expensive browser-side capture.
    capture_js = build_capture_js(element_id, strategy, [], params, from_resolved=True)
    dash.clientside_callback(
        capture_js,
        Output(snapshot_store_id, "data", allow_duplicate=True),
        Input(cache_miss_store_id, "data"),
        State(format_id, "value"),
        prevent_initial_call=True,
    )

    # --- Callback 4: Cache fresh snapshots ---
    # `allow_duplicate=True` — clear_cache_on_close (registered later in
    # wire_wizard) also writes to snapshot_cache_store, so both Outputs
    # need to declare the duplicate.
    @dash.callback(
        Output(snapshot_cache_store_id, "data", allow_duplicate=True),
        Input(snapshot_store_id, "data"),
        State(cache_miss_store_id, "data"),
        State(snapshot_cache_store_id, "data"),
        prevent_initial_call=True,
    )
    def cache_update(snapshot, miss_opts, cache_dict):
        if not snapshot or not miss_opts:
            return dash.no_update
        cache_key = _hash_capture_options(miss_opts)
        cache_dict = dict(cache_dict or {})
        cache_dict[cache_key] = snapshot
        return cache_dict


def _register_capture_direct(
    *,
    element_id: str,
    strategy: CaptureStrategy,
    params: Mapping,
    config_id: str,
    active_capture: list[str],
    field_specs: dict[str, Any] | None,
    snapshot_store_id: str,
    generate_id: str,
    interval_id: str,
    format_id: str,
) -> None:
    """Wire the direct flow: JS reads capture params from form State."""
    fixed_capture: dict[str, Any] = {}
    dynamic_capture: list[str] = []
    for name in active_capture:
        spec = (field_specs or {}).get(name)
        if isinstance(spec, _FieldFixed):
            fixed_capture[name] = spec.value
        else:
            dynamic_capture.append(name)

    _capture_states = [
        State(field_id(config_id, name), "value") for name in dynamic_capture
    ]
    capture_js = build_capture_js(
        element_id,
        strategy,
        dynamic_capture,
        params,
        fixed_capture=fixed_capture,
    )

    dash.clientside_callback(
        capture_js,
        Output(snapshot_store_id, "data"),
        Input(generate_id, "n_clicks"),
        Input(interval_id, "n_intervals"),
        State(format_id, "value"),
        *_capture_states,
        prevent_initial_call=True,
    )


def _register_preview_from_snapshot(
    *,
    renderer: Callable,
    config: FnForm,
    has_fig_data: bool,
    element_id: str,
    preview_id: str,
    error_id: str,
    snapshot_store_id: str,
) -> None:
    """Update preview when a new snapshot arrives (used with has_snapshot=True)."""
    _fig_states = [State(element_id, "figure")] if has_fig_data else []

    @dash.callback(
        Output(preview_id, "src"),
        Output(error_id, "children"),
        Input(snapshot_store_id, "data"),
        *_fig_states,
        *config.states,
        prevent_initial_call=True,
    )
    def generate_preview(_img_b64, *args):
        if not _img_b64:
            return dash.no_update, dash.no_update
        fig_data, field_values = _unpack_args(has_fig_data, args)
        kwargs = config.build_kwargs(tuple(field_values))
        try:
            return _to_src(
                _call_renderer(renderer, has_fig_data, True, fig_data, _img_b64, kwargs)
            ), ""
        except Exception as e:
            return dash.no_update, f"Error: {e}"


def _register_preview_from_figdata(
    *,
    renderer: Callable,
    config: FnForm,
    has_fig_data: bool,
    element_id: str,
    preview_id: str,
    error_id: str,
    generate_id: str,
    interval_id: str,
) -> None:
    """Update preview on Generate click (used with has_snapshot=False, _fig_data only)."""
    _fig_states = [State(element_id, "figure")] if has_fig_data else []

    @dash.callback(
        Output(preview_id, "src"),
        Output(error_id, "children"),
        Input(generate_id, "n_clicks"),
        Input(interval_id, "n_intervals"),
        *_fig_states,
        *config.states,
        prevent_initial_call=True,
    )
    def generate_preview(n_clicks, n_intervals, *args):
        if not n_clicks and not n_intervals:
            return dash.no_update, dash.no_update
        fig_data, field_values = _unpack_args(has_fig_data, args)
        kwargs = config.build_kwargs(tuple(field_values))
        try:
            return _to_src(
                _call_renderer(renderer, has_fig_data, False, fig_data, "", kwargs)
            ), ""
        except Exception as e:
            return dash.no_update, f"Error: {e}"


def _register_autogenerate_preview(
    *,
    renderer: Callable,
    config: FnForm,
    has_snapshot: bool,
    has_fig_data: bool,
    element_id: str,
    preview_id: str,
    error_id: str,
    autogenerate_id: str,
    snapshot_store_id: str,
) -> None:
    """Re-render preview on field changes (without capture_resolver)."""
    _fig_states = [State(element_id, "figure")] if has_fig_data else []

    @dash.callback(
        Output(preview_id, "src", allow_duplicate=True),
        Output(error_id, "children", allow_duplicate=True),
        *[Input(s.component_id, s.component_property) for s in config.states],
        State(autogenerate_id, "value"),
        State(snapshot_store_id, "data"),
        *_fig_states,
        prevent_initial_call=True,
    )
    def autogenerate_preview(*args):
        if has_fig_data:
            *field_values, autogen, _img_b64, _fig_data = args
        else:
            *field_values, autogen, _img_b64 = args
            _fig_data = {}
        if not autogen:
            return dash.no_update, dash.no_update
        if has_snapshot and not _img_b64:
            return dash.no_update, dash.no_update
        kwargs = config.build_kwargs(tuple(field_values))
        try:
            return _to_src(
                _call_renderer(
                    renderer,
                    has_fig_data,
                    has_snapshot,
                    _fig_data,
                    _img_b64 or "",
                    kwargs,
                )
            ), ""
        except Exception as e:
            return dash.no_update, f"Error: {e}"


def _register_download(
    download_id: str,
    preview_id: str,
    format_id: str,
    filename: str | Callable[..., str],
    config: FnForm | Any = None,
) -> None:
    """Download the current preview image.

    ``filename`` is either a static string or a callable that receives
    the current form-field values as kwargs and returns the filename.
    """
    is_callable = callable(filename)
    field_states = list(config.states) if (is_callable and config is not None) else []

    @dash.callback(
        Output(download_id, "data"),
        Input(f"{download_id}_btn", "n_clicks"),
        State(preview_id, "src"),
        State(format_id, "value"),
        *field_states,
        prevent_initial_call=True,
    )
    def download_figure(n_clicks, preview_src, fmt, *field_values):
        if not preview_src:
            return dash.no_update
        header, data = preview_src.split(",", 1)
        raw = base64.b64decode(data)
        kwargs = (
            config.build_kwargs(tuple(field_values))
            if (is_callable and config is not None)
            else {}
        )
        dl_name = _resolve_download_name(filename, fmt, kwargs)
        return dcc.send_bytes(raw, dl_name)


def _register_copy_to_clipboard(copy_id: str, preview_id: str) -> None:
    """Copy the preview image to clipboard (clientside)."""
    dash.clientside_callback(
        """
        async function(n_clicks, src) {
            if (!n_clicks || !src) return window.dash_clientside.no_update;
            try {
                const resp = await fetch(src);
                const blob = await resp.blob();
                await navigator.clipboard.write([
                    new ClipboardItem({ [blob.type]: blob })
                ]);
            } catch (e) {
                console.error('Copy to clipboard failed:', e);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output(copy_id, "n_clicks"),
        Input(copy_id, "n_clicks"),
        State(preview_id, "src"),
        prevent_initial_call=True,
    )


def _register_custom_action(
    *,
    btn_id: str,
    preview_id: str,
    snapshot_store_id: str,
    config: FnForm,
    callback: Callable,
) -> None:
    """Register a custom action button callback."""

    @dash.callback(
        Output(btn_id, "n_clicks"),
        Input(btn_id, "n_clicks"),
        State(snapshot_store_id, "data"),
        State(preview_id, "src"),
        *config.states,
        prevent_initial_call=True,
    )
    def handle_action(n_clicks, snapshot_data, preview_src, *field_values):
        if not n_clicks:
            return dash.no_update
        data_uri = snapshot_data or preview_src or ""
        kwargs = config.build_kwargs(tuple(field_values))
        callback(data_uri, **kwargs)
        return dash.no_update


# ---------------------------------------------------------------------------
# Main assembly: build wizard + register all callbacks
# ---------------------------------------------------------------------------


def wire_wizard(
    *,
    cfg: WizardConfig,
    strategy: CaptureStrategy,
    config: Any,  # FnForm or dash_capture.capture._NullFnForm — duck-typed
    has_snapshot: bool,
    has_fig_data: bool,
    active_capture: list[str],
    params: Mapping,
    ids: dict[str, str],
    trigger: str | Any,
    styles: dict,
    class_names: dict,
    field_specs: dict[str, Any] | None,
    show_format: bool,
) -> html.Div:
    """Build the wizard layout and register all callbacks.

    Takes the user-supplied config (``cfg``) plus the runtime state
    that ``_make_wizard`` already computed (resolved strategy after
    preprocess merge, the FnForm/_NullFnForm config, the renderer
    metadata booleans, the merged field_specs, the resolved
    show_format bool, etc.). The split keeps the dataclass focused
    on user inputs and the kwargs focused on derived state.
    """
    # Pull renderer-side data from cfg, runtime data from kwargs.
    element_id = cfg.element_id
    renderer = cfg.renderer
    filename = cfg.filename
    autogenerate = cfg.autogenerate
    capture_resolver = cfg.capture_resolver
    wizard_header = cfg.wizard_header
    actions = cfg.actions or []

    config_id = ids["cfg"]
    wizard_id = ids["wiz"]
    preview_id = ids["preview"]
    generate_id = ids["generate"]
    download_id = ids["download"]
    copy_id = ids["copy"]
    error_id = ids["error"]
    interval_id = ids["interval"]
    restore_id = ids["restore"]
    menu_id = ids["menu"]
    autogenerate_id = ids["autogen"]
    snapshot_store_id = ids["snapshot"]
    format_id = ids["format"]
    resolved_store_id = ids.get("resolved")
    snapshot_cache_store_id = ids.get("snapshot_cache")
    cache_miss_store_id = ids.get("cache_miss")

    action_ids = [
        (f"_dcap_action_{i}_{wizard_id}", action.label)
        for i, action in enumerate(actions)
    ]

    # --- Layout ---
    menu = build_dropdown(
        menu_id,
        trigger_label="···",
        close_inputs=[Input(restore_id, "n_clicks")],
        styles=styles,
        class_names=class_names,
        children=[
            html.Button(
                "Reset to defaults",
                id=restore_id,
                style=styles.get("button"),
                className=class_names.get("button", ""),
            ),
            dcc.Checklist(
                id=autogenerate_id,
                options=[{"label": " Auto-generate", "value": "auto"}],
                value=["auto"] if autogenerate else [],
                style={"padding": "4px 8px"},
                labelStyle={
                    k: v for k, v in (styles.get("label") or {}).items() if k == "color"
                },
            ),
        ],
    )

    body = build_modal_body(
        config,
        generate_id,
        download_id,
        preview_id,
        copy_id,
        error_id,
        interval_id,
        snapshot_store_id,
        format_id,
        bool(config.states),
        styles,
        class_names,
        resolved_store_id=resolved_store_id,
        snapshot_cache_store_id=snapshot_cache_store_id,
        cache_miss_store_id=cache_miss_store_id,
        show_format=show_format,
        action_button_ids=action_ids,
    )

    wizard = build_wizard(
        wizard_id,
        body,
        trigger=trigger,
        title=wizard_header,
        header_actions=menu,
        dialog_style=styles.get("dialog"),
        dialog_class_name=class_names.get("dialog", ""),
        title_style=styles.get("title"),
        close_style=styles.get("close"),
    )
    config.register_populate_callback(wizard.open_input)
    config.register_restore_callback(Input(restore_id, "n_clicks"))

    # --- Callbacks ---
    _register_autogenerate_toggle(generate_id, autogenerate_id)
    _register_arm_interval(interval_id, wizard.open_input)

    if has_snapshot:
        if capture_resolver is not None:
            assert resolved_store_id is not None
            assert snapshot_cache_store_id is not None
            assert cache_miss_store_id is not None
            _register_capture_resolved(
                element_id=element_id,
                strategy=strategy,
                params=params,
                config=config,
                resolved_store_id=resolved_store_id,
                snapshot_store_id=snapshot_store_id,
                snapshot_cache_store_id=snapshot_cache_store_id,
                cache_miss_store_id=cache_miss_store_id,
                generate_id=generate_id,
                interval_id=interval_id,
                autogenerate_id=autogenerate_id,
                format_id=format_id,
                capture_resolver=capture_resolver,
            )
        else:
            _register_capture_direct(
                element_id=element_id,
                strategy=strategy,
                params=params,
                config_id=config_id,
                active_capture=active_capture,
                field_specs=field_specs,
                snapshot_store_id=snapshot_store_id,
                generate_id=generate_id,
                interval_id=interval_id,
                format_id=format_id,
            )

        _register_preview_from_snapshot(
            renderer=renderer,
            config=config,
            has_fig_data=has_fig_data,
            element_id=element_id,
            preview_id=preview_id,
            error_id=error_id,
            snapshot_store_id=snapshot_store_id,
        )

        # Clear snapshot cache when wizard closes — only when cache is active
        # (i.e. capture_resolver is in use). The live graph might have been
        # zoomed, panned, or otherwise modified while the wizard was open, so
        # cached snapshots from before the close may no longer match the current
        # graph state. By clearing on close, we ensure the next capture is fresh.
        if snapshot_cache_store_id is not None:

            @dash.callback(
                Output(snapshot_cache_store_id, "data", allow_duplicate=True),
                wizard.open_input,
                prevent_initial_call=True,
            )
            def clear_cache_on_close(is_open):
                """Reset snapshot cache to empty dict when wizard closes."""
                if is_open:
                    # Wizard is opening: keep any existing cache
                    return dash.no_update
                # Wizard is closing: clear the cache
                return {}
    else:
        _register_preview_from_figdata(
            renderer=renderer,
            config=config,
            has_fig_data=has_fig_data,
            element_id=element_id,
            preview_id=preview_id,
            error_id=error_id,
            generate_id=generate_id,
            interval_id=interval_id,
        )

    # Autogenerate on field change — only when capture_resolver is NOT active
    # (with resolver, field changes trigger re-resolve → re-capture → snapshot
    # update → preview update via the snapshot callback chain).
    if config.states and capture_resolver is None:
        _register_autogenerate_preview(
            renderer=renderer,
            config=config,
            has_snapshot=has_snapshot,
            has_fig_data=has_fig_data,
            element_id=element_id,
            preview_id=preview_id,
            error_id=error_id,
            autogenerate_id=autogenerate_id,
            snapshot_store_id=snapshot_store_id,
        )

    _register_download(download_id, preview_id, format_id, filename, config=config)
    _register_copy_to_clipboard(copy_id, preview_id)

    for (btn_id, _label), action in zip(action_ids, actions, strict=False):
        _register_custom_action(
            btn_id=btn_id,
            preview_id=preview_id,
            snapshot_store_id=snapshot_store_id,
            config=config,
            callback=action.callback,
        )

    return wizard.div
