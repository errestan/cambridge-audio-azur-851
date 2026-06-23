"""Standalone client library for Cambridge Audio Azur 851 RS-232 control.

This package has NO Home Assistant imports. It can be imported, tested, and used
independently of Home Assistant. The integration layer wraps it via the
DataUpdateCoordinator.

State note: the 851A protocol has no "read everything" query -- the device emits
group-4 update frames when state changes. The client maintains a best-effort
``DeviceState`` from those frames via :meth:`Azur851Client.apply_update`.
"""

from __future__ import annotations

from typing import Any, Self

from . import commands
from .commands import INPUT_MAX, INPUT_MIN, Control, Group
from .connection import Azur851Connection
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
        """Initialize the client."""
        self._connection = connection
        self._model = model
        self._capabilities = get_model_capabilities(model)
        self._state = DeviceState()

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> Self:
        """Build a client from a config entry's data dict."""
        model = data["model"]
        capabilities = get_model_capabilities(model)
        if serial_url := data.get("serial_url"):
            connection = Azur851Connection.from_serial_url(
                serial_url, capabilities.baudrate
            )
        else:
            connection = Azur851Connection.from_serial_proxy(data["host"], data["port"])
        return cls(connection, model)

    @property
    def capabilities(self) -> ModelCapabilities:
        """Return the capability map for this model."""
        return self._capabilities

    # --- Connection lifecycle ---------------------------------------------

    async def async_test_connection(self) -> None:
        """Open the connection and confirm the device responds.

        Used by the config flow. Queries the protocol version and expects a
        group-3 reply.
        """
        await self._connection.async_open()
        await self._send(commands.get_protocol_version())

    async def async_poll_state(self) -> DeviceState:
        """Return the latest known device state.

        The 851 protocol is push-based, so this returns the state accumulated
        from group-4 update frames rather than issuing a bulk query.
        """
        return self._state

    async def async_close(self) -> None:
        """Close the underlying transport."""
        await self._connection.async_close()

    # --- Commands ----------------------------------------------------------

    async def async_power(self, on: bool) -> None:
        """Set power / standby."""
        await self._send(commands.power(on))

    async def async_mute(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._send(commands.mute(mute))

    async def async_set_volume(self, level: float) -> None:
        """Set volume from a 0..1 fraction, scaled to the device range."""
        await self._send(commands.set_volume(self._scale_to_device(level)))

    async def async_select_source(self, source: str) -> None:
        """Select an input source by its configured name."""
        index = self._capabilities.sources.get(source)
        if index is None:
            raise Azur851Error(f"Unknown source for {self._model}: {source!r}")
        await self._send(commands.select_input(index))

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

    async def _send(self, command: Command) -> Response | None:
        """Send a command, parse the reply, and fold any update into state."""
        raw = await self._connection.async_send(encode(command))
        if not raw:
            return None
        response = decode(raw)
        if response.is_error:
            raise Azur851CommandError(response.number)
        self.apply_update(response)
        return response

    def apply_update(self, response: Response) -> None:
        """Update cached state from a group-4 update/reply frame."""
        if response.group != Group.UPDATE:
            return
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
    "ModelCapabilities",
]
