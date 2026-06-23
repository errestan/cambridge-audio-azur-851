"""Per-model capability maps and the device state model.

Different Azur 851 models expose different sources and features (e.g. the 851W
power amplifier has no source selection). Keep those differences here, keyed by
model string, so the entity layer can stay model-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeviceState:
    """Snapshot of device state returned by a status poll."""

    power_on: bool | None = None
    muted: bool | None = None
    volume_raw: int | None = None  # device-native scale; convert in the entity
    source_code: int | None = None
    source_name: str | None = None


@dataclass(frozen=True)
class ModelCapabilities:
    """Describes what a given model supports."""

    model: str
    has_volume: bool = True
    has_mute: bool = True
    has_source_select: bool = True
    # Map of source name -> device-native source code.
    sources: dict[str, int] = field(default_factory=dict)
    # Device-native volume range for 0..1 scaling.
    volume_min: int = 0
    volume_max: int = 100


# TODO: Fill in real sources/codes/ranges per model from the RS-232 spec.
_CAPABILITIES: dict[str, ModelCapabilities] = {
    "851A": ModelCapabilities(model="851A"),
    "851E": ModelCapabilities(model="851E"),
    "851W": ModelCapabilities(
        model="851W", has_source_select=False, has_volume=False, has_mute=False
    ),
    "851N": ModelCapabilities(model="851N"),
    "851C": ModelCapabilities(model="851C"),
    "851D": ModelCapabilities(model="851D"),
}


def get_model_capabilities(model: str) -> ModelCapabilities:
    """Return capabilities for a model, defaulting to a generic profile."""
    return _CAPABILITIES.get(model, ModelCapabilities(model=model))
