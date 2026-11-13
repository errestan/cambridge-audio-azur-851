"""Setup/unload and end-to-end push tests for the integration.

Drives the real client/coordinator/entity stack over a fake serialx link
(see ``FakeLink`` in conftest.py).
"""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FakeLink, SetupEntry


async def test_setup_creates_media_player(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """Setting up the entry loads it and creates one media_player entity."""
    entry = await setup_entry()

    assert entry.state is ConfigEntryState.LOADED
    assert len(fake_link.readers) == 1  # the connection was opened
    assert len(hass.states.async_all("media_player")) == 1


async def test_setup_requests_state(
    fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """On connect, Volume stop is sent so the device reports its volume."""
    await setup_entry()

    assert b"#1,16,\r" in fake_link.written


async def test_push_updates_entity_state(
    hass: HomeAssistant, fake_link: FakeLink, setup_entry: SetupEntry
) -> None:
    """Unsolicited group-4 frames update the media_player state."""
    await setup_entry()
    entity_id = hass.states.async_all("media_player")[0].entity_id

    fake_link.readers[0].feed_data(b"#4,11,1\r")  # power on
    fake_link.readers[0].feed_data(b"#4,13,48\r")  # volume 48 / 96 == 0.5
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["volume_level"] == pytest.approx(0.5, abs=0.02)


async def test_unload(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Unloading the entry tears it down cleanly."""
    entry = await setup_entry()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
