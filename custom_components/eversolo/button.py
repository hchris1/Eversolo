"""Button platform for eversolo."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity


_EversoloDataUpdateCoordinatorT = TypeVar(
    "_EversoloDataUpdateCoordinatorT", bound=EversoloDataUpdateCoordinator
)


@dataclass
class EversoloButtonDescriptionMixin(Generic[_EversoloDataUpdateCoordinatorT]):
    """Mixin to describe a Button entity."""

    press_action: Callable[[
        _EversoloDataUpdateCoordinatorT], Coroutine[Any, Any, None]]


@dataclass
class EversoloButtonDescription(
    ButtonEntityDescription,
    EversoloButtonDescriptionMixin[_EversoloDataUpdateCoordinatorT],
):
    """Class to describe a Button entity."""


ENTITY_DESCRIPTIONS = [
    EversoloButtonDescription[EversoloDataUpdateCoordinator](
        key="reboot",
        name="Eversolo Reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_reboot(),
    ),
    EversoloButtonDescription[EversoloDataUpdateCoordinator](
        key="power_off",
        name="Eversolo Power Off",
        icon="mdi:power-off",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_power_off(),
    ),
    EversoloButtonDescription[EversoloDataUpdateCoordinator](
        key="toggle_screen_on_off",
        name="Eversolo Toggle Screen On/Off",
        icon="mdi:toggle-switch",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_toggle_screen(),
    ),
    EversoloButtonDescription[EversoloDataUpdateCoordinator](
        key="cycle_screen_mode",
        name="Eversolo Cycle Screen Mode",
        icon="mdi:page-next",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_cycle_screen_mode(),
    ),
    EversoloButtonDescription[EversoloDataUpdateCoordinator](
        key="cycle_screen_mode_spectrum",
        name="Eversolo Cycle Screen Mode (Spectrum)",
        icon="mdi:page-next",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_cycle_screen_mode(
            should_show_spectrum=True),
    ),
    EversoloButtonDescription[EversoloDataUpdateCoordinator](
        key="turn_screen_on",
        name="Eversolo Turn Screen On",
        icon="mdi:toggle-switch",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_turn_screen_on(),
    ),
    EversoloButtonDescription[EversoloDataUpdateCoordinator](
        key="turn_screen_off",
        name="Eversolo Turn Screen Off",
        icon="mdi:toggle-switch-off",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_turn_screen_off(),
    ),
]


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the Button platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices(
        EversoloButton(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class EversoloButton(EversoloEntity, ButtonEntity):
    """Button to control Eversolo actions."""

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: EversoloButtonDescription[EversoloDataUpdateCoordinator],
    ) -> None:
        """Initialize Eversolo button."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    async def async_press(self) -> None:
        """Triggers the Eversolo button press service."""
        await self.entity_description.press_action(self.coordinator)
