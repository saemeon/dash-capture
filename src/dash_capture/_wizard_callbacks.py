# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Wizard callback registration — each callback is a named function."""

from __future__ import annotations

import base64
import io
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, cast

import dash
from dash import Input, Output, State, dcc, html
from dash_fn_form import FnForm, field_id
from dash_fn_form._spec import _FieldFixed

from dash_capture._dropdown import build_dropdown
from dash_capture._wizard import build_wizard
from dash_capture._wizard_layout import build_modal_body
from dash_capture.strategies import CaptureStrategy, build_capture_js

if TYPE_CHECKING:
    # Avoid runtime circular import: capture.py imports wire_wizard from
    # this module, and this module needs WizardConfig only as a type hint.
    from dash_capture.capture import WizardConfig


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


# ---------------------------------------------------------------------------
# Callback registration
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
    generate_id: str,
    interval_id: str,
    autogenerate_id: str,
    format_id: str,
    capture_resolver: Callable,
) -> None:
    """Wire the two-step flow: server resolves capture opts, then JS captures."""
    _resolve_inputs = [
        Input(s.component_id, s.component_property) for s in config.states
    ]

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
        *field_values, autogen, snapshot = args
        is_generate = dash.ctx.triggered_id in (generate_id, interval_id)
        if not is_generate and (not autogen or not snapshot):
            return dash.no_update
        kwargs = config.build_kwargs(tuple(field_values))
        return capture_resolver(**kwargs)

    capture_js = build_capture_js(element_id, strategy, [], params, from_resolved=True)
    dash.clientside_callback(
        capture_js,
        Output(snapshot_store_id, "data"),
        Input(resolved_store_id, "data"),
        State(format_id, "value"),
        prevent_initial_call=True,
    )


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
            _register_capture_resolved(
                element_id=element_id,
                strategy=strategy,
                params=params,
                config=config,
                resolved_store_id=resolved_store_id,
                snapshot_store_id=snapshot_store_id,
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
