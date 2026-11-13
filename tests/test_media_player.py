"""Media player service-call tests: each call sends the right frame."""

from __future__ import annotations

from typing import Any

import pytest
from custom_components.cambridge_azur851.azur851.models import ModelCapabilities
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
    full = _supported_features(ModelCapabilities(model="851A", sources={"Input 1": 1}))
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
