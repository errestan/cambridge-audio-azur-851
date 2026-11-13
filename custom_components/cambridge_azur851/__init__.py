"""The Cambridge Audio Azur 851 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_MODEL, SUPPORTED_MODELS
from .coordinator import Azur851Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

# Use a typed config entry so runtime_data carries the coordinator.
type Azur851ConfigEntry = ConfigEntry[Azur851Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Azur851ConfigEntry) -> bool:
    """Set up Cambridge Audio Azur 851 from a config entry."""
    if (model := entry.data[CONF_MODEL]) not in SUPPORTED_MODELS:
        # Entries created before the model list was narrowed keep working on the
        # generic profile, but the user should know it is not a verified fit.
        _LOGGER.warning(
            "Azur %s is not a supported model; it is being controlled with the "
            "851A command set, which may not match. Supported: %s",
            model,
            ", ".join(SUPPORTED_MODELS),
        )
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
