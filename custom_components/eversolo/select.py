"""Select platform for Eversolo settings."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EversoloDataUpdateCoordinator
from .entity import EversoloEntity


@dataclass(frozen=True, kw_only=True)
class EversoloSelectDescription(SelectEntityDescription):
    """Describe an Eversolo select."""

    state_key: str
    options_key: str = "data"
    selected_key: str = "currentIndex"
    select_option: Callable[
        [EversoloDataUpdateCoordinator, int, str], Coroutine[Any, Any, None]
    ]


ENTITY_DESCRIPTIONS = (
    EversoloSelectDescription(
        key="vu_style",
        translation_key="vu_style",
        icon="mdi:gauge-low",
        entity_category=EntityCategory.CONFIG,
        state_key="vu_mode_state",
        select_option=lambda coordinator, index, tag: (
            coordinator.client.async_select_vu_mode_option(index, tag)
        ),
    ),
    EversoloSelectDescription(
        key="spectrum_style",
        translation_key="spectrum_style",
        icon="mdi:chart-histogram",
        entity_category=EntityCategory.CONFIG,
        state_key="spectrum_mode_state",
        select_option=lambda coordinator, index, tag: (
            coordinator.client.async_select_spectrum_mode_option(index, tag)
        ),
    ),
    EversoloSelectDescription(
        key="output_mode",
        translation_key="output_mode",
        icon="mdi:audio-input-stereo-minijack",
        entity_category=EntityCategory.CONFIG,
        state_key="input_output_state",
        options_key="transformed_outputs",
        selected_key="outputIndex",
        select_option=lambda coordinator, index, tag: (
            coordinator.client.async_set_output(index, tag)
        ),
    ),
)

KNOB_COLOR_DESCRIPTION = EversoloSelectDescription(
    key="knob_color",
    translation_key="knob_color",
    icon="mdi:palette",
    entity_category=EntityCategory.CONFIG,
    state_key="knob_color_state",
    select_option=lambda coordinator, index, tag: (
        coordinator.client.async_select_knob_color_option(index, tag)
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry[EversoloDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eversolo selects."""
    coordinator = entry.runtime_data
    descriptions = list(ENTITY_DESCRIPTIONS)
    if "knob_color_state" in coordinator.data:
        descriptions.append(KNOB_COLOR_DESCRIPTION)
    async_add_entities(
        EversoloSelect(coordinator, description) for description in descriptions
    )
    if coordinator.data.get("streaming_apps"):
        async_add_entities([EversoloStreamingAppSelect(coordinator)])


class EversoloSelect(EversoloEntity, SelectEntity):
    """Control an Eversolo enumerated setting."""

    entity_description: EversoloSelectDescription

    def __init__(
        self,
        coordinator: EversoloDataUpdateCoordinator,
        entity_description: EversoloSelectDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def _state_data(self) -> dict[str, Any]:
        """Return this select's cached API response."""
        return self.coordinator.data.get(self.entity_description.state_key) or {}

    @property
    def _raw_options(self) -> list[dict[str, Any]]:
        """Return normalized option objects."""
        return [
            option
            for option in self._state_data.get(self.entity_description.options_key)
            or []
            if isinstance(option, dict)
        ]

    @property
    def available(self) -> bool:
        """Return whether the setting is supported and the device is online."""
        return super().available and bool(self._raw_options)

    @property
    def options(self) -> list[str]:
        """Return available human-readable options."""
        return [
            str(option.get("title") or option.get("name") or option.get("tag"))
            for option in self._raw_options
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current option, preserving original device indexes."""
        selected = self._state_data.get(self.entity_description.selected_key)
        if not isinstance(selected, int):
            return None
        for position, option in enumerate(self._raw_options):
            option_index = int(option.get("index", position))
            if option_index == selected:
                return str(
                    option.get("title") or option.get("name") or option.get("tag")
                )
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the setting."""
        for position, value in enumerate(self._raw_options):
            title = str(value.get("title") or value.get("name") or value.get("tag"))
            if option != title:
                continue
            await self.entity_description.select_option(
                self.coordinator,
                int(value.get("index", position)),
                str(value.get("tag", "")),
            )
            await self.coordinator.async_refresh_settings()
            return


class EversoloStreamingAppSelect(EversoloEntity, SelectEntity):
    """Launch an installed music application from a native HA control."""

    _attr_translation_key = "streaming_app"
    _attr_icon = "mdi:apps"

    def __init__(self, coordinator: EversoloDataUpdateCoordinator) -> None:
        """Initialize the application launcher."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_streaming_app"
        self._attr_current_option = None

    @property
    def _apps(self) -> list[dict[str, Any]]:
        """Return discovered launchable applications."""
        return [
            app
            for app in self.coordinator.data.get("streaming_apps") or []
            if isinstance(app, dict) and app.get("packageName") and app.get("label")
        ]

    @property
    def available(self) -> bool:
        """Return whether applications were discovered."""
        return super().available and bool(self._apps)

    @property
    def options(self) -> list[str]:
        """Return friendly application names."""
        return [str(app["label"]) for app in self._apps]

    async def async_select_option(self, option: str) -> None:
        """Launch the selected application."""
        for app in self._apps:
            if app["label"] != option:
                continue
            await self.coordinator.client.async_open_app(str(app["packageName"]))
            self._attr_current_option = option
            self.async_write_ha_state()
            return
        raise HomeAssistantError(f"Eversolo application {option!r} is unavailable")
