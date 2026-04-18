"""Eversolo integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EversoloApiClient
from .const import DOMAIN, LOGGER, NAME
from .coordinator import EversoloDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to a new version."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        # Version 2: Update title from host IP to "Eversolo {model}" for proper
        # device naming with _attr_has_entity_name = True.
        title = NAME
        try:
            client = EversoloApiClient(
                host=entry.data[CONF_HOST],
                port=entry.data[CONF_PORT],
                session=async_get_clientsession(hass),
            )
            device_info = await client.async_get_device_model()
            model = device_info.get("model")
            if model:
                title = f"{NAME} {model}"
        except Exception as exception:
            LOGGER.warning(
                "Could not fetch device model during migration, "
                "using default title: %s",
                exception,
            )

        hass.config_entries.async_update_entry(entry, title=title, version=2)
        LOGGER.info("Migration to version 2 successful, title set to '%s'", title)

    if entry.version == 2:
        from .const import CONF_SHUTDOWN_ACTION, DEFAULT_SHUTDOWN_ACTION

        new_data = {**entry.data, CONF_SHUTDOWN_ACTION: DEFAULT_SHUTDOWN_ACTION}
        hass.config_entries.async_update_entry(entry, data=new_data, version=3)
        LOGGER.info("Migration to version 3 successful, added shutdown_action config")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator = EversoloDataUpdateCoordinator(
        hass=hass,
        client=EversoloApiClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            session=async_get_clientsession(hass),
        ),
    )

    # Accept offline device to expose WoL functionality
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        LOGGER.info(
            "Eversolo device is offline, integration set up will continue")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
