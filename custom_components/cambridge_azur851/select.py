"""Select platform: speaker outputs (A, A+B, B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .azur851 import Speakers
from .entity import Azur851SettingDescription, Azur851SettingEntity

if TYPE_CHECKING:
    from . import Azur851ConfigEntry

# Option keys (translated in strings.json), in device order: A=0, AB=1, B=2.
_SPEAKER_OPTIONS: dict[str, Speakers] = {
    "a": Speakers.A,
    "ab": Speakers.AB,
    "b": Speakers.B,
}


@dataclass(frozen=True, kw_only=True)
class Azur851SelectDescription(Azur851SettingDescription[int], SelectEntityDescription):
    """A setting chosen from a fixed list."""


SPEAKERS = Azur851SelectDescription(
    key="speakers",
    translation_key="speakers",
    options=list(_SPEAKER_OPTIONS),
    value_fn=lambda state: state.speakers,
    exists_fn=lambda caps: caps.has_speaker_select,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Azur851ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the speaker select on models that have one."""
    coordinator = entry.runtime_data
    if SPEAKERS.exists_fn(coordinator.client.capabilities):
        async_add_entities([Azur851SpeakerSelect(coordinator, SPEAKERS)])


class Azur851SpeakerSelect(Azur851SettingEntity[int], SelectEntity):
    """Which speaker outputs are active."""

    entity_description: Azur851SelectDescription

    def _parse_restored(self, state: str) -> int | None:
        """Turn a restored option key back into a device value."""
        speakers = _SPEAKER_OPTIONS.get(state)
        return None if speakers is None else int(speakers)

    @property
    def current_option(self) -> str | None:
        """Return the selected speaker outputs."""
        value = self._value
        for option, speakers in _SPEAKER_OPTIONS.items():
            if speakers == value:
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        """Select speaker outputs."""
        await self._async_send(
            self.coordinator.client.async_set_speakers(_SPEAKER_OPTIONS[option])
        )
