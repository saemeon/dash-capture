# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.


class _IdGenerator:
    """Package-wide unique Dash component ID generator.

    Generates IDs of the form ``_s5ndt_<prefix>_<n>`` where *n* is a
    monotonically increasing integer, unique across the entire s5ndt package.

    Use the package-level singleton :data:`id_generator`.
    """

    def __init__(self) -> None:
        self._counter = 0

    def __call__(self, prefix: str = "") -> str:
        self._counter += 1
        return f"_s5ndt_{prefix}_{self._counter}" if prefix else f"_s5ndt_{self._counter}"


id_generator = _IdGenerator()
