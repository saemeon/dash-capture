"""Auto-include vendored html2canvas.min.js.

When ``capture_element`` uses html2canvas_strategy, the JS library is
injected into the Dash app's ``index_string`` so the browser executes it
as part of the initial HTML response.  No CDN needed.
"""

from __future__ import annotations

from pathlib import Path

import dash

_ASSETS_DIR = Path(__file__).parent / "assets"
_MARKER = "<!--dcap-html2canvas-->"


def _read_html2canvas() -> str:
    js_path = _ASSETS_DIR / "html2canvas.min.js"
    if not js_path.exists():
        raise FileNotFoundError(
            f"html2canvas.min.js not found at {js_path}. "
            "The vendored file may be missing from the package installation."
        )
    return js_path.read_text()


def ensure_html2canvas(children: list) -> list:
    """Ensure html2canvas is loaded into the current Dash app's HTML head.

    Patches ``app.index_string`` once per app so the script is part of
    the initial HTML response (React does not execute ``<script>`` tags
    rendered inside the component tree).  ``children`` is returned
    unchanged — kept for API symmetry with the previous behavior.
    """
    try:
        app = dash.get_app()
    except Exception:
        return children

    if getattr(app, "_dcap_html2canvas_injected", False):
        return children

    js = _read_html2canvas()
    snippet = f"{_MARKER}<script>{js}</script>"
    if "{%scripts%}" in app.index_string:
        app.index_string = app.index_string.replace(
            "{%scripts%}", snippet + "{%scripts%}"
        )
    elif "</head>" in app.index_string:
        app.index_string = app.index_string.replace("</head>", snippet + "</head>")
    app._dcap_html2canvas_injected = True
    return children
