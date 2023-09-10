"""Sensor platform for eversolo."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .const import DOMAIN
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity

VERSION_ENTITY_DESCRIPTION = SensorEntityDescription(
    key='version',
    name='Eversolo Version',
    icon='mdi:semantic-web',
)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    new_devices = []
    new_devices.append(EversoloVersionSensor(coordinator=coordinator, entity_description=VERSION_ENTITY_DESCRIPTION))

    if new_devices:
        async_add_devices(new_devices)


class EversoloVersionSensor(EversoloEntity, SensorEntity):
    """Eversolo Sensor class."""

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f'{coordinator.config_entry.entry_id}_{entity_description.key}'

    @property
    def native_value(self) -> str:
        """Return the native value of the sensor."""
        state = self.coordinator.data.get('music_control_state', None)

        if state is None:
            return None

        return state['volumeData']['version']
