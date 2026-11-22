"""Sensor platform: the 851D's input sample rate and bit depth."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfFrequency, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .azur851.models import DeviceState, ModelCapabilities
from .entity import Azur851Entity

if TYPE_CHECKING:
    from . import Azur851ConfigEntry
    from .coordinator import Azur851Coordinator


@dataclass(frozen=True, kw_only=True)
class Azur851SensorDescription(SensorEntityDescription):
    """A value read from the device."""

    value_fn: Callable[[DeviceState], int | None]
    exists_fn: Callable[[ModelCapabilities], bool]


SENSORS: tuple[Azur851SensorDescription, ...] = (
    Azur851SensorDescription(
        key="sample_rate",
        translation_key="sample_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_unit_of_measurement=UnitOfFrequency.KILOHERTZ,
        suggested_display_precision=1,
        value_fn=lambda state: state.sample_rate,
        exists_fn=lambda caps: caps.has_signal_info,
    ),
    Azur851SensorDescription(
        key="bit_depth",
        translation_key="bit_depth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.BITS,
        value_fn=lambda state: state.word_width,
        exists_fn=lambda caps: caps.has_signal_info,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Azur851ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors this model has."""
    coordinator = entry.runtime_data
    caps = coordinator.client.capabilities
    async_add_entities(
        Azur851Sensor(coordinator, description)
        for description in SENSORS
        if description.exists_fn(caps)
    )


class Azur851Sensor(Azur851Entity, SensorEntity):
    """A value read from the device.

    Unknown while there is no valid input signal, e.g. in standby.
    """

    entity_description: Azur851SensorDescription

    def __init__(
        self,
        coordinator: Azur851Coordinator,
        description: Azur851SensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        """Return the value."""
        return self.entity_description.value_fn(self.coordinator.data)
