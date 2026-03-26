"""Base classes for brand sizes: figure sizes, font sizes, and scaling.

Provides:

- ``FigsizesBase`` — validated (width, height) tuples in inches
- ``SizesBase`` — named font sizes (points) with scaling support
- ``figsize_context()`` — context manager that temporarily scales fonts for a given figsize

Example::

    from mpl_brandpacker.sizes import FigsizesBase, SizesBase, MM_TO_INCH

    class Sizes(FigsizesBase):
        publication_half = (88 * MM_TO_INCH, 76 * MM_TO_INCH)
        presentation_full = (314 * MM_TO_INCH, 130 * MM_TO_INCH)

    class FontSizes(SizesBase):
        title = 10
        subtitle = 8
        body = 8
        footer = 6.5

    # Scale fonts 2x for presentations:
    FontSizes.add_scaler("presentation_full", 2.0)

    with FontSizes.figsize_context("presentation_full"):
        # FontSizes.title → 20, FontSizes.body → 16, etc.
        ...
"""

from __future__ import annotations

import contextlib
from typing import Any

import matplotlib.pyplot as plt

from mpl_brandpacker.utils import PrintableEnum

MM_TO_INCH = 1 / 25.4
"""Multiply mm values by this to get inches."""

POINTS_TO_INCH = 1 / 72
"""Multiply point values by this to get inches."""


# ---------------------------------------------------------------------------
# FigsizesBase
# ---------------------------------------------------------------------------


class FigsizesBase(tuple, PrintableEnum):
    """Base class for brand figure sizes. All values must be ``(width, height)`` in inches.

    Call ``MySizes.plot()`` to display a visual comparison.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for name, member in cls.__members__.items():
            val = member.value
            if (
                not isinstance(val, tuple)
                or len(val) != 2
                or not all(isinstance(v, (int, float)) for v in val)
            ):
                raise ValueError(
                    f"{cls.__name__}.{name} = {val!r} must be a (width, height) "
                    f"tuple of numbers in inches (e.g. (6.0, 4.0))."
                )

    @classmethod
    def plot(cls, figsize=None):
        """Display a visual comparison of all figure sizes."""
        import matplotlib.patches as patches

        names = list(cls.__members__.keys())
        sizes = [cls[n].value for n in names]
        max_w = max(w for w, h in sizes)

        if figsize is None:
            fig_w = max_w * 0.25 + 4
            fig_h = sum(h * 0.25 + 0.15 for _, h in sizes) + 0.5
            figsize = (fig_w, fig_h)

        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(cls.__name__, fontsize=12, weight="bold", loc="left")
        ax.axis("off")

        y = 0
        for name, (w, h) in zip(names, sizes):
            sw, sh = w * 0.25, h * 0.25
            rect = patches.Rectangle(
                (0.1, y),
                sw,
                sh,
                facecolor="#e8e8e8",
                edgecolor="#888",
                linewidth=0.8,
            )
            ax.add_patch(rect)
            ax.text(
                sw + 0.3,
                y + sh / 2,
                f"{name}  ({w:.1f} x {h:.1f} in)",
                fontsize=8,
                va="center",
            )
            y += sh + 0.15

        ax.set_xlim(-0.1, max_w * 0.25 + 5)
        ax.set_ylim(-0.1, y + 0.1)
        fig.tight_layout()
        return fig


# ---------------------------------------------------------------------------
# SizesBase
# ---------------------------------------------------------------------------


class SizesBase:
    """Base class for brand font sizes with per-figsize scaling.

    Define font sizes as class attributes (in points) and ``_scalers``
    as a dict mapping names to scaling specs.

    Scaler values can be:

    - A number: scale ALL attributes by that factor
    - A tuple ``(factor, [attrs])``: scale only the listed attributes
    - A tuple ``(factor, None)``: same as just a number (scale all)

    Example::

        class FontSizes(SizesBase):
            title = 10
            subtitle = 8
            body = 8
            footer = 6.5

            _scalers = {
                "presentation": (2.0, ["title", "subtitle", "body"]),  # footer stays
                "mobile": 0.67,                                         # scale all
            }

        with FontSizes.scaled("presentation"):
            print(FontSizes.title)   # → 20
            print(FontSizes.footer)  # → 6.5 (unchanged)

        with FontSizes.scaled(1.5):
            print(FontSizes.title)   # → 15
    """

    _scalers: dict[str, float | tuple[float, list[str] | None]] = {}
    _originals: dict[str, float] = {}
    _active_scaler: float | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "_scalers" not in cls.__dict__:
            cls._scalers = dict(getattr(cls, "_scalers", {}))
        cls._originals = {}
        cls._active_scaler = None

    @classmethod
    def add_scaler(
        cls,
        name: str,
        factor: float,
        attrs: list[str] | None = None,
    ) -> None:
        """Register a scaling factor at runtime.

        Parameters
        ----------
        name :
            Scaler name (e.g. ``"presentation"``).
        factor :
            Multiply selected attributes by this.
        attrs :
            Attributes to scale. ``None`` means all.
        """
        cls._scalers[name] = (factor, attrs) if attrs is not None else factor

    @classmethod
    @contextlib.contextmanager
    def scaled(cls, factor_or_name: str | float):
        """Temporarily scale font sizes.

        Parameters
        ----------
        factor_or_name :
            A scaling factor (e.g. ``2.0``) or a name from ``_scalers``.

        Example::

            with FontSizes.scaled("presentation"):
                # title/subtitle/body scaled, footer unchanged

            with FontSizes.scaled(0.5):
                # all sizes halved
        """
        if isinstance(factor_or_name, (int, float)):
            scaler = float(factor_or_name)
            affected = None
        else:
            spec = cls._scalers.get(factor_or_name, 1.0)
            if isinstance(spec, tuple):
                scaler, affected = spec
            else:
                scaler, affected = float(spec), None

        # Save originals and scale
        all_attrs = _get_size_attrs(cls)
        target_attrs = affected if affected is not None else all_attrs

        cls._originals = {}
        for name in all_attrs:
            original = getattr(cls, name)
            cls._originals[name] = original
            if name in target_attrs:
                setattr(cls, name, original * scaler)

        cls._active_scaler = scaler
        try:
            yield
        finally:
            for name, original in cls._originals.items():
                setattr(cls, name, original)
            cls._active_scaler = None
            cls._originals = {}


def _get_size_attrs(cls: type) -> list[str]:
    """Get all numeric class attributes (the font size definitions)."""
    return [
        name
        for name in vars(cls)
        if not name.startswith("_") and isinstance(getattr(cls, name), (int, float))
    ]
