"""Config flow for the Cambridge Audio Azur 851 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)

from .azur851 import Azur851Client, Azur851ConnectionError
from .const import CONF_MODEL, CONF_SERIAL_URL, DOMAIN, SUPPORTED_MODELS

_LOGGER = logging.getLogger(__name__)


# SerialPortSelector is Home Assistant's own serial picker: it lists local ports
# and ESPHome serial proxies. Proxy ports come back as `esphome-hass://` URLs,
# which serialx opens over Home Assistant's existing (already authenticated)
# ESPHome API connection -- so no separate encryption key is needed.
_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=model, label=model)
                    for model in SUPPORTED_MODELS
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_SERIAL_URL): SerialPortSelector(),
    }
)


class Azur851ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI-driven setup and reconfigure flows."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a serial port (local or ESPHome proxy) and the model."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SERIAL_URL])
            self._abort_if_unique_id_configured()

            data = self._entry_data(user_input)
            errors = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(
                    title=f"Azur {user_input[CONF_MODEL]}", data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _FORM_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the connection (serial port / model) of an entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            data = self._entry_data(user_input)
            errors = await self._async_validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        suggested = {
            CONF_MODEL: entry.data[CONF_MODEL],
            CONF_SERIAL_URL: entry.data[CONF_SERIAL_URL],
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _FORM_SCHEMA, user_input or suggested
            ),
            errors=errors,
        )

    @staticmethod
    def _entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
        """Build stored entry data from the form input."""
        return {
            CONF_MODEL: user_input[CONF_MODEL],
            CONF_SERIAL_URL: user_input[CONF_SERIAL_URL],
        }

    async def _async_validate(self, data: dict[str, Any]) -> dict[str, str]:
        """Try connecting; return form errors (empty dict means success)."""
        try:
            client = Azur851Client.from_config(data)
            await client.async_test_connection()
        except Azur851ConnectionError as err:
            _LOGGER.warning("Cannot connect to Azur 851: %s", err)
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating Azur 851 connection")
            return {"base": "unknown"}
        return {}
