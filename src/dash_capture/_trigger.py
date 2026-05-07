# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Trigger configuration for capture wizards."""

from __future__ import annotations

from dataclasses import dataclass

from dash_capture._icons import SvgIcon


@dataclass
class CaptureButton:
    """Trigger configuration for a capture wizard.

    Used as the ``trigger=`` argument to :func:`capture_graph` and
    :func:`capture_element`. When passed to ``capture_graph``, the icon
    and label are injected into the Plotly modebar.

    Parameters
    ----------
    icon : SvgIcon, optional
        SVG icon. When set, rendered as SVG instead of a text label.
    label : str
        Text/emoji label. Defaults to a camera emoji when neither
        *label* nor *icon* is set.
    tooltip : str
        Hover tooltip text (default ``"Capture"``).

    Examples
    --------
    >>> from dash_capture import CaptureButton, capture_graph
    >>> capture_graph("my-graph", trigger=CaptureButton(tooltip="Export"))
    """

    icon: SvgIcon | None = None
    label: str = ""
    tooltip: str = "Capture"
