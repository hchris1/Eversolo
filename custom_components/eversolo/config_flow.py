"""Adds config flow for Eversolo."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    EversoloApiClient,
    EversoloApiClientAuthenticationError,
    EversoloApiClientCommunicationError,
    EversoloApiClientError,
)
from .const import DEFAULT_PORT, DOMAIN, LOGGER


class EversoloFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Eversolo."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    host=user_input[CONF_HOST], port=user_input[CONF_PORT]
                )
            except EversoloApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except EversoloApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except EversoloApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(user_input or {}).get(CONF_HOST),
                    ): cv.string,
                    vol.Required(
                        CONF_PORT,
                        default=DEFAULT_PORT,
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                            ),
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
            errors=_errors,
        )

    async def _test_credentials(self, host: str, port: int) -> None:
        """Validate credentials."""
        client = EversoloApiClient(
            host=host,
            port=port,
            session=async_create_clientsession(self.hass),
        )
        await client.async_get_data()
