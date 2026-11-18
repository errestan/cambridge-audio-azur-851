"""Media player service-call tests: each call sends the right frame."""

from __future__ import annotations

from typing import Any

import pytest
from custom_components.cambridge_azur851.azur851.models import (
    ModelCapabilities,
    Source,
)
from custom_components.cambridge_azur851.media_player import _supported_features
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
)
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

ENTITY_ID = "media_player.azur_851a"


@pytest.mark.parametrize(
    "case",
    [
        (SERVICE_TURN_ON, {}, b"#1,11,1\r"),
        (SERVICE_TURN_OFF, {}, b"#1,11,0\r"),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.5}, b"#1,13,48\r"),
        # Control-command mute encoding is inverted: 0 = mute ON.
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, b"#1,12,0\r"),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}, b"#1,12,1\r"),
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "Input 3"}, b"#1,03,\r"),
        # Dual-socket inputs always name the socket explicitly.
        (SERVICE_SELECT_SOURCE, {ATTR_INPUT_SOURCE: "Input 1"}, b"#1,01,0\r"),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "Input 2 (Balanced)"},
            b"#1,02,1\r",
        ),
    ],
)
async def test_service_sends_frame(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[str, dict[str, Any], bytes],
) -> None:
    """Each service call writes the expected 851A control frame."""
    service, data, frame = case
    await setup_entry()
    fake_link.written.clear()

    await hass.services.async_call(
        MP_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
    )

    assert fake_link.written == [frame]


@pytest.mark.parametrize(
    "case",
    [
        (b"#4,01,1\r", "Input 1 (Balanced)"),
        (b"#4,01,\r", "Input 1"),
        (b"#4,05,\r", "Input 5"),
    ],
)
async def test_source_reports_socket(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[bytes, str],
) -> None:
    """Input updates distinguish the balanced and unbalanced sockets."""
    frame, source = case
    await setup_entry()

    fake_link.readers[-1].feed_data(frame)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == source


async def test_851e_source_list_has_balanced_input_3(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    """The 851E has a balanced socket on input 3 as well; the 851A does not."""
    await setup_entry("851E")

    state = hass.states.get("media_player.azur_851e")
    assert state is not None
    assert "Input 3 (Balanced)" in state.attributes["source_list"]
    assert "Input 4 (Balanced)" not in state.attributes["source_list"]


@pytest.mark.parametrize("case", [(b"#4,11,1\r", "on"), (b"#4,11,0\r", "off")])
async def test_power_state(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[bytes, str],
) -> None:
    """Power updates map to on / off (standby is reported as off)."""
    frame, expected = case
    await setup_entry()

    fake_link.readers[-1].feed_data(frame)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


async def test_command_on_dropped_link_raises_ha_error(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    """A command while the link is down fails cleanly, not with a traceback."""
    entry = await setup_entry()
    await entry.runtime_data.client.async_close()

    with pytest.raises(HomeAssistantError, match="Azur 851 command failed"):
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )


def test_supported_features_follow_capabilities() -> None:
    """Features are derived from the model's capability map."""
    full = _supported_features(
        ModelCapabilities(model="851A", sources={"Input 1": Source(1)})
    )
    assert full & MediaPlayerEntityFeature.VOLUME_SET
    assert full & MediaPlayerEntityFeature.VOLUME_MUTE
    assert full & MediaPlayerEntityFeature.SELECT_SOURCE

    power_only = _supported_features(
        ModelCapabilities(
            model="x", has_volume=False, has_mute=False, has_source_select=False
        )
    )
    assert power_only == (
        MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
    )
