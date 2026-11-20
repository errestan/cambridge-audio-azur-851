"""Select platform: speaker outputs, display brightness and the 851D filter."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .azur851 import Azur851Client, Brightness, Filter, Speakers
from .entity import Azur851SettingDescription, Azur851SettingEntity

if TYPE_CHECKING:
    from . import Azur851ConfigEntry


@dataclass(frozen=True, kw_only=True)
class Azur851SelectDescription(Azur851SettingDescription[int], SelectEntityDescription):
    """A setting chosen from a fixed list.

    ``values`` maps each option key (translated in strings.json) to the
    device's data value; ``options`` is derived from it.
    """

    values: dict[str, int]
    set_fn: Callable[[Azur851Client, int], Awaitable[None]]


SELECTS: tuple[Azur851SelectDescription, ...] = (
    Azur851SelectDescription(
        key="speakers",
        translation_key="speakers",
        values={"a": Speakers.A, "ab": Speakers.AB, "b": Speakers.B},
        options=["a", "ab", "b"],
        value_fn=lambda state: state.speakers,
        exists_fn=lambda caps: caps.has_speaker_select,
        set_fn=lambda client, value: client.async_set_speakers(Speakers(value)),
    ),
    Azur851SelectDescription(
        key="display_brightness",
        translation_key="display_brightness",
        entity_category=EntityCategory.CONFIG,
        values={
            "off": Brightness.OFF,
            "dim": Brightness.DIM,
            "bright": Brightness.BRIGHT,
        },
        options=["off", "dim", "bright"],
        value_fn=lambda state: state.brightness,
        exists_fn=lambda caps: caps.has_display_brightness,
        set_fn=lambda client, value: client.async_set_brightness(Brightness(value)),
    ),
    Azur851SelectDescription(
        key="filter",
        translation_key="filter",
        entity_category=EntityCategory.CONFIG,
        values={
            "linear": Filter.LINEAR,
            "minimum": Filter.MINIMUM,
            "steep": Filter.STEEP,
        },
        options=["linear", "minimum", "steep"],
        value_fn=lambda state: state.filter,
        exists_fn=lambda caps: caps.has_filter,
        set_fn=lambda client, value: client.async_set_filter(Filter(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Azur851ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select settings this model has."""
    coordinator = entry.runtime_data
    caps = coordinator.client.capabilities
    async_add_entities(
        Azur851Select(coordinator, description)
        for description in SELECTS
        if description.exists_fn(caps)
    )


class Azur851Select(Azur851SettingEntity[int], SelectEntity):
    """A device setting chosen from a fixed list."""

    entity_description: Azur851SelectDescription

    def _parse_restored(self, state: str) -> int | None:
        """Turn a restored option key back into a device value."""
        return self.entity_description.values.get(state)

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        value = self._value
        for option, device_value in self.entity_description.values.items():
            if device_value == value:
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self._async_send(
            self.entity_description.set_fn(
                self.coordinator.client, self.entity_description.values[option]
            )
        )
