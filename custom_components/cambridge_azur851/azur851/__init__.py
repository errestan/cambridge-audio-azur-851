"""Standalone client library for Cambridge Audio Azur 851 RS-232 control.

This package has NO Home Assistant imports. It can be imported, tested, and used
independently of Home Assistant. The integration layer wraps it via the
DataUpdateCoordinator.
"""

from __future__ import annotations

from typing import Any, Self

from .connection import Azur851Connection
from .models import DeviceState, get_model_capabilities


class Azur851Error(Exception):
    """Base error for the Azur 851 client."""


class Azur851ConnectionError(Azur851Error):
    """Raised when the transport cannot reach the device."""


class Azur851ProtocolError(Azur851Error):
    """Raised when a frame cannot be parsed or the device reports an error."""


class Azur851Client:
    """High-level async client for an Azur 851 device.

    The integration talks only to this class; protocol/frame details live in
    `protocol.py` and `commands.py`.
    """

    def __init__(self, connection: Azur851Connection, model: str) -> None:
        """Initialize the client."""
        self._connection = connection
        self._model = model
        self._capabilities = get_model_capabilities(model)

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> Self:
        """Build a client from a config entry's data dict."""
        # TODO: construct the appropriate transport (serial proxy vs. local serial)
        #       from the config keys and instantiate Azur851Connection.
        raise NotImplementedError

    async def async_test_connection(self) -> None:
        """Open the connection and confirm the device responds. Used by config flow."""
        # TODO: open connection, query identity/firmware or a harmless status command.
        raise NotImplementedError

    async def async_poll_state(self) -> DeviceState:
        """Query and return the full device state."""
        # TODO: issue the status command(s) and parse into DeviceState.
        raise NotImplementedError

    # --- Commands ----------------------------------------------------------

    async def async_power(self, on: bool) -> None:
        """Set power / standby."""
        raise NotImplementedError

    async def async_set_volume(self, level: float) -> None:
        """Set volume from a 0..1 level."""
        raise NotImplementedError

    async def async_mute(self, mute: bool) -> None:
        """Mute or unmute."""
        raise NotImplementedError

    async def async_select_source(self, source: str) -> None:
        """Select an input source by name."""
        raise NotImplementedError

    async def async_close(self) -> None:
        """Close the underlying transport."""
        await self._connection.async_close()


__all__ = [
    "Azur851Client",
    "Azur851ConnectionError",
    "Azur851Error",
    "Azur851ProtocolError",
    "DeviceState",
]
