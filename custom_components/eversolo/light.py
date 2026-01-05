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

from .const import DOMAIN, LOGGER
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity

_EversoloDataUpdateCoordinatorT = TypeVar(
    "_EversoloDataUpdateCoordinatorT", bound=EversoloDataUpdateCoordinator
)


@dataclass
class EversoloLightDescriptionMixin(Generic[_EversoloDataUpdateCoordinatorT]):
    """Mixin to describe a Light entity."""

    brightness_key: str
    set_brightness: Callable[
        [_EversoloDataUpdateCoordinatorT, int], Coroutine[Any, Any, None]
    ]
    key: str
    name: str
    icon: str
    is_light_on_key: str | None = None
    turn_on: Callable[[
        _EversoloDataUpdateCoordinatorT], Coroutine[Any, Any, None]] | None = None
    turn_off: Callable[[_EversoloDataUpdateCoordinatorT],
                       Coroutine[Any, Any, None]] | None = None


@dataclass
class EversoloLightDescription(
    LightEntityDescription,
    EversoloLightDescriptionMixin[_EversoloDataUpdateCoordinatorT],
):
    """Class to describe a Light entity."""


ENTITY_DESCRIPTIONS = [
    EversoloLightDescription[EversoloDataUpdateCoordinator](
        key="display",
        name="Eversolo Display",
        icon="mdi:tablet",
        brightness_key="display_brightness",
        set_brightness=lambda coordinator, brightness: coordinator.client.async_set_display_brightness(
            brightness
        ),
        is_light_on_key="is_display_on",
        turn_on=lambda coordinator: coordinator.client.async_trigger_turn_screen_on(),
        turn_off=lambda coordinator: coordinator.client.async_trigger_turn_screen_off(),
    ),
    EversoloLightDescription[EversoloDataUpdateCoordinator](
        key="knob",
        name="Eversolo Knob",
        icon="mdi:knob",
        brightness_key="knob_brightness",
        set_brightness=lambda coordinator, brightness: coordinator.client.async_set_knob_brightness(
            brightness
        ),
        turn_off=lambda coordinator: coordinator.client.async_set_knob_brightness(
            0
        ),
    ),
]


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the Light platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices(
        EversoloLight(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class EversoloLight(EversoloEntity, LightEntity):
    """Light to control Eversolo Lights."""

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: LightEntityDescription,
    ) -> None:
        """Initialize the Light class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self.last_brightness = None

    @property
    def is_on(self) -> bool:
        """Return true if the Light is on."""
        if self.entity_description.is_light_on_key is not None:
            return self.coordinator.data.get(
                self.entity_description.is_light_on_key, False
            )

        brightness = self.coordinator.data.get(
            self.entity_description.brightness_key, 0
        )

        if brightness is None:
            LOGGER.debug(
                "Value for key %s is None", self.entity_description.brightness_key
            )
            return None

        return brightness > 0

    @property
    def brightness(self):
        """Return brightness in range 0..255."""
        return self.coordinator.data.get(self.entity_description.brightness_key, 0)

    async def async_turn_on(self, **kwargs: any) -> None:
        """Turn on the Light."""
        has_attr_brightness = ATTR_BRIGHTNESS in kwargs

        if not has_attr_brightness:
            if self.entity_description.turn_on is not None:
                await self.entity_description.turn_on(self.coordinator)

            if self.entity_description.set_brightness is not None:
                brightness = self.last_brightness if self.last_brightness is not None else 128
                await self.entity_description.set_brightness(self.coordinator, brightness)

            await self.coordinator.async_request_refresh()
            return

        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self.last_brightness = brightness
        await self.entity_description.set_brightness(self.coordinator, brightness)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: any) -> None:
        """Turn off the Light."""
        if self.entity_description.turn_off is not None:
            await self.entity_description.turn_off(self.coordinator)
        await self.coordinator.async_request_refresh()
