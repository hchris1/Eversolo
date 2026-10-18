"""Eversolo integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import EversoloApiClient
from .const import CONF_NET_MAC, LOGGER
from .coordinator import EversoloDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
]

type EversoloConfigEntry = ConfigEntry[EversoloDataUpdateCoordinator]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate existing entries without changing legacy entity identifiers."""
    if entry.version < 2:
        hass.config_entries.async_update_entry(entry, version=2)

    if entry.version < 3:
        unique_id = entry.unique_id
        if mac := entry.data.get(CONF_NET_MAC):
            unique_id = format_mac(mac)
        hass.config_entries.async_update_entry(
            entry,
            unique_id=unique_id,
            version=3,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: EversoloConfigEntry) -> bool:
    """Set up an Eversolo config entry."""
    coordinator = EversoloDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        client=EversoloApiClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            session=async_get_clientsession(hass),
        ),
    )
    entry.runtime_data = coordinator

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        if not coordinator.can_wake:
            raise
        LOGGER.info("Eversolo is offline; keeping Wake-on-LAN controls available")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EversoloConfigEntry) -> bool:
    """Unload an Eversolo config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
