"""Shared pytest fixtures for the integration tests."""

from __future__ import annotations

import pytest


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


# TODO: add fixtures that provide a fake Azur851Connection / Azur851Client so the
#       config flow and coordinator can be tested without real hardware.
