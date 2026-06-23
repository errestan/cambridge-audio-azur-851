"""Media player platform for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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

    # TODO: derive the supported feature set from the model capability map.
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: Azur851Coordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)

    # --- State (read from coordinator.data) --------------------------------

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current power state."""
        # TODO: map DeviceState.power -> ON/OFF/STANDBY.
        return None

    @property
    def volume_level(self) -> float | None:
        """Return volume level in the 0..1 range."""
        # TODO: scale DeviceState.volume to 0..1.
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if volume is muted."""
        return None

    @property
    def source(self) -> str | None:
        """Return the currently selected source."""
        return None

    @property
    def source_list(self) -> list[str] | None:
        """Return the list of selectable sources for this model."""
        # TODO: read from the model capability map.
        return None

    # --- Commands (write through the client) -------------------------------

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        # TODO: await self.coordinator.client.async_power(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Put the device into standby."""
        # TODO: await self.coordinator.client.async_power(False)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume (0..1)."""
        # TODO: await self.coordinator.client.async_set_volume(volume)
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        # TODO: await self.coordinator.client.async_mute(mute)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        # TODO: await self.coordinator.client.async_select_source(source)
        await self.coordinator.async_request_refresh()
