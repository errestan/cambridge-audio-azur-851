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
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .azur851 import (
    Azur851Client,
    Azur851ConnectionError,
    async_discover_ports,
    build_serial_url,
)
from .const import (
    CONF_KEY,
    CONF_MODEL,
    CONF_SERIAL_URL,
    DOMAIN,
    SUPPORTED_MODELS,
)

_LOGGER = logging.getLogger(__name__)


class Azur851ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI-driven setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered port (or type a URL) and the model."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SERIAL_URL])
            self._abort_if_unique_id_configured()

            # Fold any ESPHome encryption key into the URL; store the result so
            # the key is not kept as a separate config value.
            data = {
                CONF_MODEL: user_input[CONF_MODEL],
                CONF_SERIAL_URL: build_serial_url(
                    user_input[CONF_SERIAL_URL], user_input.get(CONF_KEY)
                ),
            }

            try:
                client = Azur851Client.from_config(data)
                await client.async_test_connection()
            except Azur851ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Azur 851 connection")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Azur {user_input[CONF_MODEL]}", data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=await self._async_user_schema(),
            errors=errors,
        )

    async def _async_user_schema(self) -> vol.Schema:
        """Build the form schema, populating the port picker from discovery."""
        ports = await async_discover_ports()
        port_options = [
            SelectOptionDict(value=port.device, label=port.label) for port in ports
        ]
        return vol.Schema(
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
                # custom_value=True lets the user pick a discovered port OR type a
                # URL (socket://host:port, esphome://host:6053/?port_name=...).
                vol.Required(CONF_SERIAL_URL): SelectSelector(
                    SelectSelectorConfig(
                        options=port_options,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                # Only needed for an encrypted ESPHome serial proxy.
                vol.Optional(CONF_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
