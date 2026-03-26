"""Brand Axes — define what your axes look like."""

from mpl_brandpacker import BrandAxes
from mpl_brandpacker.axes import patch_axes

from my_brand_example.colors import Colors
from my_brand_example.sizes import FontSizes


class MyAxes(BrandAxes):
    """Example branded Axes.

    Override matplotlib methods to apply your brand styling.
    List overridden method names in _brand_methods.
    """

    _brand_methods = ["set_xlabel", "set_ylabel"]

    def set_xlabel(self, label: str, **kw) -> None:
        defaults = {"fontsize": FontSizes.body, "color": Colors.dark}
        defaults.update(kw)
        self.mpl.set_xlabel(label, **defaults)

    def set_ylabel(self, label: str, **kw) -> None:
        defaults = {"fontsize": FontSizes.body, "color": Colors.dark}
        defaults.update(kw)
        self.mpl.set_ylabel(label, **defaults)


def set_style(ax, **kw) -> None:
    """Apply brand styling to axes after patching."""
    ax.grid(True, alpha=0.2, color=Colors.gray)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def make_ax(ax, **kw):
    """Patch a plain Axes with MyAxes methods + styling."""
    patch_axes(ax, MyAxes, style_fn=set_style, **kw)
    return ax
