"""The 851D DAC: its own command set, read-back on connect, filter and phase."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from custom_components.cambridge_azur851.azur851 import commands_851d
from custom_components.cambridge_azur851.azur851.protocol import encode
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import FakeLink, SetupEntry

PLAYER = "media_player.azur_851d"
FILTER = "select.azur_851d_filter"
PHASE = "switch.azur_851d_invert_phase"
BALANCE = "number.azur_851d_balance"
BRIGHTNESS = "select.azur_851d_display_brightness"
TRIGGER = "switch.azur_851d_trigger_out"
HEADPHONE_VOLUME = "number.azur_851d_headphone_volume"
HEADPHONES = "binary_sensor.azur_851d_headphones"
SAMPLE_RATE = "sensor.azur_851d_sample_rate"
BIT_DEPTH = "sensor.azur_851d_bit_depth"


async def _settle(hass: HomeAssistant) -> None:
    """Let follow-up queries (a plain asyncio task) run, then wait for HA."""
    await hass.async_block_till_done()
    await asyncio.sleep(0.01)
    await hass.async_block_till_done()


def test_command_encoding() -> None:
    """851D frames follow its own document, not the amps'."""
    assert encode(commands_851d.power(True)) == b"#1,14,1\r"
    assert encode(commands_851d.mute(True)) == b"#1,44,\r"
    assert encode(commands_851d.mute(False)) == b"#1,45,\r"
    assert encode(commands_851d.set_volume(5)) == b"#1,13,005\r"
    assert encode(commands_851d.select_source(8)) == b"#1,01,8\r"
    assert encode(commands_851d.set_balance(8)) == b"#1,46,08\r"
    assert encode(commands_851d.lcd_brightness(2)) == b"#1,15,2\r"
    f = commands_851d.Filter
    assert encode(commands_851d.select_filter(f.LINEAR)) == b"#1,40,1\r"
    assert encode(commands_851d.select_filter(f.STEEP, True)) == b"#1,40,3,1\r"
    for bad in (
        lambda: commands_851d.set_volume(97),
        lambda: commands_851d.select_source(0),
        lambda: commands_851d.set_balance(17),
    ):
        with pytest.raises(ValueError):
            bad()


