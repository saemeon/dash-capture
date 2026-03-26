"""Brand sizes — figure dimensions, font sizes, and scalers."""

from mpl_brandpacker import FigsizesBase, SizesBase
from mpl_brandpacker.sizes import MM_TO_INCH


class Sizes(FigsizesBase):
    """Named figure sizes (width, height in inches)."""

    half = (88 * MM_TO_INCH, 76 * MM_TO_INCH)
    full = (181 * MM_TO_INCH, 76 * MM_TO_INCH)
    presentation = (314 * MM_TO_INCH, 130 * MM_TO_INCH)
    square = (4.0, 4.0)


class FontSizes(SizesBase):
    """Font sizes in points, with per-figsize scaling."""

    title = 10
    subtitle = 8
    body = 8
    footer = 6.5

    _scalers = {
        "presentation": 2.0,
        "half": 1.0,
        "full": 1.0,
    }
