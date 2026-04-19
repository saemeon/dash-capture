"""Auto-include vendored html2canvas.min.js.

When ``capture_element`` uses ``html2canvas_strategy``, the JS library is
registered via Dash's :data:`GLOBAL_INLINE_SCRIPTS` queue so Dash emits
it as an inline ``<script>`` tag on page serve. This is the same
mechanism ``@dash.callback`` / ``clientside_callback`` use to queue work
before any ``Dash`` instance exists — it lets callers build layout
fragments in independent modules and assemble the app later.
"""

from __future__ import annotations

from pathlib import Path

import dash
from dash._callback import GLOBAL_INLINE_SCRIPTS

_ASSETS_DIR = Path(__file__).parent / "assets"
_MARKER = "// __dcap_html2canvas__"


def _read_html2canvas() -> str:
    js_path = _ASSETS_DIR / "html2canvas.min.js"
    if not js_path.exists():
        raise FileNotFoundError(
            f"html2canvas.min.js not found at {js_path}. "
            "The vendored file may be missing from the package installation."
        )
    return js_path.read_text()


def ensure_html2canvas(children: list) -> list:
    """Register html2canvas with Dash's inline-script queue if not already.

    Idempotent within a Python process: the script is queued at most
    once. Safe to call before any :class:`dash.Dash` instance exists —
    Dash drains :data:`GLOBAL_INLINE_SCRIPTS` on the first page serve.

    ``children`` is returned unchanged; the list parameter is retained
    for API symmetry with the previous implementation.
    """
    # Already queued, not yet drained by any app?
    if any(_MARKER in s for s in GLOBAL_INLINE_SCRIPTS):
        return children
    # Already drained into a live app?
    try:
        app = dash.get_app()
    except Exception:
        app = None
    if app is not None and any(
        _MARKER in s for s in getattr(app, "_inline_scripts", [])
    ):
        return children
    GLOBAL_INLINE_SCRIPTS.append(f"{_MARKER}\n{_read_html2canvas()}")
    return children
