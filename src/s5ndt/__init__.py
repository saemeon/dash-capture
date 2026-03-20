# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.


from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mypackage")
except PackageNotFoundError:
    __version__ = "unknown"


from dash_fn_tools import FieldHook, FieldSpec, FromComponent, build_config
from s5ndt._ids import id_generator
from s5ndt.dropdown import build_dropdown
from s5ndt.fig_export import FromPlotly, graph_exporter
from s5ndt.wizard import Wizard, build_wizard

__all__ = [
    "FieldHook",
    "FieldSpec",
    "FromComponent",
    "FromPlotly",
    "Wizard",
    "build_config",
    "build_dropdown",
    "build_wizard",
    "graph_exporter",
    "id_generator",
]
