"""DataUpdateCoordinator for the Cambridge Audio Azur 851 integration.

All access to the device goes through this coordinator so the serial link is used
by exactly one request at a time.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .azur851 import Azur851Client, Azur851Error
from .azur851.models import DeviceState
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN

if TYPE_CHECKING:
    from . import Azur851ConfigEntry

_LOGGER = logging.getLogger(__name__)


class Azur851Coordinator(DataUpdateCoordinator[DeviceState]):
    """Polls device state and exposes it to entities."""

    config_entry: Azur851ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: Azur851ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        # TODO: build the client from entry.data (host/port or serial URL, model).
        self.client = Azur851Client.from_config(entry.data)

    async def _async_update_data(self) -> DeviceState:
        """Fetch the latest state from the device."""
        try:
            return await self.client.async_poll_state()
        except Azur851Error as err:
            raise UpdateFailed(f"Error communicating with Azur 851: {err}") from err

    async def async_shutdown(self) -> None:
        """Close the connection on unload."""
        await super().async_shutdown()
        await self.client.async_close()
