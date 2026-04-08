# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture.strategies — JS fragment generation."""

import re
import shutil
import subprocess

import pytest

from dash_capture.strategies import (
    CaptureStrategy,
    _build_strip_patches,
    build_capture_js,
    canvas_strategy,
    html2canvas_strategy,
    plotly_strategy,
)

# ---------------------------------------------------------------------------
# CaptureStrategy dataclass
# ---------------------------------------------------------------------------


class TestCaptureStrategy:
    def test_defaults(self):
        s = CaptureStrategy()
        assert s.preprocess is None
        assert s.capture == ""
        assert s.format == "png"

    def test_custom_js(self):
        s = CaptureStrategy(
            preprocess="el.style.background = 'white';",
            capture="return el.toDataURL();",
        )
        assert "background" in s.preprocess
        assert "toDataURL" in s.capture

    def test_custom_format(self):
        s = CaptureStrategy(format="jpeg")
        assert s.format == "jpeg"


# ---------------------------------------------------------------------------
# Strip patches
# ---------------------------------------------------------------------------


class TestBuildStripPatches:
    def test_no_strips(self):
        assert _build_strip_patches() == []

    def test_strip_title(self):
        patches = _build_strip_patches(strip_title=True)
        assert len(patches) == 2
        assert any("title" in p for p in patches)
        assert any("margin" in p for p in patches)

    def test_strip_legend(self):
        patches = _build_strip_patches(strip_legend=True)
        assert patches == ["layout.showlegend = false;"]

    def test_strip_annotations(self):
        patches = _build_strip_patches(strip_annotations=True)
        assert patches == ["layout.annotations = [];"]

    def test_strip_axis_titles(self):
        patches = _build_strip_patches(strip_axis_titles=True)
        assert len(patches) == 1
        assert "xaxis" in patches[0] or "xy" in patches[0]

    def test_strip_colorbar(self):
        patches = _build_strip_patches(strip_colorbar=True)
        assert "showscale" in patches[0]

    def test_strip_margin(self):
        patches = _build_strip_patches(strip_margin=True)
        assert "l:0" in patches[0]

    def test_all_strips(self):
        patches = _build_strip_patches(
            strip_title=True,
            strip_legend=True,
            strip_annotations=True,
            strip_axis_titles=True,
            strip_colorbar=True,
            strip_margin=True,
        )
        combined = " ".join(patches)
        assert "title" in combined
        assert "showlegend" in combined
        assert "annotations" in combined
        assert "showscale" in combined
        assert "l:0" in combined


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------


class TestPlotlyStrategy:
    def test_no_strips_simple_capture(self):
        s = plotly_strategy()
        assert s.preprocess is None
        assert "Plotly.toImage" in s.capture

    def test_with_strips_has_preprocess(self):
        s = plotly_strategy(strip_title=True)
        assert s.preprocess is not None
        assert "newPlot" in s.preprocess
        assert "tmp" in s.preprocess

    def test_with_strips_capture_uses_tmp(self):
        s = plotly_strategy(strip_legend=True)
        assert "_dcap_tmp" in s.capture

    def test_capture_width_in_params(self):
        s = plotly_strategy(strip_title=True, _params={"capture_width": None})
        assert "capture_width" in s.preprocess

    def test_no_capture_width(self):
        s = plotly_strategy(strip_title=True, _params={})
        assert "capture_width" not in s.preprocess

    def test_format_default_png(self):
        s = plotly_strategy()
        assert s.format == "png"

    def test_format_jpeg(self):
        s = plotly_strategy(format="jpeg")
        assert s.format == "jpeg"

    def test_format_svg(self):
        s = plotly_strategy(format="svg")
        assert s.format == "svg"


class TestHtml2canvasStrategy:
    def test_capture_js(self):
        s = html2canvas_strategy()
        assert s.preprocess is None
        assert "html2canvas" in s.capture
        assert "toDataURL" in s.capture

    def test_error_message_for_missing_lib(self):
        s = html2canvas_strategy()
        assert "not loaded" in s.capture

    def test_format_default_png(self):
        s = html2canvas_strategy()
        assert s.format == "png"

    def test_format_jpeg(self):
        s = html2canvas_strategy(format="jpeg")
        assert s.format == "jpeg"

    def test_capture_uses_mime_from_opts(self):
        s = html2canvas_strategy()
        assert "opts.format" in s.capture


