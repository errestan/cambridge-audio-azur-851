"""Protocol round-trip tests (encode -> bytes -> decode).

These run without Home Assistant since the azur851 package is standalone.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="TODO: implement once protocol framing is defined")
def test_encode_decode_round_trip() -> None:
    """A command encoded and then decoded should preserve its fields."""
    raise NotImplementedError
