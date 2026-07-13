"""Button platform for Eversolo."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity


@dataclass(frozen=True, kw_only=True)
class EversoloButtonDescription(ButtonEntityDescription):
    """Describe an Eversolo button."""

    press_action: Callable[[EversoloDataUpdateCoordinator], Coroutine[Any, Any, None]]
    supported: Callable[[EversoloDataUpdateCoordinator], bool] = lambda _: True
    refresh_settings: bool = False
    available_when_off: bool = False


ENTITY_DESCRIPTIONS = (
    EversoloButtonDescription(
        key="reboot",
        translation_key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.client.async_trigger_reboot(),
        supported=lambda coordinator: bool(
            coordinator.device_info.get("ableRemoteReboot", True)
        ),
    ),
    EversoloButtonDescription(
        key="power_off",
        translation_key="power_off",
        icon="mdi:power-off",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: coordinator.client.async_trigger_power_off(),
    ),
    EversoloButtonDescription(
        key="power_on",
        translation_key="power_on",
        icon="mdi:power-on",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: coordinator.async_send_wol(),
        supported=lambda coordinator: coordinator.can_wake,
        available_when_off=True,
    ),
    EversoloButtonDescription(
        key="standby",
        translation_key="standby",
        icon="mdi:power-sleep",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: coordinator.client.async_trigger_standby(),
        supported=lambda coordinator: coordinator.can_standby,
    ),
    EversoloButtonDescription(
        key="toggle_screen_on_off",
        translation_key="toggle_screen",
        icon="mdi:monitor-shimmer",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: (
            coordinator.client.async_trigger_toggle_screen()
        ),
        refresh_settings=True,
    ),
    EversoloButtonDescription(
        key="cycle_screen_mode",
        translation_key="cycle_screen_mode",
        icon="mdi:gauge",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: (
            coordinator.client.async_trigger_cycle_screen_mode()
        ),
        refresh_settings=True,
    ),
    EversoloButtonDescription(
        key="cycle_screen_mode_spectrum",
        translation_key="cycle_screen_mode_spectrum",
        icon="mdi:chart-histogram",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: (
            coordinator.client.async_trigger_cycle_screen_mode(
                should_show_spectrum=True
            )
        ),
        refresh_settings=True,
    ),
    EversoloButtonDescription(
        key="turn_screen_on",
        translation_key="turn_screen_on",
        icon="mdi:monitor-eye",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: (
            coordinator.client.async_trigger_turn_screen_on()
        ),
        refresh_settings=True,
    ),
    EversoloButtonDescription(
        key="turn_screen_off",
        translation_key="turn_screen_off",
        icon="mdi:monitor-off",
        entity_registry_enabled_default=False,
        press_action=lambda coordinator: (
            coordinator.client.async_trigger_turn_screen_off()
        ),
        refresh_settings=True,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[EversoloDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eversolo buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        EversoloButton(coordinator, description)
        for description in ENTITY_DESCRIPTIONS
        if description.supported(coordinator)
    )


class EversoloButton(EversoloEntity, ButtonEntity):
    """Run an Eversolo command."""

    entity_description: EversoloButtonDescription

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: EversoloButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def available(self) -> bool:
        """Keep Wake-on-LAN available while the device is off."""
        return self.entity_description.available_when_off or super().available

    async def async_press(self) -> None:
        """Run the command."""
        await self.entity_description.press_action(self.coordinator)
        if self.entity_description.refresh_settings:
            await self.coordinator.async_refresh_settings()
