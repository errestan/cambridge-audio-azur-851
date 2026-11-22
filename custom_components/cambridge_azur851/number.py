"""Number platform: balance, and the 851D's headphone volume."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .azur851 import Azur851Client
from .azur851.commands import BALANCE_CENTRE, BALANCE_MAX, BALANCE_MIN
from .azur851.commands_851d import VOLUME_MAX, VOLUME_MIN
from .entity import Azur851Entity, Azur851SettingDescription, Azur851SettingEntity

if TYPE_CHECKING:
    from . import Azur851ConfigEntry
    from .coordinator import Azur851Coordinator


@dataclass(frozen=True, kw_only=True)
class Azur851NumberDescription(Azur851SettingDescription[int], NumberEntityDescription):
    """A level setting, shown centred on zero.

    The device counts from 0, with neutral in the middle (balance 8).
    Home Assistant shows ``device value - offset``, so neutral reads as 0 and
    balance goes negative to the left.
    """

    offset: int
    set_fn: Callable[[Azur851Client, int], Awaitable[None]]


NUMBERS: tuple[Azur851NumberDescription, ...] = (
    Azur851NumberDescription(
        key="balance",
        translation_key="balance",
        entity_category=EntityCategory.CONFIG,
        native_min_value=BALANCE_MIN - BALANCE_CENTRE,
        native_max_value=BALANCE_MAX - BALANCE_CENTRE,
        offset=BALANCE_CENTRE,
        value_fn=lambda state: state.balance,
        exists_fn=lambda caps: caps.has_balance,
        set_fn=lambda client, level: client.async_set_balance(level),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Azur851ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the level settings this model has."""
    coordinator = entry.runtime_data
    caps = coordinator.client.capabilities
    entities: list[NumberEntity] = [
        Azur851Number(coordinator, description)
        for description in NUMBERS
        if description.exists_fn(caps)
    ]
    if caps.has_headphones:
        entities.append(Azur851HeadphoneVolume(coordinator))
    async_add_entities(entities)


class Azur851Number(Azur851SettingEntity[int], NumberEntity):
    """A level setting such as balance."""

    entity_description: Azur851NumberDescription
    _attr_native_step = 1

    def _parse_restored(self, state: str) -> int | None:
        """Turn a restored (displayed) value back into a device level."""
        try:
            return round(float(state)) + self.entity_description.offset
        except ValueError:
            return None

    @property
    def native_value(self) -> int | None:
        """Return the level, centred on zero."""
        value = self._value
        return None if value is None else value - self.entity_description.offset

    async def async_set_native_value(self, value: float) -> None:
        """Set the level."""
        level = round(value) + self.entity_description.offset
        await self._async_send(
            self.entity_description.set_fn(self.coordinator.client, level)
        )


class Azur851HeadphoneVolume(Azur851Entity, NumberEntity):
    """The 851D's headphone volume, in dB (0 is loudest).

    The device can report it at any time, but only changes it while headphones
    are plugged in, so the entity is unavailable while they are out.
    """

    _attr_translation_key = "headphone_volume"
    _attr_native_min_value = -VOLUME_MAX
    _attr_native_max_value = -VOLUME_MIN
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL

    def __init__(self, coordinator: Azur851Coordinator) -> None:
        """Initialize the headphone volume."""
        super().__init__(coordinator, "headphone_volume")

    @property
    def available(self) -> bool:
        """Return False while headphones are known to be unplugged."""
        return super().available and self.coordinator.data.headphones is not False

    @property
    def native_value(self) -> int | None:
        """Return the volume in dB (attenuation as a negative number)."""
        level = self.coordinator.data.headphone_volume
        return None if level is None else -level

    async def async_set_native_value(self, value: float) -> None:
        """Set the volume in dB."""
        await self._async_send(
            self.coordinator.client.async_set_headphone_volume(-round(value))
        )
