"""Standalone client library for Cambridge Audio Azur 851 RS-232 control.

This package has NO Home Assistant imports. It can be imported, tested, and used
independently of Home Assistant. The integration layer wraps it via the
DataUpdateCoordinator.

State model: the 851 protocol has no "read everything" query -- the device emits
group-4 update frames when state changes. The connection's read loop feeds those
frames to :meth:`Azur851Client._handle_frame`, which updates ``state`` and fires
the optional ``on_update`` callback so the coordinator can push to Home Assistant.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Self

from . import commands
from .commands import INPUT_MAX, INPUT_MIN, Control, Group
from .connection import Azur851Connection, DiscoveredPort, async_discover_ports
from .exceptions import (
    Azur851CommandError,
    Azur851ConnectionError,
    Azur851Error,
    Azur851ProtocolError,
)
from .models import DeviceState, ModelCapabilities, get_model_capabilities
from .protocol import Command, Response, decode, encode


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
        self._state = DeviceState()
        # Set by the coordinator to receive push notifications on state change.
        self.on_update: Callable[[], None] | None = None
        # Set by the coordinator to track availability (True = up, False = down).
        self.on_connection_state: Callable[[bool], None] | None = None

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

    async def async_test_connection(self) -> None:
        """Open the link, probe the device, then close. Used by the config flow."""
        await self._connection.async_open()
        try:
            await self._connection.async_write(encode(commands.get_protocol_version()))
        finally:
            await self._connection.async_close()

    async def async_close(self) -> None:
        """Close the underlying transport."""
        await self._connection.async_close()

    # --- Commands ----------------------------------------------------------

    async def async_power(self, on: bool) -> None:
        """Set power / standby."""
        await self._write(commands.power(on))

    async def async_mute(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._write(commands.mute(mute))

    async def async_set_volume(self, level: float) -> None:
        """Set volume from a 0..1 fraction, scaled to the device range."""
        await self._write(commands.set_volume(self._scale_to_device(level)))

    async def async_select_source(self, source: str) -> None:
        """Select an input source by its configured name."""
        index = self._capabilities.sources.get(source)
        if index is None:
            raise Azur851Error(f"Unknown source for {self._model}: {source!r}")
        await self._write(commands.select_input(index))

    # --- Volume scaling helpers -------------------------------------------

    def _scale_to_device(self, fraction: float) -> int:
        """Convert a 0..1 fraction to a device-native volume level."""
        caps = self._capabilities
        fraction = max(0.0, min(1.0, fraction))
        return caps.volume_min + round(fraction * (caps.volume_max - caps.volume_min))

    def scale_from_device(self, raw: int | None) -> float | None:
        """Convert a device-native volume level to a 0..1 fraction."""
        if raw is None:
            return None
        caps = self._capabilities
        span = caps.volume_max - caps.volume_min
        if span <= 0:
            return None
        return (raw - caps.volume_min) / span

    # --- Frame handling ----------------------------------------------------

    async def _write(self, command: Command) -> None:
        """Encode and send a command. The device answers via the read loop."""
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
        if response.is_error:
            return  # group-5 errors are not state; could be logged/raised later
        if self.apply_update(response) and self.on_update is not None:
            self.on_update()

    def apply_update(self, response: Response) -> bool:
        """Fold a group-4 update/reply frame into state; return True if changed."""
        if response.group != Group.UPDATE:
            return False
        number = response.number
        if number == Control.POWER:
            self._state.power_on = response.data == "1"
        elif number == Control.MUTE:
            # Update encoding: 1 = mute ON (inverse of the control command).
            self._state.muted = response.data == "1"
        elif number in (Control.SET_VOLUME, Control.VOLUME_STOP):
            self._state.volume_raw = _to_int(response.data)
        elif INPUT_MIN <= number <= INPUT_MAX:
            self._state.source_code = number
        else:
            return False
        return True


def _to_int(data: str) -> int | None:
    """Parse numeric frame data, returning None if it is not an integer."""
    try:
        return int(data)
    except ValueError:
        return None


__all__ = [
    "Azur851Client",
    "Azur851CommandError",
    "Azur851ConnectionError",
    "Azur851Error",
    "Azur851ProtocolError",
    "DeviceState",
    "DiscoveredPort",
    "ModelCapabilities",
    "async_discover_ports",
]
