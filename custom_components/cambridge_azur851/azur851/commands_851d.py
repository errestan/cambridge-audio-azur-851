"""Command definitions for the Azur 851D (DAC / preamplifier).

From the 851D Serial Control Protocol v1.0. The frame format is the same as the
amplifiers', but almost everything else differs from ``commands.py``:

  - Replies to control commands come back on group 3 (the amps use group 4),
    and setup replies on group 4.
  - Command numbers are different (power is #14, set volume #13, mute #44 and
    unmute #45, balance #46, ...).
  - Volume is attenuation: 000 is 0 dB (loudest) and 096 is -96 dB.
  - There are "get" commands, so volume and the filter can be read back.
  - Error numbers are 1-3 instead of 7-9.
"""

from __future__ import annotations

from enum import IntEnum

from .commands import BALANCE_MAX, BALANCE_MIN
from .protocol import Command

CONTROL_GROUP: int = 1
SETUP_GROUP: int = 2
REPLY_GROUP: int = 3  # replies to control commands
SETUP_REPLY_GROUP: int = 4

SOURCE_MIN: int = 1
SOURCE_MAX: int = 8

VOLUME_MIN: int = 0  # 0 dB
VOLUME_MAX: int = 96  # -96 dB


class Control(IntEnum):
    """Group 1 control command numbers (and their group 3 reply numbers)."""

    SELECT_SOURCE = 1
    NEXT_SOURCE = 2
    PREVIOUS_SOURCE = 3
    GET_WORD_WIDTH = 4
    GET_SAMPLE_RATE = 5
    GET_VOLUME = 12
    SET_VOLUME = 13
    POWER = 14
    LCD_BRIGHTNESS = 15
    HEADPHONES = 22  # reply only: 0 = out, 1 = inserted
    SELECT_FILTER = 40
    GET_FILTER = 41  # also the reply to SELECT_FILTER
    VOLUME_UP = 42
    VOLUME_DOWN = 43
    MUTE = 44
    UNMUTE = 45
    SET_BALANCE = 46
    BALANCE_RIGHT = 47
    BALANCE_LEFT = 48
    TRIGGER = 49
    GET_HEADPHONE_VOLUME = 50
    HEADPHONE_VOLUME_UP = 52
    HEADPHONE_VOLUME_DOWN = 53


class Setup(IntEnum):
    """Group 2 setup command numbers (and their group 4 reply numbers)."""

    GET_SOFTWARE_VERSION = 1
    GET_DSP_VERSION = 2
    SET_SOURCE_NAME = 4
    GET_SOURCE_NAME = 5


class Filter(IntEnum):
    """Digital filter types."""

    LINEAR = 1
    MINIMUM = 2
    STEEP = 3


class Error(IntEnum):
    """Group 5 error numbers. All three are replies to a bad command."""

    UNKNOWN_GROUP = 1
    UNKNOWN_NUMBER = 2
    # The document's table lists this as 04, but its example is #5,03.
    DATA_ERROR = 3


ERROR_DESCRIPTIONS: dict[int, str] = {
    Error.UNKNOWN_GROUP: "unknown command group",
    Error.UNKNOWN_NUMBER: "unknown command number",
    Error.DATA_ERROR: "invalid command data",
}


def _control(number: Control, data: str = "") -> Command:
    return Command(CONTROL_GROUP, number, data)


def power(on: bool) -> Command:
    """Set power: on, or standby."""
    return _control(Control.POWER, "1" if on else "0")


def mute(on: bool) -> Command:
    """Mute or unmute (two separate commands on the 851D)."""
    return _control(Control.MUTE if on else Control.UNMUTE)


def set_volume(level: int) -> Command:
    """Set the volume as attenuation: 0 (0 dB) .. 96 (-96 dB)."""
    if not VOLUME_MIN <= level <= VOLUME_MAX:
        raise ValueError(f"volume out of range ({VOLUME_MIN}-{VOLUME_MAX}): {level}")
    return _control(Control.SET_VOLUME, f"{level:03d}")


def get_volume() -> Command:
    """Ask for the current volume."""
    return _control(Control.GET_VOLUME)


def select_source(source: int) -> Command:
    """Select source 1-8."""
    if not SOURCE_MIN <= source <= SOURCE_MAX:
        raise ValueError(f"source out of range ({SOURCE_MIN}-{SOURCE_MAX}): {source}")
    return _control(Control.SELECT_SOURCE, str(source))


def set_balance(level: int) -> Command:
    """Set balance, 0 (max left) .. 8 (centre) .. 16 (max right)."""
    if not BALANCE_MIN <= level <= BALANCE_MAX:
        raise ValueError(f"balance out of range ({BALANCE_MIN}-{BALANCE_MAX}): {level}")
    return _control(Control.SET_BALANCE, f"{level:02d}")


def lcd_brightness(brightness: int) -> Command:
    """Set the display brightness: 0 off, 1 dim, 2 bright."""
    return _control(Control.LCD_BRIGHTNESS, str(brightness))


def select_filter(filter_type: Filter, phase_inverted: bool | None = None) -> Command:
    """Select the digital filter; leave ``phase_inverted`` None to keep the phase."""
    data = str(int(filter_type))
    if phase_inverted is not None:
        data += ",1" if phase_inverted else ",0"
    return _control(Control.SELECT_FILTER, data)


def get_filter() -> Command:
    """Ask for the current filter and phase."""
    return _control(Control.GET_FILTER)


def get_dsp_version() -> Command:
    """Ask for the DSP version (group 4 reply); used to probe the link."""
    return Command(SETUP_GROUP, Setup.GET_DSP_VERSION)


# Word width codes 01-09 are 16-24 bits; 00 means no valid signal.
WORD_WIDTHS: dict[int, int] = {code: 15 + code for code in range(1, 10)}

# Sample rate codes, in Hz; 00 means no valid signal.
SAMPLE_RATES: dict[int, int] = {
    1: 32000,
    2: 44100,
    3: 48000,
    4: 88200,
    5: 96000,
    6: 176400,
    7: 192000,
}


def set_trigger(high: bool) -> Command:
    """Set the 12 V trigger output high or low."""
    return _control(Control.TRIGGER, "1" if high else "0")


def get_word_width() -> Command:
    """Ask for the input's word width (bit depth)."""
    return _control(Control.GET_WORD_WIDTH)


def get_sample_rate() -> Command:
    """Ask for the input's sampling frequency."""
    return _control(Control.GET_SAMPLE_RATE)


def get_headphone_volume() -> Command:
    """Ask for the headphone volume."""
    return _control(Control.GET_HEADPHONE_VOLUME)


def headphone_volume_up() -> Command:
    """Raise the headphone volume one step (headphones must be in)."""
    return _control(Control.HEADPHONE_VOLUME_UP)


def headphone_volume_down() -> Command:
    """Lower the headphone volume one step (headphones must be in)."""
    return _control(Control.HEADPHONE_VOLUME_DOWN)


def get_software_version() -> Command:
    """Ask for the software version (group 4 reply)."""
    return Command(SETUP_GROUP, Setup.GET_SOFTWARE_VERSION)


def get_source_name(source: int) -> Command:
    """Ask for a source's name (group 4 reply ``x,name``)."""
    return Command(SETUP_GROUP, Setup.GET_SOURCE_NAME, f"{source},")