async def test_entities(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """The 851D gets balance, brightness, filter and phase; no amp-only settings."""
    await setup_entry("851D")

    assert set(
        hass.states.async_entity_ids(
            ["binary_sensor", "number", "select", "sensor", "switch"]
        )
    ) == {
        BALANCE,
        BRIGHTNESS,
        FILTER,
        PHASE,
        TRIGGER,
        HEADPHONE_VOLUME,
        HEADPHONES,
        SAMPLE_RATE,
        BIT_DEPTH,
    }
    state = hass.states.get(PLAYER)
    assert state is not None
    assert state.attributes["source_list"] == [
        "Input 1",
        "Input 2",
        "Input 3",
        "Input 4",
        "BNC",
        "AES/EBU",
        "Bluetooth",
        "USB",
    ]


async def test_reads_state_on_connect(
    fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """Everything that can be read back is asked for when the link comes up."""
    await setup_entry("851D")

    for query in (b"#1,12,", b"#1,41,", b"#1,04,", b"#1,05,", b"#1,50,"):
        assert query + b"\r" in fake_link.written
    assert b"#2,01,\r" in fake_link.written
    assert b"#2,05,1,\r" in fake_link.written
    assert b"#2,05,8,\r" in fake_link.written


@pytest.mark.parametrize(
    "case",
    [
        (b"#3,14,1\r", PLAYER, "state", "on"),
        (b"#3,14,0\r", PLAYER, "state", "off"),
        # Volume is attenuation: 000 is full volume.
        (b"#3,12,000\r", PLAYER, "volume_level", 1.0),
        (b"#3,13,096\r", PLAYER, "volume_level", 0.0),
        (b"#3,42,048\r", PLAYER, "volume_level", 0.5),
        (b"#3,44,\r", PLAYER, "is_volume_muted", True),
        (b"#3,45,\r", PLAYER, "is_volume_muted", False),
        (b"#3,01,6\r", PLAYER, "source", "AES/EBU"),
        (b"#3,46,05\r", BALANCE, "state", "-3"),
        (b"#3,47,09\r", BALANCE, "state", "1"),
        (b"#3,15,1\r", BRIGHTNESS, "state", "dim"),
        (b"#3,41,2,0\r", FILTER, "state", "minimum"),
        # A real 851D reports filter changes as #3,40, not #3,41.
        (b"#3,40,3,0\r", FILTER, "state", "steep"),
        # ... and sometimes sends a NUL before a frame.
        (b"\x00#3,15,2\r", BRIGHTNESS, "state", "bright"),
        (b"#3,49,1\r", TRIGGER, "state", "on"),
        (b"#3,22,1\r", HEADPHONES, "state", "on"),
        (b"#3,22,0\r", HEADPHONES, "state", "off"),
        (b"#3,50,035\r", HEADPHONE_VOLUME, "state", "-35"),
        (b"#3,52,034\r", HEADPHONE_VOLUME, "state", "-34"),
        (b"#3,05,02\r", SAMPLE_RATE, "state", "44.1"),
        (b"#3,05,07\r", SAMPLE_RATE, "state", "192.0"),
        (b"#3,05,00\r", SAMPLE_RATE, "state", "unknown"),
        (b"#3,04,09\r", BIT_DEPTH, "state", "24"),
        (b"#3,04,01\r", BIT_DEPTH, "state", "16"),
        (b"#3,41,3,1\r", PHASE, "state", "on"),
    ],
)
async def test_reply_updates_state(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[bytes, str, str, Any],
) -> None:
    """Group-3 replies drive the 851D's entities."""
    frame, entity_id, attribute, expected = case
    await setup_entry("851D")
    fake_link.readers[-1].feed_data(b"#3,14,1\r")  # attributes need it on
    fake_link.readers[-1].feed_data(frame)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    value = state.state if attribute == "state" else state.attributes.get(attribute)
    assert value == expected


async def test_amp_frames_are_ignored(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """An 851A-style update means nothing to the 851D."""
    await setup_entry("851D")
    fake_link.readers[-1].feed_data(b"#4,11,1\r")
    await hass.async_block_till_done()

    state = hass.states.get(PLAYER)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    "case",
    [
        (MP_DOMAIN, SERVICE_TURN_ON, PLAYER, {}, b"#1,14,1\r"),
        (MP_DOMAIN, SERVICE_TURN_OFF, PLAYER, {}, b"#1,14,0\r"),
        (
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            PLAYER,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.75},
            b"#1,13,024\r",
        ),
        (
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            PLAYER,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            b"#1,44,\r",
        ),
        (
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            PLAYER,
            {ATTR_MEDIA_VOLUME_MUTED: False},
            b"#1,45,\r",
        ),
        (
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            PLAYER,
            {ATTR_INPUT_SOURCE: "USB"},
            b"#1,01,8\r",
        ),
        (NUMBER_DOMAIN, SERVICE_SET_VALUE, BALANCE, {ATTR_VALUE: 2}, b"#1,46,10\r"),
        (
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            BRIGHTNESS,
            {ATTR_OPTION: "off"},
            b"#1,15,0\r",
        ),
        (
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            FILTER,
            {ATTR_OPTION: "steep"},
            b"#1,40,3\r",
        ),
    ],
)
async def test_service_sends_frame(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[str, str, str, dict[str, Any], bytes],
) -> None:
    """Each service call writes the expected 851D frame."""
    domain, service, entity_id, data, frame = case
    await setup_entry("851D")
    fake_link.written.clear()

    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )

    assert fake_link.written == [frame]


async def test_phase_keeps_current_filter(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """Phase is set together with the filter, so the current filter is resent."""
    await setup_entry("851D")
    fake_link.readers[-1].feed_data(b"#3,41,2,0\r")
    await hass.async_block_till_done()
    fake_link.written.clear()

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: PHASE}, blocking=True
    )

    assert fake_link.written == [b"#1,40,2,1\r"]


async def test_phase_needs_known_filter(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    """Without the current filter, the phase cannot be set safely."""
    await setup_entry("851D")

    with pytest.raises(HomeAssistantError, match="filter is not known"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: PHASE}, blocking=True
        )


