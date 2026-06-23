"""Protocol round-trip and command-builder tests.

These exercise the standalone azur851 package and do not require Home Assistant.
"""

from __future__ import annotations

import pytest
from custom_components.cambridge_azur851.azur851 import commands
from custom_components.cambridge_azur851.azur851.exceptions import Azur851ProtocolError
from custom_components.cambridge_azur851.azur851.protocol import (
    Command,
    Response,
    decode,
    encode,
)


def test_encode_basic() -> None:
    """A command with data encodes to the documented frame."""
    assert encode(Command(1, 13, "10")) == b"#1,13,10\r"


def test_encode_pads_command_number() -> None:
    """The command number is always two digits."""
    assert encode(Command(1, 9)) == b"#1,09,\r"


def test_decode_basic() -> None:
    """A status frame decodes into its fields."""
    assert decode(b"#4,13,15\r") == Response(group=4, number=13, data="15")


def test_decode_tolerates_missing_data_separator() -> None:
    """Some models omit the trailing separator when there is no data."""
    assert decode(b"#4,11\r") == Response(group=4, number=11, data="")


def test_decode_preserves_commas_in_data() -> None:
    """Data fields (e.g. Set Input Name) may contain commas."""
    assert decode(b"#3,03,3,iPod\r") == Response(group=3, number=3, data="3,iPod")


def test_round_trip() -> None:
    """encode -> decode preserves group, number, and data."""
    command = Command(1, 13, "42")
    response = decode(encode(command))
    assert (response.group, response.number, response.data) == (1, 13, "42")


def test_error_frame_flagged() -> None:
    """Group-5 frames are reported as errors."""
    assert decode(b"#5,07,\r").is_error is True
    assert decode(b"#4,11,1\r").is_error is False


@pytest.mark.parametrize("bad", [b"1,11,0\r", b"#x,11\r", b"#1\r"])
def test_decode_rejects_malformed(bad: bytes) -> None:
    """Malformed frames raise a protocol error."""
    with pytest.raises(Azur851ProtocolError):
        decode(bad)


def test_power_and_mute_encoding() -> None:
    """Power is intuitive; mute control encoding is inverted (0 = mute on)."""
    assert encode(commands.power(True)) == b"#1,11,1\r"
    assert encode(commands.mute(True)) == b"#1,12,0\r"
    assert encode(commands.mute(False)) == b"#1,12,1\r"


def test_select_input_range() -> None:
    """Input selection validates its range."""
    assert encode(commands.select_input(2)) == b"#1,02,\r"
    assert encode(commands.select_input(1, balanced=True)) == b"#1,01,1\r"
    with pytest.raises(ValueError):
        commands.select_input(8)
