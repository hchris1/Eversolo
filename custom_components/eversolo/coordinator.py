"""DataUpdateCoordinator for eversolo."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from wakeonlan import send_magic_packet

from .api import (
    EversoloApiClient,
    EversoloApiClientAuthenticationError,
    EversoloApiClientError,
)
from .const import CONF_NET_MAC, DEFAULT_UPDATE_INTERVAL, DOMAIN, LOGGER


class EversoloDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: EversoloApiClient,
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.data = {}

    async def _async_update_data(self):
        """Update data via library."""
        try:
            data = await self.client.async_get_data()

            if CONF_NET_MAC not in self.config_entry.data:
                await self._async_fetch_and_store_mac()

            return data
        except EversoloApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except EversoloApiClientError as exception:
            raise UpdateFailed(exception) from exception

    async def _async_fetch_and_store_mac(self) -> None:
        """Fetch and persist MAC address for Wake-on-LAN."""
        try:
            device_model = await self.client.async_get_device_model()
            net_mac = device_model.get("net_mac")
            if net_mac:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_NET_MAC: net_mac},
                )
                LOGGER.info("Stored MAC address for Wake-on-LAN: %s", net_mac)
        except Exception:
            LOGGER.debug("Could not fetch MAC address")

    async def async_send_wol(self) -> None:
        """Send Wake-on-LAN magic packet to power on the device."""
        net_mac = self.config_entry.data.get(CONF_NET_MAC)
        if net_mac:
            LOGGER.info("Sending Wake-on-LAN magic packet to %s", net_mac)
            await self.hass.async_add_executor_job(send_magic_packet, net_mac)
        else:
            LOGGER.warning(
                "No MAC address available for Wake-on-LAN - "
                "device must be powered on once to fetch MAC"
            )
