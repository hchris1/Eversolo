"""Data coordinator for Eversolo devices."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util import dt as dt_util
from wakeonlan import send_magic_packet

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
    DEFAULT_POWER_BEHAVIOR,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    SETTINGS_UPDATE_INTERVAL,
    WOL_PORTS,
)


class EversoloDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate real-time state and slower-changing device settings."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: EversoloApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_info: dict[str, Any] = self._device_info_from_entry(config_entry)
        self._settings_data: dict[str, Any] = {}
        self._settings_refresh_at = 0.0
        self.last_realtime_update = None
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.data = {}

    @staticmethod
    def _device_info_from_entry(entry: ConfigEntry) -> dict[str, Any]:
        """Build the persisted identity fallback for an offline device."""
        return {
            "model": entry.data.get(CONF_MODEL),
            "firmware": entry.data.get(CONF_FIRMWARE),
            "net_mac": entry.data.get(CONF_NET_MAC),
            "ableRemoteBoot": entry.data.get(CONF_ABLE_REMOTE_BOOT, False),
            "ableRemoteSleep": entry.data.get(CONF_ABLE_REMOTE_SLEEP, False),
            "ableRemoteShutdown": entry.data.get(CONF_ABLE_REMOTE_SHUTDOWN, True),
            "ableRemoteReboot": entry.data.get(CONF_ABLE_REMOTE_REBOOT, True),
        }

    async def _async_setup(self) -> None:
        """Load device identity once, outside the two-second polling loop."""
        try:
            self.device_info = await self.client.async_get_device_model()
        except EversoloApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except EversoloApiClientError as err:
            if not self.device_info.get(CONF_NET_MAC):
                raise UpdateFailed(
                    f"Could not identify Eversolo device: {err}"
                ) from err
            LOGGER.debug("Using persisted device identity while offline: %s", err)
            return

        persistent = {
            **self.config_entry.data,
            CONF_MODEL: self.device_info.get("model"),
            CONF_FIRMWARE: self.device_info.get("firmware"),
            CONF_NET_MAC: self.device_info.get("net_mac"),
            CONF_ABLE_REMOTE_BOOT: bool(self.device_info.get("ableRemoteBoot", False)),
            CONF_ABLE_REMOTE_SLEEP: bool(
                self.device_info.get("ableRemoteSleep", False)
            ),
            CONF_ABLE_REMOTE_SHUTDOWN: bool(
                self.device_info.get("ableRemoteShutdown", True)
            ),
            CONF_ABLE_REMOTE_REBOOT: bool(
                self.device_info.get("ableRemoteReboot", True)
            ),
        }
        persistent = {
            key: value for key, value in persistent.items() if value is not None
        }
        if persistent != dict(self.config_entry.data):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=persistent,
                title=self._device_title,
                unique_id=(
                    format_mac(mac)
                    if self.config_entry.unique_id is None
                    and (mac := self.device_info.get("net_mac"))
                    else self.config_entry.unique_id
                ),
            )

    @property
    def _device_title(self) -> str:
        """Return a friendly config-entry title."""
        model = self.device_info.get("model")
        return f"Eversolo {model}" if model else "Eversolo"

    @property
    def can_wake(self) -> bool:
        """Return whether Wake-on-LAN can be offered."""
        return bool(
            self.device_info.get("ableRemoteBoot") and self.device_info.get("net_mac")
        )

    @property
    def can_standby(self) -> bool:
        """Return whether standby is advertised or discovered."""
        if self.device_info.get("ableRemoteSleep"):
            return True
        options = self._settings_data.get("power_options", {}).get("data") or []
        return any(
            isinstance(option, dict) and option.get("tag") == "standby"
            for option in options
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh playback state quickly and settings only when due."""
        try:
            playback = await self.client.async_get_music_control_state()
        except EversoloApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except EversoloApiClientCommunicationError as err:
            raise UpdateFailed(str(err)) from err
        except EversoloApiClientError as err:
            raise UpdateFailed(f"Invalid Eversolo response: {err}") from err

        now = time.monotonic()
        if now >= self._settings_refresh_at:
            self._settings_data = await self.client.async_get_settings_data(
                self._settings_data
            )
            self._settings_refresh_at = now + SETTINGS_UPDATE_INTERVAL

        self.last_realtime_update = dt_util.utcnow()
        return {"music_control_state": playback, **self._settings_data}

    async def async_refresh_settings(self) -> None:
        """Force settings to refresh after a command changes them."""
        self._settings_refresh_at = 0
        await self.async_request_refresh()

    async def async_send_wol(self) -> None:
        """Send the magic packet on Eversolo's documented and legacy ports."""
        net_mac = self.device_info.get("net_mac")
        if not net_mac:
            LOGGER.warning("No wired MAC address is available for Wake-on-LAN")
            return
        for port in WOL_PORTS:
            await self.hass.async_add_executor_job(
                partial(send_magic_packet, net_mac, port=port)
            )

    async def async_power_off(self) -> None:
        """Apply the configured power-off behavior."""
        behavior = self.config_entry.options.get(
            CONF_POWER_BEHAVIOR, DEFAULT_POWER_BEHAVIOR
        )
        if behavior == "standby" and self.can_standby:
            await self.client.async_trigger_standby()
        else:
            await self.client.async_trigger_power_off()

    @property
    def diagnostics_summary(self) -> dict[str, Any]:
        """Return non-sensitive coordinator state for diagnostics."""
        return {
            "host": self.config_entry.data.get(CONF_HOST),
            "port": self.config_entry.data.get(CONF_PORT),
            "last_update_success": self.last_update_success,
            "device_info": self.device_info,
            "available_data": sorted(self.data),
        }
