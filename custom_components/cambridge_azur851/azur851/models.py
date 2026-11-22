"""Per-model capability maps and the device state model.

Models in the 851 series do NOT share one protocol profile. Verified from the
official Serial Control Protocol documents:

  - 851A: 9600 baud, volume 00-96, has speaker select.
  - 851E: 115200 baud (default; also 38400/9600), volume 00-91, no speaker
    select; its #08 is called "Record in" rather than "Tape monitor".
  - 851D: 9600 baud, a different command set altogether (``commands_851d.py``):
    volume is attenuation 000-096 dB, eight digital sources, and a selectable
    digital filter. No Direct, tape monitor or speaker select.

The 851A document also lists bass/treble (#24/#25), but a real 851A rejects
them as unknown commands, so they are not offered.

The 851W (power amp), 851N (network player) and 851C (CD player) have separate
command sets that are not implemented; any model without an entry here gets the
generic (851A-like) profile from ``get_model_capabilities``.
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
    # Whether the selected input is using its balanced (XLR) socket. Only
    # meaningful for inputs that have one (see ``Source.balanced``).
    source_balanced: bool = False
    # Settings. Like power/mute/source, the device only reports these when they
    # change, so they stay None until then. Levels are device-native.
    tape_monitor: bool | None = None
    balance: int | None = None  # 0 (left) .. 8 (centre) .. 16 (right)
    speakers: int | None = None  # commands.Speakers value
    direct: bool | None = None
    # Reported by the amp on every power-on, so it is known soon after connect.
    brightness: int | None = None  # commands.Brightness value
    # 851D only; it can be read back, so it is known soon after connect.
    filter: int | None = None  # commands_851d.Filter value
    phase_inverted: bool | None = None
    # More 851D-only values. The trigger and headphones are reported only when
    # they change; the rest can be read back.
    trigger: bool | None = None  # 12 V trigger output high
    headphones: bool | None = None  # headphones plugged in
    headphone_volume: int | None = None  # attenuation, 0 (0 dB) .. 96
    word_width: int | None = None  # bits; None when there is no valid signal
    sample_rate: int | None = None  # Hz; None when there is no valid signal
    software_version: str | None = None
    dsp_version: str | None = None
    # Source number -> name as set on the device (851D).
    source_names: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    """A selectable input: its control command number and socket.

    ``balanced`` is ``None`` for inputs with only one socket. For inputs with
    both, the device must be told which one explicitly: on the 851A *no data*
    means unbalanced, and on the 851E it toggles between the two.
    """

    number: int
    balanced: bool | None = None


@dataclass(frozen=True)
class ModelCapabilities:
    """Describes what a given model supports."""

    model: str
    # Which command set drives it: "amp" (851A/851E) or "dac" (851D).
    command_set: str = "amp"
    baudrate: int = 9600
    has_volume: bool = True
    has_mute: bool = True
    has_source_select: bool = True
    has_balance: bool = True
    has_direct: bool = True
    has_display_brightness: bool = True
    has_speaker_select: bool = False
    has_filter: bool = False
    has_trigger: bool = False
    has_headphones: bool = False
    has_signal_info: bool = False  # input word width and sample rate
    # Control #08: "tape_monitor" on the 851A, "record_in" on the 851E, or None.
    monitor: str | None = "tape_monitor"
    # Map of source name -> input (control command number + socket).
    sources: dict[str, Source] = field(default_factory=dict)
    # Device-native volume range, used to scale to/from Home Assistant's 0..1.
    volume_min: int = 0
    volume_max: int = 96
    # True when the device level is attenuation (0 = loudest), as on the 851D.
    volume_inverted: bool = False

    def source_name(self, code: int | None, balanced: bool = False) -> str | None:
        """Resolve a device input number (and socket) back to its name."""
        if code is None:
            return None
        for name, source in self.sources.items():
            if source.number == code and source.balanced in (None, balanced):
                return name
        return None


def _inputs(balanced: tuple[int, ...]) -> dict[str, Source]:
    """Inputs 1-7, with a separate balanced entry for each input in ``balanced``."""
    sources: dict[str, Source] = {}
    for i in range(1, 8):
        if i in balanced:
            sources[f"Input {i}"] = Source(i, balanced=False)
            sources[f"Input {i} (Balanced)"] = Source(i, balanced=True)
        else:
            sources[f"Input {i}"] = Source(i)
    return sources


_CAPABILITIES: dict[str, ModelCapabilities] = {
    "851A": ModelCapabilities(
        model="851A",
        baudrate=9600,
        sources=_inputs(balanced=(1, 2)),
        volume_max=96,
        has_speaker_select=True,
    ),
    "851E": ModelCapabilities(
        model="851E",
        baudrate=115200,
        sources=_inputs(balanced=(1, 2, 3)),
        volume_max=91,
        monitor="record_in",
    ),
    "851D": ModelCapabilities(
        model="851D",
        command_set="dac",
        baudrate=9600,
        sources={
            name: Source(number)
            for number, name in enumerate(
                (
                    "Input 1",
                    "Input 2",
                    "Input 3",
                    "Input 4",
                    "BNC",
                    "AES/EBU",
                    "Bluetooth",
                    "USB",
                ),
                start=1,
            )
        },
        volume_max=96,
        volume_inverted=True,
        has_direct=False,
        has_filter=True,
        has_trigger=True,
        has_headphones=True,
        has_signal_info=True,
        monitor=None,
    ),
}


def get_model_capabilities(model: str) -> ModelCapabilities:
    """Return capabilities for a model, defaulting to a generic profile."""
    return _CAPABILITIES.get(model, ModelCapabilities(model=model))
