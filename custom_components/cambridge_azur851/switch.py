"""Switch platform: Direct, tape monitor (851E: record in), 851D phase/trigger."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .azur851 import Azur851Client
from .entity import Azur851SettingDescription, Azur851SettingEntity

if TYPE_CHECKING:
    from . import Azur851ConfigEntry


@dataclass(frozen=True, kw_only=True)
class Azur851SwitchDescription(
    Azur851SettingDescription[bool], SwitchEntityDescription
):
    """An on/off setting."""

    set_fn: Callable[[Azur851Client, bool], Awaitable[None]]


SWITCHES: tuple[Azur851SwitchDescription, ...] = (
    Azur851SwitchDescription(
        key="direct",
        translation_key="direct",
        value_fn=lambda state: state.direct,
        exists_fn=lambda caps: caps.has_direct,
        set_fn=lambda client, on: client.async_set_direct(on),
    ),
    # Control #08 is the same command on both models but named differently.
    Azur851SwitchDescription(
        key="tape_monitor",
        translation_key="tape_monitor",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.tape_monitor,
        exists_fn=lambda caps: caps.monitor == "tape_monitor",
        set_fn=lambda client, on: client.async_set_tape_monitor(on),
    ),
    Azur851SwitchDescription(
        key="record_in",
        translation_key="record_in",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.tape_monitor,
        exists_fn=lambda caps: caps.monitor == "record_in",
        set_fn=lambda client, on: client.async_set_tape_monitor(on),
    ),
    Azur851SwitchDescription(
        key="phase_inverted",
        translation_key="phase_inverted",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.phase_inverted,
        exists_fn=lambda caps: caps.has_filter,
        set_fn=lambda client, on: client.async_set_phase_inverted(on),
    ),
    Azur851SwitchDescription(
        key="trigger",
        translation_key="trigger",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.trigger,
        exists_fn=lambda caps: caps.has_trigger,
        set_fn=lambda client, on: client.async_set_trigger(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Azur851ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the on/off settings this model has."""
    coordinator = entry.runtime_data
    caps = coordinator.client.capabilities
    async_add_entities(
        Azur851Switch(coordinator, description)
        for description in SWITCHES
        if description.exists_fn(caps)
    )


class Azur851Switch(Azur851SettingEntity[bool], SwitchEntity):
    """An on/off device setting."""

    entity_description: Azur851SwitchDescription

    def _parse_restored(self, state: str) -> bool | None:
        """Turn a restored on/off state back into a bool."""
        return state == STATE_ON

    @property
    def is_on(self) -> bool | None:
        """Return True if the setting is on."""
        return self._value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._async_send(
            self.entity_description.set_fn(self.coordinator.client, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._async_send(
            self.entity_description.set_fn(self.coordinator.client, False)
        )
