"""Media player platform for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import TYPE_CHECKING

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .azur851 import Azur851Error
from .azur851.models import ModelCapabilities
from .entity import Azur851Entity

if TYPE_CHECKING:
    from . import Azur851ConfigEntry
    from .coordinator import Azur851Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Azur851ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player from a config entry."""
    async_add_entities([Azur851MediaPlayer(entry.runtime_data)])


class Azur851MediaPlayer(Azur851Entity, MediaPlayerEntity):
    """Represents an Azur 851 device as a media player."""

    _attr_name = None  # Use the device name.

    def __init__(self, coordinator: Azur851Coordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._attr_supported_features = _supported_features(
            coordinator.client.capabilities
        )

    # --- State (read from coordinator.data) --------------------------------

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current power state."""
        power_on = self.coordinator.data.power_on
        if power_on is None:
            return None
        return MediaPlayerState.ON if power_on else MediaPlayerState.STANDBY

    @property
    def volume_level(self) -> float | None:
        """Return volume level in the 0..1 range."""
        return self.coordinator.client.scale_from_device(
            self.coordinator.data.volume_raw
        )

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if volume is muted."""
        return self.coordinator.data.muted

    @property
    def source(self) -> str | None:
        """Return the currently selected source."""
        return self.coordinator.client.capabilities.source_name(
            self.coordinator.data.source_code
        )

    @property
    def source_list(self) -> list[str]:
        """Return the list of selectable sources for this model."""
        return list(self.coordinator.client.capabilities.sources)

    # --- Commands (write through the client) -------------------------------

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self._async_send(self.coordinator.client.async_power(True))

    async def async_turn_off(self) -> None:
        """Put the device into standby."""
        await self._async_send(self.coordinator.client.async_power(False))

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume (0..1)."""
        await self._async_send(self.coordinator.client.async_set_volume(volume))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._async_send(self.coordinator.client.async_mute(mute))

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        await self._async_send(self.coordinator.client.async_select_source(source))

    async def _async_send(self, command: Awaitable[None]) -> None:
        """Send a command, surfacing link/device errors as HomeAssistantError.

        No refresh afterwards: the device confirms every change with a group-4
        frame, which arrives through the push path.
        """
        try:
            await command
        except Azur851Error as err:
            raise HomeAssistantError(f"Azur 851 command failed: {err}") from err


def _supported_features(caps: ModelCapabilities) -> MediaPlayerEntityFeature:
    """Build the entity's feature set from the model's capability map."""
    features = MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
    if caps.has_volume:
        features |= MediaPlayerEntityFeature.VOLUME_SET
        features |= MediaPlayerEntityFeature.VOLUME_STEP
    if caps.has_mute:
        features |= MediaPlayerEntityFeature.VOLUME_MUTE
    if caps.has_source_select and caps.sources:
        features |= MediaPlayerEntityFeature.SELECT_SOURCE
    return features
