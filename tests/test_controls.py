"""Setting entities (number/select/switch): push updates, commands, restore."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import mock_restore_cache

from .conftest import FakeLink, SetupEntry

BALANCE = "number.azur_851a_balance"
SPEAKERS = "select.azur_851a_speakers"
DIRECT = "switch.azur_851a_direct"
TAPE_MONITOR = "switch.azur_851a_tape_monitor"


@pytest.mark.parametrize(
    "case",
    [
        # Balance is shown centred on zero: device 8 is 0.
        (BALANCE, b"#4,17,08\r", "0"),
        (BALANCE, b"#4,17,00\r", "-8"),
        (BALANCE, b"#4,17,16\r", "8"),
        (SPEAKERS, b"#4,21,0\r", "a"),
        (SPEAKERS, b"#4,21,1\r", "ab"),
        (SPEAKERS, b"#4,21,2\r", "b"),
        (DIRECT, b"#4,26,1\r", "on"),
        (DIRECT, b"#4,26,0\r", "off"),
        (TAPE_MONITOR, b"#4,08,1\r", "on"),
    ],
)
async def test_update_sets_state(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[str, bytes, str],
) -> None:
    """Group-4 updates from the amp drive the setting entities."""
    entity_id, frame, expected = case
    await setup_entry()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN  # nothing reported yet

    fake_link.readers[-1].feed_data(frame)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    "case",
    [
        (NUMBER_DOMAIN, SERVICE_SET_VALUE, BALANCE, {ATTR_VALUE: 0}, b"#1,17,08\r"),
        (NUMBER_DOMAIN, SERVICE_SET_VALUE, BALANCE, {ATTR_VALUE: 8}, b"#1,17,16\r"),
        (NUMBER_DOMAIN, SERVICE_SET_VALUE, BALANCE, {ATTR_VALUE: -3}, b"#1,17,05\r"),
        (
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            SPEAKERS,
            {ATTR_OPTION: "b"},
            b"#1,21,2\r",
        ),
        (SWITCH_DOMAIN, SERVICE_TURN_ON, DIRECT, {}, b"#1,26,1\r"),
        (SWITCH_DOMAIN, SERVICE_TURN_OFF, TAPE_MONITOR, {}, b"#1,08,0\r"),
    ],
)
async def test_service_sends_frame(
    hass: HomeAssistant,
    fake_link: FakeLink,
    setup_entry: SetupEntry,
    case: tuple[str, str, str, dict[str, Any], bytes],
) -> None:
    """Each service call writes the expected 851A control frame."""
    domain, service, entity_id, data, frame = case
    await setup_entry()
    fake_link.written.clear()

    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )

    assert fake_link.written == [frame]


async def test_851e_has_only_its_settings(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    """The 851E has balance, Direct and Record in, but no speaker select."""
    await setup_entry("851E")

    entity_ids = set(hass.states.async_entity_ids(["number", "select", "switch"]))
    assert entity_ids == {
        "number.azur_851e_balance",
        "switch.azur_851e_direct",
        "switch.azur_851e_record_in",
    }


async def test_restored_value_until_amp_reports(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """Before the amp reports, show the pre-restart value as an assumed state."""
    mock_restore_cache(
        hass,
        [State(BALANCE, "3"), State(SPEAKERS, "ab"), State(DIRECT, "on")],
    )
    await setup_entry()

    for entity_id, expected in ((BALANCE, "3"), (SPEAKERS, "ab"), (DIRECT, "on")):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected
        assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # Once the amp reports, its value wins and is no longer assumed.
    fake_link.readers[-1].feed_data(b"#4,17,05\r")
    await hass.async_block_till_done()

    state = hass.states.get(BALANCE)
    assert state is not None
    assert state.state == "-3"
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_command_on_dropped_link_raises_ha_error(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    """A command while the link is down fails cleanly, not with a traceback."""
    entry = await setup_entry()
    await entry.runtime_data.client.async_close()

    with pytest.raises(HomeAssistantError, match="Azur 851 command failed"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DIRECT}, blocking=True
        )
