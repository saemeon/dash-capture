# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

"""Tests for dash_capture._ids — unique ID generation."""

from dash_capture._ids import _new_id


class TestNewId:
    def test_unique(self):
        a = _new_id()
        b = _new_id()
        assert a != b

    def test_format_without_prefix(self):
        result = _new_id()
        assert result.startswith("_dcap_")

    def test_format_with_prefix(self):
        result = _new_id("foo")
        assert "_dcap_foo_" in result

    def test_all_unique(self):
        ids = [_new_id("x") for _ in range(20)]
        assert len(set(ids)) == 20

    def test_unique_across_prefixes(self):
        a = _new_id("alpha")
        b = _new_id("beta")
        assert a != b

    def test_returns_string(self):
        assert isinstance(_new_id(), str)
        assert isinstance(_new_id("pfx"), str)
