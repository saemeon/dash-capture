import io
from datetime import date, datetime
from typing import Literal

import matplotlib.pyplot as plt
import plotly.graph_objects as go
from dash import Dash, dcc, html

from s5ndt import FromPlotly, fig_export_button

plt.switch_backend("agg")

app = Dash(__name__)

# --- figure ---

graph = dcc.Graph(
    id="main-graph",
    figure=go.Figure(
        go.Scatter(x=[1, 2, 3, 4, 5], y=[4, 2, 5, 1, 3], mode="markers"),
        layout={
            "title": {"text": "All-types example"},
            "xaxis": {"title": {"text": "X axis"}},
        },
    ),
)


# --- renderer: full custom (figure data, all wizard field types) ---
# Demonstrates: figure-data renderer (no browser capture), FromPlotly defaults,
# all supported wizard field types (str, int, float, bool, date, datetime,
# Literal, list, tuple).


def custom_renderer(
    _target,
    _fig_data,
    title: str = FromPlotly("layout.title.text", graph),  # type: ignore[assignment]
    xlabel: str = FromPlotly("layout.xaxis.title.text", graph),  # type: ignore[assignment]
    dpi: int = 100,
    alpha: float = 0.8,
    show_grid: bool = True,
    report_date: date | None = None,
    as_of: datetime | None = None,
    marker_style: Literal["o", "s", "^", "x"] = "o",
    y_ticks: list[float] | None = None,
    xlim: tuple[float, float] | None = None,
):
    x = _fig_data["data"][0]["x"]
    y = _fig_data["data"][0]["y"]

    fig, ax = plt.subplots(dpi=dpi)
    try:
        ax.scatter(x, y, alpha=alpha, marker=marker_style)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.grid(show_grid)

        if xlim:
            ax.set_xlim(*xlim)
        if y_ticks:
            ax.set_yticks(y_ticks)
        if report_date:
            fig.text(0, 0, str(report_date), fontsize=7)
        if as_of:
            ax.set_xlabel(f"as of {as_of.strftime('%Y-%m-%d %H:%M')}")

        fig.savefig(_target, format="png", bbox_inches="tight")
    finally:
        plt.close(fig)


# --- renderer: snapshot with matplotlib title overlay ---
# Demonstrates: _snapshot_img renderer, strip_title, FromPlotly default,
# capture_scale as wizard field forwarded to Plotly.toImage.


def snapshot_with_title(
    _target,
    _snapshot_img,
    title: str = FromPlotly("layout.title.text", graph),  # type: ignore[assignment]
    suptitle: str = "",
    capture_scale: int = 3,
):
    dpi = 300
    img = plt.imread(io.BytesIO(_snapshot_img()))
    h, w = img.shape[:2]
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    try:
        ax.imshow(img)
        ax.axis("off")
        if title:
            ax.set_title(title)
        if suptitle:
            fig.suptitle(suptitle)
        fig.savefig(_target, format="png", bbox_inches="tight", pad_inches=0)
    finally:
        plt.close(fig)


# --- renderer: custom snapshot with configurable capture dimensions ---
# Demonstrates: capture_width/height/scale as wizard fields forwarded to
# Plotly.toImage.


def snapshot_sized(
    _target,
    _snapshot_img,
    capture_width: int = 800,
    capture_height: int = 400,
    capture_scale: int = 3,
    dpi: int = 300,
):
    img = plt.imread(io.BytesIO(_snapshot_img()))
    h, w = img.shape[:2]
    fig, ax = plt.subplots(figsize=(w / dpi, h / dpi), dpi=dpi)
    try:
        fig.subplots_adjust(0, 0, 1, 1)
        ax.imshow(img)
        ax.axis("off")
        fig.savefig(_target, format="png", bbox_inches="tight", pad_inches=0)
    finally:
        plt.close(fig)


# --- layout ---

app.layout = html.Div(
    [
        graph,
        html.Div(
            style={"display": "flex", "gap": "8px", "flexWrap": "wrap"},
            children=[
                # 1. Default snapshot renderer — simplest usage, zero config.
                fig_export_button(
                    graph_id="main-graph",
                    label="Snapshot (default)",
                ),
                # 2. Custom figure-data renderer — rebuilds from raw data,
                #    no browser capture, all wizard field types.
                fig_export_button(
                    graph_id="main-graph",
                    renderer=custom_renderer,
                    label="Custom renderer",
                ),
                # 3. Snapshot with title overlay — strip Plotly chrome before
                #    capture; renderer redraws its own title.
                fig_export_button(
                    graph_id="main-graph",
                    renderer=snapshot_with_title,
                    label="Snapshot + title overlay",
                    strip_title=True,
                    strip_legend=True,
                    strip_axis_titles=True,
                    strip_margin=True,
                ),
                # 4. Configurable capture size — width/height/scale in the
                #    wizard steer both Plotly.toImage and the figure layout.
                fig_export_button(
                    graph_id="main-graph",
                    renderer=snapshot_sized,
                    label="Snapshot with capture params",
                ),
            ],
        ),
    ]
)

if __name__ == "__main__":
    app.run(debug=True, port=1234)
