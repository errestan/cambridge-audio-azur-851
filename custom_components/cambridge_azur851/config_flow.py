"""Config flow for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .azur851 import Azur851Client, Azur851ConnectionError
from .const import CONF_MODEL, CONF_SERIAL_URL, DOMAIN, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): vol.In(SUPPORTED_MODELS),
        # serialx URL: /dev/ttyUSB0, socket://host:port, or an esphome:// proxy.
        vol.Required(CONF_SERIAL_URL): str,
    }
)


class Azur851ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI-driven setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SERIAL_URL])
            self._abort_if_unique_id_configured()

            try:
                client = Azur851Client.from_config(user_input)
                await client.async_test_connection()
            except Azur851ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Azur 851 connection")
                errors["base"] = "unknown"
            else:
                title = f"Azur {user_input[CONF_MODEL]}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
