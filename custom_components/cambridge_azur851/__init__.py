"""The Cambridge Audio Azur 851 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import Azur851Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

# Use a typed config entry so runtime_data carries the coordinator.
type Azur851ConfigEntry = ConfigEntry[Azur851Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Azur851ConfigEntry) -> bool:
    """Set up Cambridge Audio Azur 851 from a config entry."""
    coordinator = Azur851Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Azur851ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
