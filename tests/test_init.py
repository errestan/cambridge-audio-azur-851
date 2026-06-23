"""Setup/unload and end-to-end push tests for the integration.

Drives the real client/coordinator/entity stack over a fake serialx link.
"""

from __future__ import annotations

import asyncio

import pytest
import serialx
from custom_components.cambridge_azur851.const import (
    CONF_MODEL,
    CONF_SERIAL_URL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


class _FakeWriter:
    """Minimal stand-in for serialx's stream writer."""

    def __init__(self) -> None:
        self.written: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


@pytest.fixture
def fake_link(monkeypatch: pytest.MonkeyPatch) -> list[asyncio.StreamReader]:
    """Patch serialx so opening a link yields a controllable reader."""
    readers: list[asyncio.StreamReader] = []

    def _open(url: str, baudrate: int | None = None):
        async def _connect():
            reader = asyncio.StreamReader()
            readers.append(reader)
            return reader, _FakeWriter()

        return _connect()

    monkeypatch.setattr(serialx, "open_serial_connection", _open)
    return readers


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Azur 851A",
        unique_id="/dev/ttyUSB0",
        data={CONF_MODEL: "851A", CONF_SERIAL_URL: "/dev/ttyUSB0"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_creates_media_player(
    hass: HomeAssistant, fake_link: list[asyncio.StreamReader]
) -> None:
    """Setting up the entry loads it and creates one media_player entity."""
    entry = await _setup(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert len(fake_link) == 1  # the connection was opened
    assert len(hass.states.async_all("media_player")) == 1


async def test_push_updates_entity_state(
    hass: HomeAssistant, fake_link: list[asyncio.StreamReader]
) -> None:
    """Unsolicited group-4 frames update the media_player state."""
    await _setup(hass)
    entity_id = hass.states.async_all("media_player")[0].entity_id

    fake_link[0].feed_data(b"#4,11,1\r")  # power on
    fake_link[0].feed_data(b"#4,13,48\r")  # volume 48 / 96 == 0.5
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["volume_level"] == pytest.approx(0.5, abs=0.02)


async def test_unload(
    hass: HomeAssistant, fake_link: list[asyncio.StreamReader]
) -> None:
    """Unloading the entry tears it down cleanly."""
    entry = await _setup(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
