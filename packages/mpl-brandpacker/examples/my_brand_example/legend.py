"""Horizontal legend placement — above or below axes.

Provides helpers for placing legends horizontally outside the axes,
which is a common requirement in corporate/publication charts.

Usage::

    from mpl_brandpacker.legend import legend_below, legend_above

    # On axes
    legend_below(ax)
    legend_above(ax, ncol=3)

    # On figure (combining multiple axes)
    legend_below(fig, axes=[ax1, ax2])
"""

from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.legend import Legend


def legend_below(
    target: Axes | Figure,
    *,
    axes: list[Axes] | None = None,
    ncol: int | str = "auto",
    spacing: float = 0.08,
    handles=None,
    labels=None,
    make_unique: bool = False,
    **legend_kw,
) -> Legend:
    """Place a horizontal legend below the axes or figure.

    Parameters
    ----------
    target :
        Axes or Figure to attach the legend to.
    axes :
        For figure legends: list of axes whose handles/labels to combine.
        If None and target is a Figure, uses all axes.
    ncol :
        Number of columns. ``"auto"`` fits all items in one row.
    spacing :
        Space between axes bottom and legend top, in inches.
    handles, labels :
        Explicit handles/labels. If None, collected from axes.
    make_unique :
        If True, keep only the last handle per label (useful when
        the same line appears in multiple subplots).
    **legend_kw :
        Passed to ``ax.legend()`` or ``fig.legend()``.
    """
    h, l = _collect_handles_labels(target, axes, handles, labels, make_unique)
    if not h:
        return None

    n = len(h) if ncol == "auto" else ncol

    defaults = {
        "loc": "upper center",
        "bbox_to_anchor": (0.5, -spacing),
        "bbox_transform": _get_transform(target),
        "ncol": n,
        "frameon": False,
        "borderaxespad": 0,
    }
    defaults.update(legend_kw)

    if isinstance(target, Figure):
        return target.legend(h, l, **defaults)
    return target.legend(h, l, **defaults)


def legend_above(
    target: Axes | Figure,
    *,
    axes: list[Axes] | None = None,
    ncol: int | str = "auto",
    spacing: float = 0.08,
    handles=None,
    labels=None,
    make_unique: bool = False,
    **legend_kw,
) -> Legend:
    """Place a horizontal legend above the axes or figure.

    Parameters are the same as :func:`legend_below`.
    """
    h, l = _collect_handles_labels(target, axes, handles, labels, make_unique)
    if not h:
        return None

    n = len(h) if ncol == "auto" else ncol

    defaults = {
        "loc": "lower center",
        "bbox_to_anchor": (0.5, 1.0 + spacing),
        "bbox_transform": _get_transform(target),
        "ncol": n,
        "frameon": False,
        "borderaxespad": 0,
    }
    defaults.update(legend_kw)

    if isinstance(target, Figure):
        return target.legend(h, l, **defaults)
    return target.legend(h, l, **defaults)


def _get_transform(target):
    if isinstance(target, Figure):
        return target.transFigure
    return target.transAxes


def _collect_handles_labels(target, axes, handles, labels, make_unique):
    """Collect handles and labels from target or explicit args."""
    if handles is not None and labels is not None:
        h, l = list(handles), list(labels)
    elif isinstance(target, Figure):
        all_axes = axes or target.axes
        h, l = [], []
        for ax in all_axes:
            ah, al = ax.get_legend_handles_labels()
            h.extend(ah)
            l.extend(al)
    else:
        h, l = target.get_legend_handles_labels()

    if make_unique:
        seen = {}
        for handle, label in zip(h, l):
            seen[label] = handle
        l = list(seen.keys())
        h = list(seen.values())

    return h, l
