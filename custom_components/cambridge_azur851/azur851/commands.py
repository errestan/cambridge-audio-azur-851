"""Command/response definitions for the Azur 851 protocol.

Command numbers below are from the 851A Serial Control Protocol V1.0. The 851E
shares the layout but omits some commands and uses a different volume range; see
``models.py`` for per-model differences and ``docs/protocol.md`` for the full
reference.

Encoding gotcha: for the *control* Mute command (group 1, #12) the data is
inverted relative to intuition -- ``0`` means "mute ON", ``1`` means "mute OFF".
The corresponding *update* (group 4, #12) is the other way round. ``mute()`` and
``Update.parse_mute()`` below hide this.
"""

from __future__ import annotations

from enum import IntEnum

from .protocol import Command

# Main input selects map to control command numbers 1..7.
INPUT_MIN: int = 1
INPUT_MAX: int = 7


class Group(IntEnum):
    """Command groups."""

    CONTROL = 1  # commands we send to change state
    SETUP = 2  # commands we send to query/configure
    SETUP_REPLY = 3  # device replies to setup commands
    UPDATE = 4  # replies to control commands + unsolicited state updates
    ERROR = 5  # device error messages


class Control(IntEnum):
    """Group 1 control command numbers (851A)."""

    INPUT_1 = 1
    INPUT_2 = 2
    INPUT_3 = 3
    INPUT_4 = 4
    INPUT_5 = 5
    INPUT_6 = 6
    INPUT_7 = 7
    TAPE_MONITOR = 8
    INPUT_UP = 9
    INPUT_DOWN = 10
    POWER = 11
    MUTE = 12
    SET_VOLUME = 13
    VOLUME_UP = 14
    VOLUME_DOWN = 15
    VOLUME_STOP = 16
    SET_BALANCE = 17
    BALANCE_RIGHT = 18
    BALANCE_LEFT = 19
    LCD_BRIGHTNESS = 20
    SPEAKER_SELECT = 21  # 851A only
    SET_BASS = 24  # 851A only
    SET_TREBLE = 25  # 851A only
    SET_DIRECT = 26


class Setup(IntEnum):
    """Group 2 setup command numbers."""

    GET_SOFTWARE_VERSION = 1
    GET_PROTOCOL_VERSION = 2
    SET_INPUT_NAME = 3


# --- Control command builders ---------------------------------------------


def power(on: bool) -> Command:
    """Set power: on, or standby."""
    return Command(Group.CONTROL, Control.POWER, "1" if on else "0")


def mute(on: bool) -> Command:
    """Mute or unmute. NB control encoding is inverted (0 = mute on)."""
    return Command(Group.CONTROL, Control.MUTE, "0" if on else "1")


def set_volume(level: int) -> Command:
    """Set absolute volume to a device-native level (e.g. 0-96 on 851A)."""
    return Command(Group.CONTROL, Control.SET_VOLUME, f"{level:02d}")


def volume_up() -> Command:
    """Start ramping the volume up (until ``volume_stop``)."""
    return Command(Group.CONTROL, Control.VOLUME_UP)


def volume_down() -> Command:
    """Start ramping the volume down (until ``volume_stop``)."""
    return Command(Group.CONTROL, Control.VOLUME_DOWN)


def volume_stop() -> Command:
    """Stop an in-progress volume ramp."""
    return Command(Group.CONTROL, Control.VOLUME_STOP)


def select_input(index: int, balanced: bool = False) -> Command:
    """Select main input 1-7. ``balanced`` applies to inputs 1 & 2 only."""
    if not INPUT_MIN <= index <= INPUT_MAX:
        raise ValueError(f"input index out of range (1-7): {index}")
    return Command(Group.CONTROL, index, "1" if balanced else "")


def input_up() -> Command:
    """Step to the next input."""
    return Command(Group.CONTROL, Control.INPUT_UP)


def input_down() -> Command:
    """Step to the previous input."""
    return Command(Group.CONTROL, Control.INPUT_DOWN)


def set_direct(on: bool) -> Command:
    """Enable or disable Direct mode."""
    return Command(Group.CONTROL, Control.SET_DIRECT, "1" if on else "0")


# --- Setup command builders ------------------------------------------------


def get_software_version() -> Command:
    """Request the device software version (group-3 reply)."""
    return Command(Group.SETUP, Setup.GET_SOFTWARE_VERSION)


def get_protocol_version() -> Command:
    """Request the device protocol version (group-3 reply)."""
    return Command(Group.SETUP, Setup.GET_PROTOCOL_VERSION)
