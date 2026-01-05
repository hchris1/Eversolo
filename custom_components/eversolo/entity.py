"""EversoloEntity class."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_FIRMWARE, CONF_MODEL, DOMAIN, NAME
from .coordinator import EversoloDataUpdateCoordinator


class EversoloEntity(CoordinatorEntity):
    """EversoloEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: EversoloDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=NAME,
            model=coordinator.config_entry.data.get(CONF_MODEL),
            sw_version=coordinator.config_entry.data.get(CONF_FIRMWARE),
            manufacturer=NAME,
        )