async def test_error_reply_is_logged(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """851D error numbers are its own (1-3), not the amps' (7-9)."""
    entry = await setup_entry("851D")
    await entry.runtime_data.client.async_power(True)
    fake_link.readers[-1].feed_data(b"#5,02,\r")
    await hass.async_block_till_done()

    assert "Azur 851D rejected #1,14,1: unknown command number" in caplog.text


async def test_source_names_from_device(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """Names set on the 851D replace the defaults, cleaned of padding and noise."""
    await setup_entry("851D")
    reader = fake_link.readers[-1]
    reader.feed_data(b"#4,05,1, TV     \r#4,05,7,\x07 BTooth\r#4,05,8,     USB\r")
    reader.feed_data(b"#4,05,2,TV\r")  # duplicate names stay distinct
    reader.feed_data(b"#3,14,1\r#3,01,7\r")
    await hass.async_block_till_done()

    state = hass.states.get(PLAYER)
    assert state is not None
    assert state.attributes["source_list"] == [
        "TV",
        "TV (2)",
        "Input 3",
        "Input 4",
        "BNC",
        "AES/EBU",
        "BTooth",
        "USB",
    ]
    assert state.attributes["source"] == "BTooth"

    fake_link.written.clear()
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: PLAYER, ATTR_INPUT_SOURCE: "TV (2)"},
        blocking=True,
    )
    assert fake_link.written == [b"#1,01,2\r"]


@pytest.mark.parametrize(
    "case",
    [
        # From -35 dB: louder steps up, quieter steps down.
        (-32, [b"#1,52,\r"] * 3),
        (-37, [b"#1,53,\r"] * 2),
        (-35, []),
    ],
)
async def test_headphone_volume_steps(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[int, list[bytes]],
) -> None:
    """Headphone volume can only step, so setting it sends the right steps."""
    target, frames = case
    await setup_entry("851D")
    fake_link.readers[-1].feed_data(b"#3,50,035\r")
    await _settle(hass)
    fake_link.written.clear()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: HEADPHONE_VOLUME, ATTR_VALUE: target},
        blocking=True,
    )

    assert fake_link.written == frames


async def test_headphone_volume_unavailable_when_unplugged(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """With headphones out the volume cannot change, so it is unavailable."""
    await setup_entry("851D")
    fake_link.readers[-1].feed_data(b"#3,50,035\r#3,22,0\r")
    await hass.async_block_till_done()

    state = hass.states.get(HEADPHONE_VOLUME)
    assert state is not None
    assert state.state == "unavailable"


async def test_trigger_sends_frame(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """The trigger switch drives the 12 V trigger output."""
    await setup_entry("851D")
    fake_link.written.clear()

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TRIGGER}, blocking=True
    )

    assert fake_link.written == [b"#1,49,1\r"]


@pytest.mark.parametrize(
    "case",
    [
        (b"#3,01,3\r", [b"#1,04,\r", b"#1,05,\r"]),
        (b"#3,14,1\r", [b"#1,04,\r", b"#1,05,\r"]),
        (b"#3,22,1\r", [b"#1,50,\r"]),
        (b"#3,14,0\r", []),
    ],
)
async def test_follow_up_queries(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[bytes, list[bytes]],
) -> None:
    """After a source change, power-on or headphones in, re-read what changed."""
    frame, queries = case
    await setup_entry("851D")
    fake_link.written.clear()

    fake_link.readers[-1].feed_data(frame)
    await _settle(hass)

    assert fake_link.written == queries


async def test_poll_reads_signal_while_on(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """The input signal is polled while the 851D is on, not in standby."""
    await setup_entry("851D")
    reader = fake_link.readers[-1]

    reader.feed_data(b"#3,14,0\r")
    await _settle(hass)
    fake_link.written.clear()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert fake_link.written == []

    reader.feed_data(b"#3,14,1\r")
    await _settle(hass)
    fake_link.written.clear()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=62))
    await hass.async_block_till_done()
    assert fake_link.written == [b"#1,04,\r", b"#1,05,\r"]


async def test_versions_on_device_page(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """Software and DSP versions show on the device; standby's 00.00 is ignored."""
    entry = await setup_entry("851D")
    fake_link.readers[-1].feed_data(b"#4,01,1.7 \r#4,02,00.00\r")
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    (device,) = dr.async_entries_for_config_entry(registry, entry.entry_id)
    assert device.sw_version == "1.7"

    fake_link.readers[-1].feed_data(b"#4,02,16.59\r")
    await hass.async_block_till_done()
    device = registry.async_get(device.id)
    assert device is not None
    assert device.sw_version == "1.7 (DSP 16.59)"
