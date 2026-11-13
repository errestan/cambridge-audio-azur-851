"""Shared pytest fixtures for the integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
import serialx
from custom_components.cambridge_azur851.const import (
    CONF_MODEL,
    CONF_SERIAL_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in every test."""
    yield


@pytest.fixture(autouse=True)
def mock_usb_dependency(hass):
    """Mark the `usb` dependency as loaded.

    The real integration depends on `usb` (it registers the serial port selector
    and the ESPHome serial proxy handler), but the tests use a fake serial link,
    so set it up as a no-op rather than pulling in its heavy requirements.
    """
    hass.config.components.add("usb")


class _FakeWriter:
    """Minimal stand-in for serialx's stream writer; records what is sent."""

    def __init__(self, link: FakeLink) -> None:
        self._link = link

    def write(self, data: bytes) -> None:
        self._link.written.append(data)
        if self._link.reply is not None:
            self._link.readers[-1].feed_data(self._link.reply)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


class FakeLink:
    """A fake serialx link: one reader per open, and every frame written.

    Feed device frames with ``link.readers[-1].feed_data(b"#4,11,1\\r")``. Set
    ``reply`` to have the "device" answer every write with that frame.
    """

    def __init__(self) -> None:
        self.readers: list[asyncio.StreamReader] = []
        self.written: list[bytes] = []
        self.reply: bytes | None = None

    async def open(
        self, url: str, baudrate: int | None = None
    ) -> tuple[asyncio.StreamReader, _FakeWriter]:
        """Stand in for ``serialx.open_serial_connection``."""
        reader = asyncio.StreamReader()
        self.readers.append(reader)
        return reader, _FakeWriter(self)


@pytest.fixture
def fake_link(monkeypatch: pytest.MonkeyPatch) -> FakeLink:
    """Patch serialx so opening a port yields a controllable fake link."""
    link = FakeLink()
    monkeypatch.setattr(serialx, "open_serial_connection", link.open)
    return link


type SetupEntry = Callable[..., Awaitable[MockConfigEntry]]


@pytest.fixture
def setup_entry(hass: HomeAssistant, fake_link: FakeLink) -> SetupEntry:
    """Return a helper that adds and sets up a config entry over the fake link."""

    async def _setup(model: str = "851A") -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=f"Azur {model}",
            unique_id="/dev/ttyUSB0",
            data={CONF_MODEL: model, CONF_SERIAL_URL: "/dev/ttyUSB0"},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup
