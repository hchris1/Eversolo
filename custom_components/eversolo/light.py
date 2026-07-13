"""Light platform for Eversolo front-panel controls."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity


@dataclass(frozen=True, kw_only=True)
class EversoloLightDescription(LightEntityDescription):
    """Describe an Eversolo front-panel light."""

    brightness_key: str
    set_brightness: Callable[
        [EversoloDataUpdateCoordinator, int], Coroutine[Any, Any, None]
    ]
    is_light_on_key: str | None = None
    turn_on: (
        Callable[[EversoloDataUpdateCoordinator], Coroutine[Any, Any, None]] | None
    ) = None
    turn_off: (
        Callable[[EversoloDataUpdateCoordinator], Coroutine[Any, Any, None]] | None
    ) = None


ENTITY_DESCRIPTIONS = (
    EversoloLightDescription(
        key="display",
        translation_key="display",
        icon="mdi:monitor",
        brightness_key="display_brightness",
        set_brightness=lambda coordinator, brightness: (
            coordinator.client.async_set_display_brightness(brightness)
        ),
        is_light_on_key="is_display_on",
        turn_on=lambda coordinator: coordinator.client.async_trigger_turn_screen_on(),
        turn_off=lambda coordinator: coordinator.client.async_trigger_turn_screen_off(),
    ),
    EversoloLightDescription(
        key="knob",
        translation_key="knob",
        icon="mdi:knob",
        brightness_key="knob_brightness",
        set_brightness=lambda coordinator, brightness: (
            coordinator.client.async_set_knob_brightness(brightness)
        ),
        turn_off=lambda coordinator: coordinator.client.async_set_knob_brightness(0),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[EversoloDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up front-panel lights."""
    async_add_entities(
        EversoloLight(entry.runtime_data, description)
        for description in ENTITY_DESCRIPTIONS
    )


class EversoloLight(EversoloEntity, LightEntity):
    """Control display or knob illumination."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    entity_description: EversoloLightDescription

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: EversoloLightDescription,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._last_brightness: int | None = None

    @property
    def available(self) -> bool:
        """Return whether this model exposes the brightness setting."""
        return (
            super().available
            and self.coordinator.data.get(self.entity_description.brightness_key)
            is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the illumination is on."""
        if self.entity_description.is_light_on_key:
            screen_state = self.coordinator.data.get(
                self.entity_description.is_light_on_key
            )
            if screen_state is not None:
                return bool(screen_state)
        brightness = self.brightness
        return brightness > 0 if brightness is not None else None

    @property
    def brightness(self) -> int | None:
        """Return brightness in the 0..255 range."""
        return self.coordinator.data.get(self.entity_description.brightness_key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on and optionally set brightness."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            if self.entity_description.turn_on is not None:
                await self.entity_description.turn_on(self.coordinator)
            brightness = self._last_brightness or self.brightness or 128
        self._last_brightness = int(brightness)
        await self.entity_description.set_brightness(
            self.coordinator, self._last_brightness
        )
        await self.coordinator.async_refresh_settings()

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off illumination."""
        if self.brightness:
            self._last_brightness = self.brightness
        if self.entity_description.turn_off is not None:
            await self.entity_description.turn_off(self.coordinator)
        else:
            await self.entity_description.set_brightness(self.coordinator, 0)
        await self.coordinator.async_refresh_settings()
