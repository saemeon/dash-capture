# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""SVG icon primitives for Dash buttons."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from dash import html


@dataclass
class SvgIcon:
    """SVG icon definition.

    Parameters
    ----------
    path : str
        SVG ``<path d="...">`` data. Ignored if *svg_content* is set.
    svg_content : str
        Raw SVG inner markup for complex icons (multiple paths, text, etc.).
    width, height : int
        ViewBox dimensions (default 1000 x 1000, matching Plotly icons).
    transform : str
        Optional SVG transform applied to the path.

    Examples
    --------
    >>> from dash_capture import SvgIcon
    >>> icon = SvgIcon(path="M500 0 L1000 1000 L0 1000 Z")
    """

    path: str = ""
    svg_content: str = ""
    width: int = 1000
    height: int = 1000
    transform: str = ""

    def to_svg_inner(self) -> str:
        """Return SVG inner markup."""
        if self.svg_content:
            return self.svg_content
        transform = f' transform="{self.transform}"' if self.transform else ""
        return f'<path fill="currentColor" d="{self.path}"{transform}/>'


def icon_button(
    icon: SvgIcon,
    button_id: str,
    *,
    tooltip: str = "",
    height: int = 20,
) -> html.Button:
    """Render a :class:`SvgIcon` as a standalone Dash button.

    Height is fixed, width computed from the icon's viewBox aspect ratio.
    The SVG is embedded as a data URI on ``html.Img`` — works on any Dash
    version.

    Parameters
    ----------
    icon : SvgIcon
        The icon definition to render.
    button_id : str
        ``id`` of the resulting ``html.Button``.
    tooltip : str
        ``title`` attribute (hover tooltip).
    height : int
        Icon height in pixels (default 20, matching the Plotly modebar).

    Examples
    --------
    >>> from dash_capture import SvgIcon, icon_button
    >>> icon = SvgIcon(path="M500 0 L1000 1000 L0 1000 Z")
    >>> btn = icon_button(icon, "my-btn", tooltip="Export")
    """
    width = round(height * icon.width / icon.height)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {icon.width} {icon.height}" '
        f'width="{width}" height="{height}">'
        f"{icon.to_svg_inner()}</svg>"
    )
    return html.Button(
        id=button_id,
        n_clicks=0,
        title=tooltip,
        children=html.Img(
            src="data:image/svg+xml;utf8," + quote(svg),
            height=height,
            style={"display": "block"},
        ),
        style={
            "background": "rgba(255,255,255,0.85)",
            "border": "1px solid #ccc",
            "borderRadius": "4px",
            "padding": "4px 6px",
            "cursor": "pointer",
            "pointerEvents": "auto",
        },
    )
