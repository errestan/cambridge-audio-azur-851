"""DataUpdateCoordinator for the Cambridge Audio Azur 851 integration.

The 851 is push-based: there is no bulk status query, the device emits group-4
update frames on every state change. So this coordinator opens the connection
once and lets the client push updates in (via ``on_update``) rather than polling.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .azur851 import Azur851Client, Azur851ConnectionError, Azur851Error
from .azur851.models import DeviceState
from .const import DOMAIN

if TYPE_CHECKING:
    from . import Azur851ConfigEntry

_LOGGER = logging.getLogger(__name__)


class Azur851Coordinator(DataUpdateCoordinator[DeviceState]):
    """Owns the connection and pushes device state to entities."""

    config_entry: Azur851ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: Azur851ConfigEntry) -> None:
        """Initialize the coordinator (no polling interval -- push only)."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=None,
        )
        self.client = Azur851Client.from_config(entry.data)
        self.client.on_update = self._handle_push
        self.client.on_connection_state = self._handle_connection_state

    @callback
    def _handle_push(self) -> None:
        """Publish freshly pushed device state to listeners."""
        self.async_set_updated_data(self.client.state)

    @callback
    def _handle_connection_state(self, connected: bool) -> None:
        """Mark entities available/unavailable as the link comes and goes."""
        if connected:
            self.async_set_updated_data(self.client.state)
        else:
            self.async_set_update_error(
                Azur851ConnectionError("Connection to Azur 851 lost")
            )

    async def _async_update_data(self) -> DeviceState:
        """Ensure the connection is open; return the latest known state.

        Called once on first refresh. After that, updates arrive via push.
        TODO: add reconnection handling if the link drops.
        """
        try:
            if not self.client.is_open:
                await self.client.async_connect()
        except Azur851Error as err:
            raise UpdateFailed(f"Error connecting to Azur 851: {err}") from err
        return self.client.state

    async def async_shutdown(self) -> None:
        """Close the connection on unload."""
        await super().async_shutdown()
        await self.client.async_close()
