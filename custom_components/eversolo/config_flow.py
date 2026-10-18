"""Config and options flows for Eversolo."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    EversoloApiClient,
    EversoloApiClientAuthenticationError,
    EversoloApiClientCommunicationError,
    EversoloApiClientError,
)
from .const import (
    CONF_ABLE_REMOTE_BOOT,
    CONF_ABLE_REMOTE_REBOOT,
    CONF_ABLE_REMOTE_SHUTDOWN,
    CONF_ABLE_REMOTE_SLEEP,
    CONF_FIRMWARE,
    CONF_MODEL,
    CONF_NET_MAC,
    CONF_POWER_BEHAVIOR,
    DEFAULT_PORT,
    DEFAULT_POWER_BEHAVIOR,
    DOMAIN,
    LOGGER,
    NAME,
    POWER_BEHAVIORS,
)


class EversoloFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Eversolo configuration."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EversoloOptionsFlow:
        """Return the options flow."""
        return EversoloOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._async_create_entry(user_input)
            except EversoloApiClientAuthenticationError as err:
                LOGGER.warning("Eversolo rejected authentication: %s", err)
                errors["base"] = "auth"
            except EversoloApiClientCommunicationError as err:
                LOGGER.debug("Could not reach Eversolo: %s", err)
                errors["base"] = "connection"
            except EversoloApiClientError:
                LOGGER.exception("Unexpected Eversolo response during setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self._connection_schema(user_input),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle Eversolo mDNS discovery."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host:
                return self.async_abort(reason="already_configured")

        self._discovered = {CONF_HOST: host, CONF_PORT: port}
        display_name = discovery_info.name.removesuffix("._eversolo._tcp.local.")
        self.context["title_placeholders"] = {"name": display_name or NAME}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm a discovered device."""
        if self._discovered is None:
            return self.async_abort(reason="unknown")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._async_create_entry(self._discovered)
            except EversoloApiClientCommunicationError:
                errors["base"] = "connection"
            except EversoloApiClientError:
                LOGGER.exception("Could not confirm discovered Eversolo")
                errors["base"] = "unknown"
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Update host or port for an existing device."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        suggested = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data[CONF_PORT],
            **(user_input or {}),
        }
        if user_input is not None:
            try:
                device_info = await self._async_get_device_info(user_input)
            except EversoloApiClientCommunicationError:
                errors["base"] = "connection"
            except EversoloApiClientError:
                LOGGER.exception("Could not reconfigure Eversolo")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        **entry.data,
                        **user_input,
                        **self._identity(device_info),
                    },
                    title=self._title(device_info),
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._connection_schema(suggested),
            errors=errors,
        )

    async def _async_create_entry(
        self, connection: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Validate a device, enforce uniqueness, and create the entry."""
        device_info = await self._async_get_device_info(connection)
        unique_id = self._unique_id(device_info, connection)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: connection[CONF_HOST], CONF_PORT: connection[CONF_PORT]}
        )
        return self.async_create_entry(
            title=self._title(device_info),
            data={**connection, **self._identity(device_info)},
        )

    async def _async_get_device_info(
        self, connection: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the connection with the lightweight identity endpoint."""
        client = EversoloApiClient(
            host=connection[CONF_HOST],
            port=connection[CONF_PORT],
            session=async_get_clientsession(self.hass),
        )
        return await client.async_get_device_model()

    @staticmethod
    def _identity(device_info: dict[str, Any]) -> dict[str, Any]:
        """Extract stable identity and capabilities for offline startup."""
        values = {
            CONF_NET_MAC: device_info.get("net_mac"),
            CONF_MODEL: device_info.get("model"),
            CONF_FIRMWARE: device_info.get("firmware"),
            CONF_ABLE_REMOTE_BOOT: bool(device_info.get("ableRemoteBoot", False)),
            CONF_ABLE_REMOTE_SLEEP: bool(device_info.get("ableRemoteSleep", False)),
            CONF_ABLE_REMOTE_SHUTDOWN: bool(
                device_info.get("ableRemoteShutdown", True)
            ),
            CONF_ABLE_REMOTE_REBOOT: bool(device_info.get("ableRemoteReboot", True)),
        }
        return {key: value for key, value in values.items() if value is not None}

    @staticmethod
    def _unique_id(device_info: dict[str, Any], connection: dict[str, Any]) -> str:
        """Prefer wired MAC and fall back to the local endpoint."""
        if mac := device_info.get("net_mac"):
            return format_mac(mac)
        return f"{connection[CONF_HOST]}:{connection[CONF_PORT]}"

    @staticmethod
    def _title(device_info: dict[str, Any]) -> str:
        """Build a friendly device title."""
        model = device_info.get("model") or device_info.get("deviceName")
        return f"{NAME} {model}" if model else NAME

    @staticmethod
    def _connection_schema(
        suggested: dict[str, Any] | None,
    ) -> vol.Schema:
        """Return the shared connection form schema."""
        suggested = suggested or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=suggested.get(CONF_HOST),
                ): cv.string,
                vol.Required(
                    CONF_PORT,
                    default=suggested.get(CONF_PORT, DEFAULT_PORT),
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=65535,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Coerce(int),
                ),
            }
        )


class EversoloOptionsFlow(config_entries.OptionsFlowWithReload):
    """Manage behavior that can be changed after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit Eversolo options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POWER_BEHAVIOR,
                        default=self.config_entry.options.get(
                            CONF_POWER_BEHAVIOR, DEFAULT_POWER_BEHAVIOR
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(POWER_BEHAVIORS),
                            translation_key="power_behavior",
                        )
                    )
                }
            ),
        )
