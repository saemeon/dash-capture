# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Backwards-compatible re-exports — use ``dash_capture.capture`` instead."""

from dash_capture.capture import FromPlotly, capture_graph as graph_exporter

__all__ = ["FromPlotly", "graph_exporter"]
