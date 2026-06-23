"""Config flow tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.cambridge_azur851.azur851 import Azur851ConnectionError
from custom_components.cambridge_azur851.const import (
    CONF_KEY,
    CONF_MODEL,
    CONF_SERIAL_URL,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

_TEST_CONNECTION = (
    "custom_components.cambridge_azur851.config_flow."
    "Azur851Client.async_test_connection"
)


@pytest.fixture(autouse=True)
def _no_discovery():
    """Skip real serial enumeration when building the form schema."""
    with patch(
        "custom_components.cambridge_azur851.config_flow.async_discover_ports",
        return_value=[],
    ):
        yield


async def _start(hass: HomeAssistant) -> str:
    """Begin the user flow and return the flow id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A valid connection creates an entry with the expected data."""
    flow_id = await _start(hass)
    with (
        patch(_TEST_CONNECTION, new=AsyncMock()),
        patch(
            "custom_components.cambridge_azur851.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_MODEL: "851A", CONF_SERIAL_URL: "/dev/ttyUSB0"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Azur 851A"
    assert result["data"] == {CONF_MODEL: "851A", CONF_SERIAL_URL: "/dev/ttyUSB0"}


async def test_user_flow_folds_esphome_key(hass: HomeAssistant) -> None:
    """The encryption key is merged into the URL and not stored separately."""
    flow_id = await _start(hass)
    with (
        patch(_TEST_CONNECTION, new=AsyncMock()),
        patch(
            "custom_components.cambridge_azur851.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_MODEL: "851E",
                CONF_SERIAL_URL: "esphome://10.0.0.5:6053/?port_name=851E",
                CONF_KEY: "SECRET_PSK",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"][CONF_SERIAL_URL]
        == "esphome://10.0.0.5:6053/?port_name=851E&key=SECRET_PSK"
    )
    assert CONF_KEY not in result["data"]


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """A connection error is surfaced as a form error, not a crash."""
    flow_id = await _start(hass)
    with patch(_TEST_CONNECTION, side_effect=Azur851ConnectionError):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_MODEL: "851A", CONF_SERIAL_URL: "socket://10.0.0.9:1"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """An unexpected error maps to the 'unknown' form error."""
    flow_id = await _start(hass)
    with patch(_TEST_CONNECTION, side_effect=RuntimeError("boom")):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_MODEL: "851A", CONF_SERIAL_URL: "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Re-adding the same serial URL aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={CONF_MODEL: "851A", CONF_SERIAL_URL: "/dev/ttyUSB0"},
    ).add_to_hass(hass)

    flow_id = await _start(hass)
    with patch(_TEST_CONNECTION, new=AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_MODEL: "851A", CONF_SERIAL_URL: "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
