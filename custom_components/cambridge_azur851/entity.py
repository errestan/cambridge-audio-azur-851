"""Shared base entities for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .azur851 import Azur851Error
from .azur851.models import DeviceState, ModelCapabilities
from .const import DOMAIN, MANUFACTURER
from .coordinator import Azur851Coordinator


class Azur851Entity(CoordinatorEntity[Azur851Coordinator]):
    """Base entity wiring device info and availability to the coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Azur851Coordinator, key: str | None = None) -> None:
        """Initialize the base entity.

        ``key`` distinguishes this device's entities; the media player (the
        main entity) has none, so its unique ID stays the bare entry ID.
        """
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = (
            entry.entry_id if key is None else f"{entry.entry_id}_{key}"
        )
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

    async def _async_send(self, command: Awaitable[None]) -> None:
        """Send a command, surfacing link/device errors as HomeAssistantError.

        No refresh afterwards: the device confirms every change with a group-4
        frame, which arrives through the push path.
        """
        try:
            await command
        except Azur851Error as err:
            raise HomeAssistantError(f"Azur 851 command failed: {err}") from err


@dataclass(frozen=True, kw_only=True)
class Azur851SettingDescription[T](EntityDescription):
    """Describes one device setting: where it lives in state, which models have it."""

    value_fn: Callable[[DeviceState], T | None]
    exists_fn: Callable[[ModelCapabilities], bool]


class Azur851SettingEntity[T](Azur851Entity, RestoreEntity):
    """A device setting the amp reports only when it changes.

    There is no way to read a setting's current value, so until the amp reports
    one, the entity shows the value it last had before Home Assistant restarted
    and flags it as an assumed state. The amp also pushes every change made on
    the front panel or remote, so that value is only stale if the setting was
    changed while Home Assistant was not connected.
    """

    entity_description: Azur851SettingDescription[T]

    def __init__(
        self,
        coordinator: Azur851Coordinator,
        description: Azur851SettingDescription[T],
    ) -> None:
        """Initialize the setting entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._restored: T | None = None

    async def async_added_to_hass(self) -> None:
        """Pick up the value this setting had before the restart."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._restored = self._parse_restored(last.state)

    def _parse_restored(self, state: str) -> T | None:
        """Convert a restored state string back to this entity's value type."""
        raise NotImplementedError

    @property
    def _reported(self) -> T | None:
        """Return the value the amp has reported, if any."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def _value(self) -> T | None:
        """Return the reported value, falling back to the restored one."""
        reported = self._reported
        return self._restored if reported is None else reported

    @property
    def assumed_state(self) -> bool:
        """Return True while showing a restored value the amp has not confirmed."""
        return self._reported is None and self._restored is not None
