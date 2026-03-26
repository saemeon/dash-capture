"""my-brand — example branded matplotlib package.

Usage::

    import my_brand_example.pyplot as plt

    fig, ax = plt.subplots(figsize=my_brand_example.Sizes.half)
    ax.plot([1, 2, 3], [4, 5, 6], color=my_brand_example.Colors.primary)
    fig.set_title("Q4 Revenue")
    fig.set_sources("Internal Data")
    plt.show()

    # Scale fonts for a presentation:
    with my_brand_example.FontSizes.scaled("presentation"):
        fig, ax = plt.subplots(figsize=my_brand_example.Sizes.presentation)
        ...
"""

from pathlib import Path

import mpl_brandpacker

from my_brand_example.axes import MyAxes, make_ax, set_style
from my_brand_example.colors import Colors
from my_brand_example.figure import MyFigure, make_fig
from my_brand_example.sizes import FontSizes, Sizes

mpl_brandpacker.configure(
    figure_cls=MyFigure,
    axes_cls=MyAxes,
    style_fn=set_style,
    stylesheet=Path(__file__).parent,
)
