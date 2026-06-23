"""Command and response definitions for the Azur 851 protocol.

Maps logical operations (power on, set volume, select source, query status) to the
concrete command groups/numbers from the RS-232 specification.

TODO: Populate from the official Azur 851 RS-232 command reference. The values
below are placeholders to illustrate the intended shape.
"""

from __future__ import annotations

from enum import IntEnum

from .protocol import Command


class Group(IntEnum):
    """Command groups. TODO: replace with real values from the spec."""

    POWER = 0
    SOURCE = 0
    VOLUME = 0
    STATUS = 0


def power(on: bool) -> Command:
    """Build a power on/standby command."""
    raise NotImplementedError


def set_volume(raw_level: int) -> Command:
    """Build a set-volume command from a device-native level."""
    raise NotImplementedError


def mute(on: bool) -> Command:
    """Build a mute on/off command."""
    raise NotImplementedError


def select_source(source_code: int) -> Command:
    """Build a select-source command from a device-native source code."""
    raise NotImplementedError


def query_status() -> Command:
    """Build a command that requests the full device status."""
    raise NotImplementedError