class TestCanvasStrategy:
    def test_capture_js(self):
        s = canvas_strategy()
        assert s.preprocess is None
        assert "toDataURL" in s.capture
        assert "canvas" in s.capture.lower()

    def test_format_default_png(self):
        s = canvas_strategy()
        assert s.format == "png"

    def test_format_webp(self):
        s = canvas_strategy(format="webp")
        assert s.format == "webp"


# ---------------------------------------------------------------------------
# JS assembly
# ---------------------------------------------------------------------------


class TestBuildCaptureJs:
    def test_simple_plotly(self):
        s = plotly_strategy()
        js = build_capture_js("my-graph", s, [], {})
        assert "async function" in js
        assert "my-graph" in js
        assert "no_update" in js
        assert "Plotly.toImage" in js

    def test_with_strip_patches(self):
        s = plotly_strategy(strip_title=True)
        js = build_capture_js("g", s, [], {})
        assert "newPlot" in js
        assert "title" in js

    def test_active_capture_params(self):
        s = plotly_strategy()
        js = build_capture_js("g", s, ["capture_width", "capture_height"], {})
        assert "capture_width" in js
        assert "capture_height" in js
        assert "opts.width" in js
        assert "opts.height" in js

    def test_html2canvas_strategy(self):
        s = html2canvas_strategy()
        js = build_capture_js("my-div", s, [], {})
        assert "html2canvas" in js
        assert "my-div" in js

    def test_custom_strategy(self):
        s = CaptureStrategy(
            preprocess="el.classList.add('capturing');",
            capture="return await customCapture(el);",
        )
        js = build_capture_js("el-id", s, [], {})
        assert "capturing" in js
        assert "customCapture" in js

    def test_custom_preprocess_only(self):
        s = CaptureStrategy(
            preprocess="console.log('pre');",
            capture="return 'data:image/png;base64,abc';",
        )
        js = build_capture_js("x", s, [], {})
        assert "console.log" in js
        assert "base64,abc" in js

    def test_format_in_opts(self):
        s = plotly_strategy(format="svg")
        js = build_capture_js("g", s, [], {})
        assert "fmt || 'svg'" in js

    def test_format_jpeg_in_opts(self):
        s = html2canvas_strategy(format="jpeg")
        js = build_capture_js("g", s, [], {})
        assert "fmt || 'jpeg'" in js

    def test_element_id_escaping(self):
        s = plotly_strategy()
        js = build_capture_js("test'; alert('xss');//", s, [], {})
        assert "alert" in js  # string is present but escaped
        assert "\\'" in js  # single quote is escaped


# ---------------------------------------------------------------------------
# JS validity (regression guards)
# ---------------------------------------------------------------------------


def _extract_function_params(js: str) -> list[str]:
    """Extract parameter names from the first ``async function(...)`` line."""
    m = re.search(r"async function\s*\(([^)]*)\)", js)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",")]


def _find_const_let_var_redeclarations(js: str, params: list[str]) -> list[str]:
    """Return any ``const|let|var <param>`` declarations colliding with params."""
    # Word-boundary match for `const p`, `let p`, `var p`
    return [
        p for p in params if re.search(rf"\b(?:const|let|var)\s+{re.escape(p)}\b", js)
    ]


