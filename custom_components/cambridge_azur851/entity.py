"""Shared base entity for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import Azur851Coordinator


class Azur851Entity(CoordinatorEntity[Azur851Coordinator]):
    """Base entity wiring device info and availability to the coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Azur851Coordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=entry.data.get("model"),
            name=entry.title,
        )

    @property
    def available(self) -> bool:
        """Return True if the device is reachable."""
        return super().available and self.coordinator.data is not None
