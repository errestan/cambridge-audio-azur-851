"""Standalone client library for Cambridge Audio Azur 851 RS-232 control.

This package has NO Home Assistant imports. It can be imported, tested, and used
independently of Home Assistant. The integration layer wraps it via the
DataUpdateCoordinator.

State model: the 851 protocol has no "read everything" query -- the device
reports state when it changes (and, on the 851D, a few values on request). The
connection's read loop feeds those frames to :meth:`Azur851Client._handle_frame`,
which updates ``state`` through the model's command set and fires the optional
``on_update`` callback so the coordinator can push to Home Assistant.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Self

from . import commands, commands_851d
from .command_sets import CommandSet, get_command_set
from .commands import Brightness, Speakers
from .commands_851d import Filter
from .connection import Azur851Connection
from .exceptions import (
    Azur851CommandError,
    Azur851ConnectionError,
    Azur851Error,
    Azur851NoResponseError,
    Azur851ProtocolError,
)
from .models import DeviceState, ModelCapabilities, get_model_capabilities
from .protocol import Command, Response, decode, encode

_LOGGER = logging.getLogger(__name__)

# How long to wait for the device to answer a probe. The 851 replies within
# milliseconds; this leaves headroom for a network serial proxy.
PROBE_TIMEOUT: float = 2.0


class Azur851Client:
    """High-level async client for an Azur 851 device.

    The integration talks only to this class; protocol/frame details live in
    ``protocol.py`` and ``commands.py``.
    """

    def __init__(self, connection: Azur851Connection, model: str) -> None:
        """Initialize the client and subscribe to inbound frames."""
        self._connection = connection
        self._connection.on_frame = self._handle_frame
        self._connection.on_connection_state = self._forward_connection_state
        self._model = model
        self._capabilities = get_model_capabilities(model)
        self._commands: CommandSet = get_command_set(self._capabilities.command_set)
        self._state = DeviceState()
        # Set by the coordinator to receive push notifications on state change.
        self.on_update: Callable[[], None] | None = None
        # Set by the coordinator to track availability (True = up, False = down).
        self.on_connection_state: Callable[[bool], None] | None = None
        # Resolved by the next valid inbound frame while a probe is in flight.
        self._probe_waiter: asyncio.Future[Response] | None = None
        # The last command sent, so a group-5 reply can say what it rejected.
        self._last_sent: Command | None = None

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> Self:
        """Build a client from a config entry's data dict."""
        model = data["model"]
        capabilities = get_model_capabilities(model)
        connection = Azur851Connection(data["serial_url"], capabilities.baudrate)
        return cls(connection, model)

    @property
    def capabilities(self) -> ModelCapabilities:
        """Return the capability map for this model."""
        return self._capabilities

    @property
    def state(self) -> DeviceState:
        """Return the latest known device state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Return True if the transport is open."""
        return self._connection.is_open

    # --- Connection lifecycle ---------------------------------------------

    async def async_connect(self) -> None:
        """Open the transport and start receiving updates."""
        await self._connection.async_open()

    async def async_test_connection(
        self, response_timeout: float = PROBE_TIMEOUT
    ) -> None:
        """Open the link, check the device answers, then close.

        Used by the config flow. Raises ``Azur851ConnectionError`` if the port
        cannot be opened, or ``Azur851NoResponseError`` if it opens but the
        device stays silent.
        """
        await self._connection.async_open()
        try:
            await self.async_probe(response_timeout)
        finally:
            await self._connection.async_close()

    async def async_probe(self, response_timeout: float = PROBE_TIMEOUT) -> Response:
        """Send a harmless query and wait for the device to answer.

        Any valid frame counts as an answer -- even a group-5 error proves the
        device is there and listening. Returns the first frame received.
        """
        waiter: asyncio.Future[Response] = asyncio.get_running_loop().create_future()
        self._probe_waiter = waiter
        try:
            await self._write(self._commands.probe())
            return await asyncio.wait_for(waiter, response_timeout)
        except TimeoutError as err:
            raise Azur851NoResponseError(
                f"No response from the {self._model} within {response_timeout:g}s"
            ) from err
        finally:
            self._probe_waiter = None

    async def async_request_state(self) -> None:
        """Ask the device to report whatever state it can without changing it.

        Which values can be read back depends on the model (see the command
        sets); the rest are learned only from the updates sent when they change.
        """
        for command in self._commands.state_queries():
            await self._write(command)

    async def async_close(self) -> None:
        """Close the underlying transport."""
        await self._connection.async_close()

    # --- Commands ----------------------------------------------------------

    async def async_power(self, on: bool) -> None:
        """Set power / standby."""
        await self._write(self._commands.power(on))

    async def async_mute(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._write(self._commands.mute(mute))

    async def async_set_volume(self, level: float) -> None:
        """Set volume from a 0..1 fraction, scaled to the device range."""
        await self._write(self._commands.set_volume(self._scale_to_device(level)))

    async def async_select_source(self, source: str) -> None:
        """Select an input source by its configured name."""
        selected = self._capabilities.sources.get(source)
        if selected is None:
            raise Azur851Error(f"Unknown source for {self._model}: {source!r}")
        await self._write(self._commands.select_source(selected))

    async def async_set_tape_monitor(self, on: bool) -> None:
        """Turn tape monitor (851E: record in) on or off."""
        await self._write(commands.tape_monitor(on))

    async def async_set_brightness(self, brightness: Brightness) -> None:
        """Set the display brightness."""
        await self._write(self._commands.lcd_brightness(brightness))

    async def async_set_direct(self, on: bool) -> None:
        """Turn Direct mode on or off."""
        await self._write(commands.set_direct(on))

    async def async_set_balance(self, level: int) -> None:
        """Set balance, device-native 0 (left) .. 8 (centre) .. 16 (right)."""
        await self._write(self._commands.set_balance(level))

    async def async_set_speakers(self, speakers: Speakers) -> None:
        """Select speaker outputs A, A+B or B."""
        await self._write(commands.speaker_select(speakers))

    async def async_set_filter(self, filter_type: Filter) -> None:
        """Select the digital filter, keeping the phase (851D only)."""
        await self._write(commands_851d.select_filter(filter_type))

    async def async_set_phase_inverted(self, inverted: bool) -> None:
        """Invert or restore the output phase (851D only).

        The command sets filter and phase together, so it needs the current
        filter; that is read back on connect.
        """
        filter_type = self._state.filter
        if filter_type is None:
            raise Azur851Error("The current filter is not known yet")
        await self._write(commands_851d.select_filter(Filter(filter_type), inverted))

    # --- Volume scaling helpers -------------------------------------------

    def _scale_to_device(self, fraction: float) -> int:
        """Convert a 0..1 fraction to a device-native volume level."""
        caps = self._capabilities
        fraction = max(0.0, min(1.0, fraction))
        if caps.volume_inverted:
            fraction = 1.0 - fraction
        return caps.volume_min + round(fraction * (caps.volume_max - caps.volume_min))

    def scale_from_device(self, raw: int | None) -> float | None:
        """Convert a device-native volume level to a 0..1 fraction."""
        if raw is None:
            return None
        caps = self._capabilities
        span = caps.volume_max - caps.volume_min
        if span <= 0:
            return None
        fraction = (raw - caps.volume_min) / span
        return 1.0 - fraction if caps.volume_inverted else fraction

    # --- Frame handling ----------------------------------------------------

    async def _write(self, command: Command) -> None:
        """Encode and send a command. The device answers via the read loop."""
        self._last_sent = command
        await self._connection.async_write(encode(command))

    def _forward_connection_state(self, connected: bool) -> None:
        """Relay the transport's up/down state to the coordinator."""
        if self.on_connection_state is not None:
            self.on_connection_state(connected)

    def _handle_frame(self, raw: bytes) -> None:
        """Handle one inbound frame from the connection's read loop."""
        try:
            response = decode(raw)
        except Azur851ProtocolError:
            return  # ignore unparseable noise on the line
        if self._probe_waiter is not None and not self._probe_waiter.done():
            self._probe_waiter.set_result(response)
        if response.is_error:
            self._log_error(response)
            return
        if self.apply_update(response) and self.on_update is not None:
            self.on_update()

    def _log_error(self, response: Response) -> None:
        """Log a group-5 error: a rejected command or a hardware fault."""
        number = response.number
        what = self._commands.error_descriptions.get(number, f"error {number}")
        if number in self._commands.command_errors:
            sent = self._last_sent
            rejected = encode(sent).decode().strip() if sent else "a command"
            _LOGGER.warning("Azur %s rejected %s: %s", self._model, rejected, what)
        else:
            _LOGGER.warning("Azur %s reported a fault: %s", self._model, what)

    def apply_update(self, response: Response) -> bool:
        """Fold a state reply/update into ``state``; return True if changed."""
        return self._commands.apply(response, self._state)


__all__ = [
    "Azur851Client",
    "Azur851CommandError",
    "Azur851ConnectionError",
    "Azur851Error",
    "Azur851NoResponseError",
    "Azur851ProtocolError",
    "Brightness",
    "DeviceState",
    "Filter",
    "ModelCapabilities",
    "Speakers",
]
