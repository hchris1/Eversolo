"""Base entity for Eversolo."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME
from .coordinator import EversoloDataUpdateCoordinator


class EversoloEntity(CoordinatorEntity[EversoloDataUpdateCoordinator]):
    """Represent an entity belonging to one Eversolo device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: EntityDescription

    def __init__(self, coordinator: EversoloDataUpdateCoordinator) -> None:
        """Initialize the entity while preserving legacy identifiers."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = entry.entry_id
        device_info = coordinator.device_info
        mac = device_info.get("net_mac")
        connections = {(CONNECTION_NETWORK_MAC, mac)} if mac else set()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            connections=connections,
            name=entry.title,
            model=device_info.get("model"),
            model_id=device_info.get("model"),
            sw_version=device_info.get("firmware"),
            manufacturer=NAME,
        )
