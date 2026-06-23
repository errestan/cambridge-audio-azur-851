"""Config flow for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .azur851 import Azur851Client, Azur851ConnectionError
from .const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
    SUPPORTED_MODELS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): vol.In(SUPPORTED_MODELS),
        # Serial-proxy / network bridge address.
        # TODO: align fields with the chosen serial-proxy connection scheme.
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
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
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()

            try:
                # Validate by opening a connection and reading identity/state.
                client = Azur851Client.from_config(user_input)
                await client.async_test_connection()
                await client.async_close()
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
