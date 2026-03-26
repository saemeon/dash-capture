"""Generic header/footer layout engine using invisible axes.

Provides ``Header`` and ``Footer`` that create invisible axes regions
at the top/bottom of a figure. The brand author gets a standard
matplotlib Axes to draw anything on — text, images, patches, lines.

Helpers for common patterns (stacked text, horizontal alignment) are
provided, but the brand author can use any matplotlib artist.

Example::

    from mpl_brandpacker.header import Header, Footer

    class MyFigure(BrandFigure):
        _brand_methods = ["set_title", "set_sources"]

        def set_title(self, title, **kw):
            h = Header.get_or_create(self, height=0.5)
            h.clear()
            h.text(title, y=0.7, fontsize=10, weight="bold")

        def set_sources(self, sources, **kw):
            f = Footer.get_or_create(self, height=0.3)
            f.clear()
            f.text(f"Source: {sources}", y=0.4, fontsize=6.5, color="#888")

The header/footer axes use axes coordinates (0-1 in both directions),
so positioning is relative to the header region, not the full figure.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure


class _Region:
    """Base class for Header and Footer — an invisible axes region on a figure."""

    _attr_name: str  # set by subclasses

    def __init__(self, fig: Figure, ax: Axes, height: float) -> None:
        self.fig = fig
        self.ax = ax
        self.height = height

    @classmethod
    def get_or_create(cls, fig: Figure, height: float = 0.4) -> "_Region":
        """Get existing region or create a new one.

        Parameters
        ----------
        fig :
            The figure to attach to.
        height :
            Height of the region in inches.
        """
        existing = getattr(fig, cls._attr_name, None)
        if existing is not None:
            return existing

        fig_w, fig_h = fig.get_size_inches()
        frac = height / fig_h

        rect = cls._compute_rect(frac)
        ax = fig.add_axes(rect)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        region = cls(fig, ax, height)
        setattr(fig, cls._attr_name, region)

        # Adjust main axes to make room
        cls._adjust_axes(fig, frac)

        return region

    @staticmethod
    def _compute_rect(frac: float) -> list[float]:
        raise NotImplementedError

    @staticmethod
    def _adjust_axes(fig: Figure, frac: float) -> None:
        """Shrink main axes to make room for the region."""
        for ax in fig.axes:
            if getattr(ax, "_is_brand_region", False):
                continue
            pos = ax.get_position()
            new_pos = _Region._shrink_pos(pos, frac, fig)
            ax.set_position(new_pos)

    @staticmethod
    def _shrink_pos(pos, frac, fig):
        raise NotImplementedError

    def clear(self) -> None:
        """Remove all artists from the region."""
        self.ax.clear()
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.axis("off")

    def text(
        self,
        s: str,
        x: float = 0.02,
        y: float = 0.5,
        ha: str = "left",
        va: str = "center",
        **kw: Any,
    ) -> Any:
        """Add text to the region.

        Coordinates are in axes-relative units (0-1).
        """
        return self.ax.text(x, y, s, ha=ha, va=va, transform=self.ax.transAxes, **kw)

    def add_artist(self, artist: Any) -> Any:
        """Add any matplotlib artist to the region."""
        return self.ax.add_artist(artist)

    def imshow(self, img, **kw) -> Any:
        """Display an image in the region (e.g. a logo)."""
        return self.ax.imshow(img, **kw)


class Header(_Region):
    """Invisible axes at the top of the figure.

    Example::

        h = Header.get_or_create(fig, height=0.5)
        h.text("Title", y=0.7, fontsize=10, weight="bold")
        h.text("Subtitle", y=0.3, fontsize=8, color="#888")
        h.ax.axhline(0.05, color="black", linewidth=2)  # accent line
    """

    _attr_name = "_brand_header"

    @staticmethod
    def _compute_rect(frac: float) -> list[float]:
        # [left, bottom, width, height] — top strip of figure
        return [0, 1 - frac, 1, frac]

    @staticmethod
    def _shrink_pos(pos, frac, fig):
        # Push axes down to make room at top
        return [pos.x0, pos.y0, pos.width, pos.height - frac]

    @classmethod
    def _adjust_axes(cls, fig, frac):
        for ax in fig.axes:
            if getattr(ax, "_is_brand_region", False):
                continue
            pos = ax.get_position()
            ax.set_position([pos.x0, pos.y0, pos.width, pos.height - frac])
        # Mark the header axes
        header = getattr(fig, cls._attr_name)
        header.ax._is_brand_region = True


class Footer(_Region):
    """Invisible axes at the bottom of the figure.

    Example::

        f = Footer.get_or_create(fig, height=0.3)
        f.text("Source: Bloomberg", y=0.5, fontsize=6.5, color="#888")
    """

    _attr_name = "_brand_footer"

    @staticmethod
    def _compute_rect(frac: float) -> list[float]:
        # [left, bottom, width, height] — bottom strip of figure
        return [0, 0, 1, frac]

    @staticmethod
    def _shrink_pos(pos, frac, fig):
        # Push axes up to make room at bottom
        return [pos.x0, pos.y0 + frac, pos.width, pos.height - frac]

    @classmethod
    def _adjust_axes(cls, fig, frac):
        for ax in fig.axes:
            if getattr(ax, "_is_brand_region", False):
                continue
            pos = ax.get_position()
            ax.set_position([pos.x0, pos.y0 + frac, pos.width, pos.height - frac])
        footer = getattr(fig, cls._attr_name)
        footer.ax._is_brand_region = True
