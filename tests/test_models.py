"""Model support: only verified models are offered; older entries still load."""

from __future__ import annotations

import pytest
import serialx
from custom_components.cambridge_azur851.const import (
    CONF_MODEL,
    CONF_SERIAL_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_unsupported_model_entry_warns(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An entry for a model no longer offered in setup is flagged at setup."""

    async def _unreachable(url: str, baudrate: int | None = None):
        raise OSError("no device in tests")

    monkeypatch.setattr(serialx, "open_serial_connection", _unreachable)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Azur 851D",
        data={CONF_MODEL: "851D", CONF_SERIAL_URL: "/dev/ttyUSB0"},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Logged before connecting, so the (unreachable) port does not matter.
    assert "Azur 851D is not a supported model" in caplog.text
