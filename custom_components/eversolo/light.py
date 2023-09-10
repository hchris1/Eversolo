"""Light platform for eversolo."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from homeassistant.components.light import (
    LightEntity,
    LightEntityDescription,
    ColorMode,
    ATTR_BRIGHTNESS,
)

from .const import DOMAIN
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity


_EversoloDataUpdateCoordinatorT = TypeVar(
    '_EversoloDataUpdateCoordinatorT', bound=EversoloDataUpdateCoordinator
)


@dataclass
class EversoloLightDescriptionMixin(Generic[_EversoloDataUpdateCoordinatorT]):
    """Mixin to describe a Light entity."""

    brightness_key: str
    set_brightness: Callable[
        [_EversoloDataUpdateCoordinatorT], Coroutine[Any, Any, None]
    ]


@dataclass
class EversoloLightDescription(
    LightEntityDescription,
    EversoloLightDescriptionMixin[_EversoloDataUpdateCoordinatorT],
):
    """Class to describe a Light entity."""


ENTITY_DESCRIPTIONS = [
    EversoloLightDescription[EversoloDataUpdateCoordinator](
        key='display',
        name='Eversolo Display',
        icon='mdi:tablet',
        brightness_key='display_brightness',
        set_brightness=lambda coordinator, brightness: coordinator.client.async_set_display_brightness(
            brightness
        ),
    ),
    EversoloLightDescription[EversoloDataUpdateCoordinator](
        key='knob',
        name='Eversolo Knob',
        icon='mdi:knob',
        brightness_key='knob_brightness',
        set_brightness=lambda coordinator, brightness: coordinator.client.async_set_knob_brightness(
            brightness
        ),
    ),
]


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices(
        EversoloLight(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class EversoloLight(EversoloEntity, LightEntity):
    """Light to control Eversolo display brightness."""

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: LightEntityDescription,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_unique_id = (
            f'{coordinator.config_entry.entry_id}_{entity_description.key}'
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.data.get(self.entity_description.brightness_key, 0) > 0

    @property
    def brightness(self):
        return self.coordinator.data.get(self.entity_description.brightness_key, 0)

    async def async_turn_on(self, **kwargs: any) -> None:
        """Turn on the switch."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        await self.entity_description.set_brightness(self.coordinator, brightness)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: any) -> None:
        """Turn off the switch."""
        await self.entity_description.set_brightness(self.coordinator, 0)
        await self.coordinator.async_request_refresh()
