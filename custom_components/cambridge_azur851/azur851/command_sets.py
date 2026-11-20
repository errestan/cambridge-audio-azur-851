"""Per-model command sets: how to build commands and read replies.

The 851A and 851E share one command set (``commands.py``); the 851D has its own
(``commands_851d.py``). The client picks one from the model's capabilities and
goes through it for everything that differs between them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from . import commands, commands_851d
from .commands import Control, Group
from .commands_851d import Control as DControl
from .models import DeviceState, Source
from .protocol import Command, Response

# Amp group-4 updates that carry a setting, mapped to the DeviceState field.
_AMP_LEVELS: dict[int, str] = {
    Control.SET_BALANCE: "balance",
    Control.SPEAKER_SELECT: "speakers",
    Control.LCD_BRIGHTNESS: "brightness",
}
_AMP_SWITCHES: dict[int, str] = {
    Control.TAPE_MONITOR: "tape_monitor",
    Control.SET_DIRECT: "direct",
}


class CommandSet(ABC):
    """What the client needs from a model's protocol."""

    # Group-5 error number -> description, and which numbers mean the last
    # command was rejected (as opposed to a hardware fault).
    error_descriptions: dict[int, str]
    command_errors: frozenset[int]

    @abstractmethod
    def probe(self) -> Command:
        """Return a harmless command the device always answers."""

    @abstractmethod
    def state_queries(self) -> list[Command]:
        """Return commands that make the device report its state."""

    @abstractmethod
    def power(self, on: bool) -> Command:
        """Return the power on/standby command."""

    @abstractmethod
    def mute(self, on: bool) -> Command:
        """Return the mute/unmute command."""

    @abstractmethod
    def set_volume(self, level: int) -> Command:
        """Return the set-volume command for a device-native level."""

    @abstractmethod
    def select_source(self, source: Source) -> Command:
        """Return the command selecting ``source``."""

    @abstractmethod
    def set_balance(self, level: int) -> Command:
        """Return the set-balance command (0 left .. 8 centre .. 16 right)."""

    @abstractmethod
    def lcd_brightness(self, brightness: int) -> Command:
        """Return the display brightness command."""

    @abstractmethod
    def apply(self, response: Response, state: DeviceState) -> bool:
        """Fold a reply into ``state``; return True if it was a state reply."""


class AmpCommandSet(CommandSet):
    """The 851A and 851E."""

    error_descriptions = commands.ERROR_DESCRIPTIONS
    command_errors = commands.COMMAND_ERRORS

    def probe(self) -> Command:
        """Ask for the protocol version."""
        return commands.get_protocol_version()

    def state_queries(self) -> list[Command]:
        """Only volume can be learned on demand.

        *Volume stop* is a no-op when no ramp is running, and the device answers
        it with ``#4,16,<level>``. Everything else is reported only when it
        changes.
        """
        return [commands.volume_stop()]

    def power(self, on: bool) -> Command:
        """Set power."""
        return commands.power(on)

    def mute(self, on: bool) -> Command:
        """Mute or unmute."""
        return commands.mute(on)

    def set_volume(self, level: int) -> Command:
        """Set volume."""
        return commands.set_volume(level)

    def select_source(self, source: Source) -> Command:
        """Select an input and socket."""
        return commands.select_input(source.number, source.balanced)

    def set_balance(self, level: int) -> Command:
        """Set balance."""
        return commands.set_balance(level)

    def lcd_brightness(self, brightness: int) -> Command:
        """Set display brightness."""
        return commands.lcd_brightness(commands.Brightness(brightness))

    def apply(self, response: Response, state: DeviceState) -> bool:
        """Read a group-4 update."""
        if response.group != Group.UPDATE:
            return False
        number, data = response.number, response.data
        if number == Control.POWER:
            state.power_on = data == "1"
        elif number == Control.MUTE:
            # Update encoding: 1 = mute ON (inverse of the control command).
            state.muted = data == "1"
        elif number in (Control.SET_VOLUME, Control.VOLUME_STOP):
            state.volume_raw = _to_int(data)
        elif commands.INPUT_MIN <= number <= commands.INPUT_MAX:
            state.source_code = number
            # "1" = balanced socket; no data = unbalanced (or single-socket).
            state.source_balanced = data == "1"
        elif number in _AMP_SWITCHES:
            setattr(state, _AMP_SWITCHES[number], data == "1")
        elif number in _AMP_LEVELS:
            setattr(state, _AMP_LEVELS[number], _to_int(data))
        else:
            return False
        return True


class DacCommandSet(CommandSet):
    """The 851D."""

    error_descriptions = commands_851d.ERROR_DESCRIPTIONS
    command_errors = frozenset(commands_851d.Error)

    def probe(self) -> Command:
        """Ask for the DSP version."""
        return commands_851d.get_dsp_version()

    def state_queries(self) -> list[Command]:
        """Volume and filter can be read back; the rest only on change."""
        return [commands_851d.get_volume(), commands_851d.get_filter()]

    def power(self, on: bool) -> Command:
        """Set power."""
        return commands_851d.power(on)

    def mute(self, on: bool) -> Command:
        """Mute or unmute."""
        return commands_851d.mute(on)

    def set_volume(self, level: int) -> Command:
        """Set volume (attenuation)."""
        return commands_851d.set_volume(level)

    def select_source(self, source: Source) -> Command:
        """Select a source."""
        return commands_851d.select_source(source.number)

    def set_balance(self, level: int) -> Command:
        """Set balance."""
        return commands_851d.set_balance(level)

    def lcd_brightness(self, brightness: int) -> Command:
        """Set display brightness."""
        return commands_851d.lcd_brightness(brightness)

    def apply(self, response: Response, state: DeviceState) -> bool:
        """Read a group-3 control reply."""
        if response.group != commands_851d.REPLY_GROUP:
            return False
        number, data = response.number, response.data
        if number == DControl.POWER:
            state.power_on = data == "1"
        elif number in (DControl.MUTE, DControl.UNMUTE):
            state.muted = number == DControl.MUTE
        elif number in (
            DControl.GET_VOLUME,
            DControl.SET_VOLUME,
            DControl.VOLUME_UP,
            DControl.VOLUME_DOWN,
        ):
            state.volume_raw = _to_int(data)
        elif number == DControl.SELECT_SOURCE:
            state.source_code = _to_int(data)
        elif number in (
            DControl.SET_BALANCE,
            DControl.BALANCE_RIGHT,
            DControl.BALANCE_LEFT,
        ):
            state.balance = _to_int(data)
        elif number == DControl.LCD_BRIGHTNESS:
            state.brightness = _to_int(data)
        # The document says filter changes reply as #3,41, but a real 851D
        # reports them (including front-panel changes) as #3,40.
        elif number in (DControl.SELECT_FILTER, DControl.GET_FILTER):
            filter_type, _, phase = data.partition(",")
            state.filter = _to_int(filter_type)
            state.phase_inverted = phase == "1" if phase else None
        else:
            return False
        return True


def _to_int(data: str) -> int | None:
    """Parse numeric frame data, returning None if it is not an integer."""
    try:
        return int(data)
    except ValueError:
        return None


_COMMAND_SETS: dict[str, CommandSet] = {
    "amp": AmpCommandSet(),
    "dac": DacCommandSet(),
}


def get_command_set(name: str) -> CommandSet:
    """Return the command set a model's capabilities name."""
    return _COMMAND_SETS[name]
