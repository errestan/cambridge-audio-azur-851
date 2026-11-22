"""Binary sensor platform: whether headphones are plugged into the 851D."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import Azur851Entity

if TYPE_CHECKING:
    from . import Azur851ConfigEntry
    from .coordinator import Azur851Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Azur851ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the headphones sensor on models that report it."""
    coordinator = entry.runtime_data
    if coordinator.client.capabilities.has_headphones:
        async_add_entities([Azur851Headphones(coordinator)])


class Azur851Headphones(Azur851Entity, BinarySensorEntity):
    """On while headphones are plugged in.

    The 851D reports this only when headphones go in or out, so it is unknown
    until the first change after Home Assistant connects.
    """

    _attr_translation_key = "headphones"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    def __init__(self, coordinator: Azur851Coordinator) -> None:
        """Initialize the headphones sensor."""
        super().__init__(coordinator, "headphones")

    @property
    def is_on(self) -> bool | None:
        """Return True if headphones are plugged in."""
        return self.coordinator.data.headphones
