# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""dash-interact — pyplot-style convenience layer for Dash.

Re-exports the full dash-fn-interact engine plus the page/singleton API::

    from dash_interact import page, interact, Page

    page.H1("My App")

    @page.interact
    def sine_wave(amplitude: float = 1.0, frequency: float = 2.0):
        ...

    page.run(debug=True)
"""

from dash_interact import page
from dash_interact.page import Page, add, current, interact, run

# Re-export dash-fn-interact engine for users who install only dash-interact
from dash_fn_interact import (
    Field,
    FieldHook,
    FieldMaker,
    FieldRef,
    FnForm,
    Form,
    FromComponent,
    build_fn_panel,
    field_id,
    fixed,
    make_dbc_field,
    make_dcc_field,
    make_dmc_field,
    register_renderer,
)

__all__ = [
    # page API
    "Page",
    "add",
    "current",
    "interact",
    "page",
    "run",
    # engine re-exports
    "Field",
    "FieldHook",
    "FieldMaker",
    "FieldRef",
    "FnForm",
    "Form",
    "FromComponent",
    "build_fn_panel",
    "field_id",
    "fixed",
    "make_dbc_field",
    "make_dcc_field",
    "make_dmc_field",
    "register_renderer",
]
