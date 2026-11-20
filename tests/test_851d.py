"""The 851D DAC: its own command set, read-back on connect, filter and phase."""

from __future__ import annotations

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

from .conftest import FakeLink, SetupEntry

PLAYER = "media_player.azur_851d"
FILTER = "select.azur_851d_filter"
PHASE = "switch.azur_851d_invert_phase"
BALANCE = "number.azur_851d_balance"
BRIGHTNESS = "select.azur_851d_display_brightness"


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

    assert set(hass.states.async_entity_ids(["number", "select", "switch"])) == {
        BALANCE,
        BRIGHTNESS,
        FILTER,
        PHASE,
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
    """Volume and filter are read back when the link comes up."""
    await setup_entry("851D")

    assert b"#1,12,\r" in fake_link.written
    assert b"#1,41,\r" in fake_link.written


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
