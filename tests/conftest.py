"""Shared pytest fixtures for the integration tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in every test."""
    yield


# TODO: add fixtures that provide a fake Azur851Connection / Azur851Client so the
#       config flow and coordinator can be tested without real hardware.
