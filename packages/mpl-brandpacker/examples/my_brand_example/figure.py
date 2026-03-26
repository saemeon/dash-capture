"""Brand Figure — title, subtitle, sources, footnote.

Uses Header/Footer helper for layout and FontSizes for sizing.
"""

from mpl_brandpacker import BrandFigure
from mpl_brandpacker.figure import patch_figure

from my_brand_example.colors import Colors
from my_brand_example.header import Footer, Header
from my_brand_example.sizes import FontSizes


class MyFigure(BrandFigure):
    """Example branded Figure using Header/Footer regions."""

    _brand_methods = ["set_title", "set_subtitle", "set_sources", "set_footnote"]

    def set_title(self, title: str, **kw) -> None:
        self._brand_title = title
        h = Header.get_or_create(self, height=0.5)
        h.clear()
        h.ax.axhline(0.95, xmin=0, xmax=0.12, color=Colors.primary, linewidth=4)
        h.text(title, y=0.6, fontsize=FontSizes.title, weight="bold", color=Colors.dark, **kw)
        subtitle = getattr(self, "_brand_subtitle", None)
        if subtitle:
            h.text(subtitle, y=0.15, fontsize=FontSizes.subtitle, color=Colors.gray)

    def set_subtitle(self, subtitle: str, **kw) -> None:
        self._brand_subtitle = subtitle
        title = getattr(self, "_brand_title", None)
        if title:
            self.set_title(title)
        else:
            h = Header.get_or_create(self, height=0.5)
            h.text(subtitle, y=0.5, fontsize=FontSizes.subtitle, color=Colors.gray, **kw)

    def set_sources(self, sources: str, **kw) -> None:
        self._brand_sources = sources
        f = Footer.get_or_create(self, height=0.25)
        f.clear()
        f.text(f"Source: {sources}", y=0.5, fontsize=FontSizes.footer, color=Colors.gray, **kw)
        footnote = getattr(self, "_brand_footnote", None)
        if footnote:
            f.text(footnote, x=0.98, y=0.5, ha="right", fontsize=FontSizes.footer, color=Colors.gray)

    def set_footnote(self, footnote: str, **kw) -> None:
        self._brand_footnote = footnote
        sources = getattr(self, "_brand_sources", None)
        if sources:
            self.set_sources(sources)
        else:
            f = Footer.get_or_create(self, height=0.25)
            f.text(footnote, x=0.98, y=0.5, ha="right", fontsize=FontSizes.footer, color=Colors.gray, **kw)


def make_fig(fig):
    """Patch a plain Figure with MyFigure methods."""
    from my_brand_example.axes import make_ax

    patch_figure(fig, MyFigure, make_ax=make_ax)
    return fig
