"""Per-model capability maps and the device state model.

Models in the 851 series do NOT share one protocol profile. Verified from the
official Serial Control Protocol documents:

  - 851A: 9600 baud, volume 00-96, has speaker select / bass / treble.
  - 851E: 115200 baud (default; also 38400/9600), volume 00-91, no tone controls.

851W (power amp), 851N (network player) and 851C (CD player) have separate
command sets; their entries below are conservative placeholders -- consult their
RS232 code pages before relying on them (see docs/protocol.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeviceState:
    """Snapshot of device state, built up from group-4 update frames."""

    power_on: bool | None = None
    muted: bool | None = None
    volume_raw: int | None = None  # device-native scale; convert in the entity
    source_code: int | None = None


@dataclass(frozen=True)
class ModelCapabilities:
    """Describes what a given model supports."""

    model: str
    baudrate: int = 9600
    has_volume: bool = True
    has_mute: bool = True
    has_source_select: bool = True
    # Map of source name -> device-native input number (control command #).
    sources: dict[str, int] = field(default_factory=dict)
    # Device-native volume range, used to scale to/from Home Assistant's 0..1.
    volume_min: int = 0
    volume_max: int = 96

    def source_name(self, code: int | None) -> str | None:
        """Resolve a device source code back to its configured name."""
        if code is None:
            return None
        for name, value in self.sources.items():
            if value == code:
                return name
        return None


_SEVEN_INPUTS: dict[str, int] = {f"Input {i}": i for i in range(1, 8)}


_CAPABILITIES: dict[str, ModelCapabilities] = {
    "851A": ModelCapabilities(
        model="851A",
        baudrate=9600,
        sources=dict(_SEVEN_INPUTS),
        volume_max=96,
    ),
    "851E": ModelCapabilities(
        model="851E",
        baudrate=115200,
        sources=dict(_SEVEN_INPUTS),
        volume_max=91,
    ),
    # TODO: verify against each model's RS232 code page.
    "851W": ModelCapabilities(
        model="851W",
        has_volume=False,
        has_mute=False,
        has_source_select=False,
    ),
    "851N": ModelCapabilities(model="851N"),
    "851C": ModelCapabilities(model="851C"),
    "851D": ModelCapabilities(model="851D"),
}


def get_model_capabilities(model: str) -> ModelCapabilities:
    """Return capabilities for a model, defaulting to a generic profile."""
    return _CAPABILITIES.get(model, ModelCapabilities(model=model))