def _all_built_in_strategy_js() -> list[tuple[str, str]]:
    """Return ``(label, js)`` pairs for every built-in strategy combo.

    Covers the strategy ``x`` format ``x`` strip-patch matrix that
    ``build_capture_js`` actually emits in production.
    """
    cases: list[tuple[str, str]] = []
    for label, strat in [
        ("plotly_simple", plotly_strategy()),
        ("plotly_jpeg", plotly_strategy(format="jpeg")),
        ("plotly_svg", plotly_strategy(format="svg")),
        ("plotly_strip_title", plotly_strategy(strip_title=True)),
        (
            "plotly_strip_all",
            plotly_strategy(
                strip_title=True,
                strip_legend=True,
                strip_annotations=True,
                strip_axis_titles=True,
                strip_colorbar=True,
                strip_margin=True,
            ),
        ),
        ("html2canvas", html2canvas_strategy()),
        ("html2canvas_jpeg", html2canvas_strategy(format="jpeg")),
        ("canvas", canvas_strategy()),
        ("canvas_webp", canvas_strategy(format="webp")),
    ]:
        # Two flavors per strategy: with and without active capture params
        cases.append((label, build_capture_js("test-id", strat, [], {})))
        cases.append(
            (
                f"{label}+capture_params",
                build_capture_js(
                    "test-id", strat, ["capture_width", "capture_height"], {}
                ),
            )
        )
    return cases


class TestGeneratedJsValidity:
    """Regression guards for the generated clientside-callback JS.

    Two layers:

    1. **Identifier-collision guard** (always runs, no deps): catches the
       specific bug class where a function parameter name is also
       redeclared with ``const`` / ``let`` / ``var`` inside the body.
       Concrete example: the ``fmt`` collision in ``_HTML2CANVAS_CAPTURE``
       and ``_CANVAS_CAPTURE`` introduced when the format dropdown started
       passing ``fmt`` as a clientside-callback argument.

    2. **Full syntax check via Node** (skipped if node not on PATH):
       compiles the JS body with ``new Function(...)`` and reports any
       SyntaxError. Catches anything else the regex might miss.
    """

    @pytest.mark.parametrize(
        "label,js",
        _all_built_in_strategy_js(),
        ids=lambda x: x if isinstance(x, str) else "",
    )
    def test_no_param_redeclarations(self, label: str, js: str):
        params = _extract_function_params(js)
        assert params, f"{label}: failed to extract params from generated JS"
        offenders = _find_const_let_var_redeclarations(js, params)
        assert not offenders, (
            f"{label}: parameters {offenders} are redeclared as const/let/var "
            f"inside the function body — this is a SyntaxError in strict mode "
            f"and silently breaks the clientside callback."
            f"\n\nGenerated JS:\n{js}"
        )

    @pytest.mark.skipif(
        shutil.which("node") is None,
        reason="node executable not available — skipping JS syntax check",
    )
    @pytest.mark.parametrize(
        "label,js",
        _all_built_in_strategy_js(),
        ids=lambda x: x if isinstance(x, str) else "",
    )
    def test_parses_in_node(self, tmp_path, label: str, js: str):
        # Wrap the bare `async function(...) {}` as a function expression
        # assigned to a variable so it parses as a top-level statement.
        # `node --check` only validates syntax, no execution.
        source = f"const _f = {js.strip()};\n"
        f = tmp_path / "snippet.js"
        f.write_text(source)
        result = subprocess.run(
            ["node", "--check", str(f)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"{label}: generated JS failed to parse in node.\n"
            f"stderr: {result.stderr}\n\nGenerated JS:\n{source}"
        )


# ---------------------------------------------------------------------------
# Batch capture
# ---------------------------------------------------------------------------


class TestMultipleBindings:
    def test_multiple_bindings_unique_store_ids(self):
        from dash_capture import capture_binding

        b1 = capture_binding("a")
        b2 = capture_binding("b")
        assert b1.store_id != b2.store_id

    def test_multiple_bindings_with_strategy(self):
        from dash_capture import capture_binding

        b1 = capture_binding("x", strategy=plotly_strategy(strip_title=True))
        b2 = capture_binding("y", strategy=plotly_strategy(strip_title=True))
        assert b1.store_id != b2.store_id


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------


def test_import():
    import dash_capture

    assert hasattr(dash_capture, "CaptureStrategy")
    assert hasattr(dash_capture, "plotly_strategy")
    assert hasattr(dash_capture, "html2canvas_strategy")
    assert hasattr(dash_capture, "canvas_strategy")
    assert hasattr(dash_capture, "capture_element")
    assert hasattr(dash_capture, "capture_graph")
    assert hasattr(dash_capture, "capture_binding")
    assert hasattr(dash_capture, "CaptureBinding")
