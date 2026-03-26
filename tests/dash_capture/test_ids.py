# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture._ids — unique ID generation."""

from dash_capture._ids import _IdGenerator


class TestIdGenerator:
    def test_increments(self):
        gen = _IdGenerator()
        a = gen()
        b = gen()
        assert a != b

    def test_format_without_prefix(self):
        gen = _IdGenerator()
        result = gen()
        assert result.startswith("_dcap_")
        # No double underscore from empty prefix
        assert "__" not in result

    def test_format_with_prefix(self):
        gen = _IdGenerator()
        result = gen("foo")
        assert "_dcap_foo_" in result

    def test_monotonic(self):
        gen = _IdGenerator()
        ids = [gen("x") for _ in range(5)]
        # Extract trailing integer
        nums = [int(i.rsplit("_", 1)[1]) for i in ids]
        assert nums == sorted(nums)
        assert len(set(nums)) == 5

    def test_unique_across_prefixes(self):
        gen = _IdGenerator()
        a = gen("alpha")
        b = gen("beta")
        assert a != b

    def test_module_singleton(self):
        from dash_capture._ids import id_generator

        assert isinstance(id_generator, _IdGenerator)
        # Calling it returns a string
        result = id_generator("test")
        assert isinstance(result, str)
